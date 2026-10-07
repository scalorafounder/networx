"""CATCH: transcript chunk in, people and promises out (OpenAI), saved to Supabase.

    python catch.py <transcript.txt> [--from 14:03:00] [--to 14:20:00] [--dry]
"""
import argparse, json, os, re, requests
from common import env, db, EVENT, log

MODEL = "gpt-5.2"
SYSTEM = """You read a messy wristband transcript from a networking event. Speaker names are not labeled.
The wearer is the person wearing the recorder. Return JSON only:
{"people":[{"name":"","company":"","link":"","what_they_do":""}],
 "promises":[{"person":"","who_owes":"me|them","what":"","by_when":"","quote":""}]}
Rules:
- Only people clearly named and spoken to. Skip names you only half hear.
- A promise is a real commitment: connect on LinkedIn, send something, make an intro, set a call, meet again.
- "what" is one short action sentence. "quote" is the exact words from the transcript.
- by_when only if said, else "".
- Never invent a link or company. Leave empty if not said.
- The same promise said twice is one promise."""


def slice_lines(path, a, b):
    out = []
    for ln in open(path, encoding="utf-8"):
        m = re.match(r"- (\d\d:\d\d:\d\d) ", ln)
        if m and (not a or m.group(1) >= a) and (not b or m.group(1) <= b):
            out.append(ln.strip()[2:])
    return "\n".join(out)


def extract_box(text):
    """Fallback when OpenAI refuses (no credit): the Agent37 box's own model reads it."""
    import a37
    out = a37.ask(SYSTEM + "\n\nTRANSCRIPT:\n" + text + "\n\nReply with the JSON object only.")
    t = out.get("output_text") or json.dumps(out)
    return json.loads(re.search(r"\{.*\}", t, re.S).group(0))


def extract(text):
    import pathlib
    note = os.environ.get("CONTEXT", "")
    ctx = pathlib.Path(os.environ.get("CONTEXT_FILE", "context.txt"))
    if not note and ctx.exists():
        note = ctx.read_text(encoding="utf-8")
    if note:
        text = "NOTES FROM THE WEARER:\n" + note + "\nTRANSCRIPT:\n" + text
    if not os.environ.get("OPENAI_API_KEY"):
        return extract_box(text)
    try:
        return extract_openai(text)
    except requests.HTTPError as e:
        print("OpenAI refused (%s), using the Agent37 box instead" % e.response.status_code)
        return extract_box(text)


def extract_openai(text):
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
                      json={"model": MODEL, "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": text}]}, timeout=120)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def save(data):
    c = db()
    for p in data.get("people", []):
        c.execute("""insert into event_agent.people(event,name,company,link,what_they_do) values(%s,%s,%s,%s,%s)
                     on conflict (event,name) do update set company=coalesce(nullif(excluded.company,''),event_agent.people.company),
                     link=coalesce(nullif(excluded.link,''),event_agent.people.link),
                     what_they_do=coalesce(nullif(excluded.what_they_do,''),event_agent.people.what_they_do)""",
                  (EVENT, p["name"], p.get("company"), p.get("link"), p.get("what_they_do")))
    for p in data.get("people", []):
        log("person", p.get("what_they_do") or "", person=p["name"], c=c)
    seen = []
    for q in data.get("promises", []):
        words = set(re.findall(r"[a-z0-9]+", (q["person"] + " " + q["what"]).lower())) - {"the", "a", "to", "with", "on", "and", "of"}
        if any(len(words & w) / max(1, min(len(words), len(w))) >= 0.6 for w in seen):
            continue          # same promise said twice
        seen.append(words)
        pid = c.execute("insert into event_agent.promises(event,person,who_owes,what,by_when,quote) values(%s,%s,%s,%s,%s,%s) returning id",
                        (EVENT, q["person"], q.get("who_owes", "me"), q["what"], q.get("by_when"), q.get("quote"))).fetchone()[0]
        log("promise", q["what"], promise_id=pid, person=q["person"], c=c)
    c.execute("insert into event_agent.runs(kind,note) values('catch',%s)",
              (f"{len(data.get('people',[]))} people, {len(data.get('promises',[]))} promises",))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--from", dest="a"); ap.add_argument("--to", dest="b")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    d = extract(slice_lines(a.file, a.a, a.b))
    print(json.dumps(d, indent=1))
    if not a.dry:
        save(d); print("saved")
