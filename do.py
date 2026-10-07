"""DO: each open promise goes to the Agent37 box as a task. The box researches and
writes a DRAFT. Result goes to Supabase, then one Telegram message to the wearer only.
Nothing is sent to anyone else. A draft is "ready", never "sent".

    python do.py            # all open promises
    python do.py --id 3     # one
"""
import argparse, json, os, re
import a37
from common import db, EVENT, log
from notify import send as telegram

TASK = """You are the wearer's follow-up agent at an event. Do ONE job and write a DRAFT only. Never send anything to anyone.
Person: {person}{company}
What was said: "{quote}"
Job: {what}
Who owes it: {who_owes}
Timing said: {by_when}
Context from the wearer: {context}
If the person's company has a website, look at it if you can and say in one line what they do, only what you can see. Do not invent facts, emails or links.
Write the draft in plain words, seventh grade, short sentences, no em dashes, no hype.
Pick the channel: linkedin, email, intro, or calendar. For calendar write a hold title and a suggested window (1 to 2 weeks out), not a fake date.
Reply with JSON only: {{"research":"one or two lines of what you found","channel":"","draft":"the message or hold text"}}"""


def run_one(c, row):
    c = db()  # own connection so jobs can run side by side
    pid, person, who_owes, what, by_when, quote, company = row
    c.execute("update event_agent.promises set status='doing', updated_at=now() where id=%s", (pid,))
    prompt = TASK.format(person=person, company=f" ({company})" if company else "", quote=quote or "",
                         what=what, who_owes=who_owes, by_when=by_when or "not said", context=((os.environ.get("CONTEXT") or "none") + (" Where this happened: " + os.environ["EVENT_PLACE"] if os.environ.get("EVENT_PLACE") else "")))
    log("box", "Agent37 box is working on it", promise_id=pid, person=person, c=c)
    out = a37.ask(prompt)
    t = out.get("output_text") or json.dumps(out)
    d = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
    msg = (f"READY, not sent. Promise {pid} for {person}\n"
           f"Job: {what}\nChannel: {d.get('channel')}\n\nDRAFT:\n{d.get('draft')}\n\nWhat I found: {d.get('research')}")
    c.execute("""update event_agent.promises set research=%s, draft=%s, channel=%s, agent_session=%s, updated_at=now() where id=%s""",
              (d.get("research"), d.get("draft"), d.get("channel"), out.get("session_id"), pid))
    log("found", d.get("research") or "", promise_id=pid, person=person, c=c)
    log("draft", d.get("draft") or "", promise_id=pid, person=person, c=c)
    mid = telegram(msg)
    c.execute("update event_agent.promises set status='ready', telegram_sent_at=now(), updated_at=now() where id=%s", (pid,))
    log("sent", ("Ready on screen. Not sent to " if mid == "screen" else "Sent to your phone. Not sent to ") + person + ".", promise_id=pid, person=person, c=c)
    print(f"promise {pid}: ready, telegram message {mid}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--id", type=int); a = ap.parse_args()
    c = db()
    q = """select p.id,p.person,p.who_owes,p.what,p.by_when,p.quote,pe.company from event_agent.promises p
           left join event_agent.people pe on pe.event=p.event and pe.name=p.person
           where p.event=%s and p.status='open' """ + ("and p.id=%s" if a.id else "") + " order by p.id"
    rows = c.execute(q, (EVENT, a.id) if a.id else (EVENT,)).fetchall()
    for r in rows:
        try:
            run_one(c, r)
        except Exception as e:
            c.execute("update event_agent.promises set status='needs_you', research=%s, updated_at=now() where id=%s",
                      (f"agent failed: {e}"[:300], r[0]))
            print("promise", r[0], "needs you:", e)
