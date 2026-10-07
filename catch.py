"""CATCH: transcript chunk in, people and promises out (OpenAI), saved to Supabase.

    python catch.py <transcript.txt> [--from 14:03:00] [--to 14:20:00] [--dry]
"""
import argparse, json, os, re, requests
from common import env, db, event, log

MODEL = "gpt-5.2"
SYSTEM = """You read a numbered transcript from a networking event. Lines may start with a speaker name.
The wearer is the person marked (you), or the person wearing the recorder. Return JSON only:
{"people":[{"name":"","company":"","role":"","what_they_do":""}],
 "promises":[{"person":"","who_owes":"me|them","what":"","kind":"email|intro|calendar|other","ask":"","by_when":"","quote":"","line":0}]}
Rules:
- people: only people clearly named and spoken to (not people only mentioned). Use role and company only if said.
- A promise is a real commitment: send something, make an intro, set a meeting, connect, meet again.
- kind: email = the wearer will send material by email (a deck, a document). intro = the wearer will introduce them to a third person. calendar = a meeting or call will be set.
- who_owes is me when the wearer must act, them when the other person must act.
- ask = what the other person asked for or said they want, in a few words. Empty if none.
- what is one short action sentence. quote is the exact words of the transcript line. line is that line's number.
- by_when only if said, else "".
- Never invent a company, role, link or email. The same promise said twice is one promise."""


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
        c.execute("""insert into event_agent.people(event,name,company,link,what_they_do,role) values(%s,%s,%s,%s,%s,%s)
                     on conflict (event,name) do update set company=coalesce(nullif(excluded.company,''),event_agent.people.company),
                     link=coalesce(nullif(excluded.link,''),event_agent.people.link),
                     what_they_do=coalesce(nullif(excluded.what_they_do,''),event_agent.people.what_they_do),
                     role=coalesce(nullif(excluded.role,''),event_agent.people.role)""",
                  (event(), p["name"], p.get("company"), p.get("link"), p.get("what_they_do"), p.get("role")))
    for p in data.get("people", []):
        log("person", " · ".join(x for x in (p.get("role"), p.get("company")) if x) or (p.get("what_they_do") or ""), person=p["name"], c=c)
    seen = []
    seen_kind = []
    for q in data.get("promises", []):
        words = set(re.findall(r"[a-z0-9]+", q["what"].lower())) - {"the", "a", "to", "with", "on", "and", "of", "send", "for", "by", "in", "at", "will", "me", "my"}
        if q.get("kind") in ("email", "intro", "calendar") and (q["person"], q["kind"]) in seen_kind:
            continue          # one draft per kind per person is enough for a single conversation
        if any(len(words & w) / max(1, min(len(words), len(w))) >= 0.75 for w in seen):
            continue          # same promise said twice
        seen_kind.append((q["person"], q.get("kind")))
        seen.append(words)
        pid = c.execute("insert into event_agent.promises(event,person,who_owes,what,by_when,quote,line,kind,ask) values(%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                        (event(), q["person"], q.get("who_owes", "me"), q["what"], q.get("by_when"), q.get("quote"), (int(q["line"]) if str(q.get("line") or "").isdigit() else None), q.get("kind"), q.get("ask"))).fetchone()[0]
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
