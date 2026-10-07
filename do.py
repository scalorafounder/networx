"""DO: each open promise goes to the Agent37 box as a task. The box researches and
writes a DRAFT of the right kind (email, intro or calendar invite). The result goes to
Supabase. Nothing is sent to anyone. A draft is "ready", never "sent".

    python do.py            # all open promises
    python do.py --id 3     # one
"""
import argparse, json, os, re
import a37
import events
from common import db, event, log
from notify import send as telegram

LABEL = {"email": "Email", "intro": "Intro", "calendar": "Calendar invite"}

BASE = """You are the wearer's follow-up agent at an event. Write ONE draft. Never send anything to anyone.
Person met: {person}{company}{role}
What they asked for: {ask}
The wearer's promise: {what}
Exact words: "{quote}"
Context from the wearer: {context}
Write in plain words, seventh grade, short sentences, no em dashes, no hype. Do not invent facts, emails or links. Use [deck link] where a link belongs.
"""

KIND = {
    "email": """Write an EMAIL to {person}. First line: Subject. Then the body. Start with 'As promised' and say the deck is linked below. Mention what she said she wants ({ask}). One line on why the deck is relevant. Offer to talk next week.""",
    "intro": """Write a short double opt-in INTRO message to the OTHER person named in the exact words (not to {person}). Ask if they are open to meeting {person}{role_company}. Give one line of context from the conversation ({ask}). Make it easy to say no. Do not make the introduction yet.""",
    "calendar": """Write a CALENDAR INVITE draft to {person}. Give: Title, When ({slot}), Length 30 minutes, and a one line agenda from the conversation. It is a tentative hold the wearer confirms with one tap. Say it was checked against the wearer's calendar.""",
    "other": """Write the best short follow-up message to {person} that keeps this promise.""",
}


def run_one(c, row):
    c = db()  # own connection so jobs can run side by side
    pid, person, who_owes, what, by_when, quote, company, kind, role, ask = (list(row) + [None] * 10)[:10]
    kind = kind if kind in KIND else "other"
    c.execute("update event_agent.promises set status='doing', updated_at=now() where id=%s", (pid,))
    slot = events.free_slot()
    slot_text = f"{slot['day']}, {slot['start']} to {slot['end']}" if slot else "a free 30 minutes next week"
    head = BASE.format(person=person, company=f" ({company})" if company else "", role=f", {role}" if role else "",
                       ask=ask or "not said", what=what, quote=quote or "",
                       context=((os.environ.get("CONTEXT") or "none") + (" Where this happened: " + os.environ["EVENT_PLACE"] if os.environ.get("EVENT_PLACE") else "")))
    body = KIND[kind].format(person=person, ask=ask or "what they said", slot=slot_text,
                             role_company=(f" ({role}{', ' + company if company else ''})" if role or company else ""))
    prompt = head + "\n" + body + '\nReply with JSON only: {"research":"one line on anything useful you know about them or their company, only what you can see","draft":"the full draft text"}'
    log("box", "Agent37 box is working on it", promise_id=pid, person=person, c=c)
    out = a37.ask(prompt)
    t = out.get("output_text") or json.dumps(out)
    d = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
    label = LABEL.get(kind, "Draft")
    msg = (f"READY, not sent. {label} for {person}\n\n{d.get('draft')}\n\nWhat I found: {d.get('research')}")
    c.execute("""update event_agent.promises set research=%s, draft=%s, channel=%s, agent_session=%s, updated_at=now() where id=%s""",
              (d.get("research"), d.get("draft"), label, out.get("session_id"), pid))
    log("found", d.get("research") or "", promise_id=pid, person=person, c=c)
    log("draft", d.get("draft") or "", promise_id=pid, person=person, c=c)
    mid = telegram(msg)
    c.execute("update event_agent.promises set status='ready', telegram_sent_at=now(), updated_at=now() where id=%s", (pid,))
    log("sent", ("Ready on screen. Not sent to " if mid == "screen" else "Sent to your phone. Not sent to ") + person + ".", promise_id=pid, person=person, c=c)
    print(f"promise {pid}: ready ({label}), output {mid}")


OPEN_ROWS = """select p.id,p.person,p.who_owes,p.what,p.by_when,p.quote,pe.company,p.kind,pe.role,p.ask from event_agent.promises p
           left join event_agent.people pe on pe.event=p.event and pe.name=p.person
           where p.event=%s and p.status='open' """

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--id", type=int); a = ap.parse_args()
    c = db()
    q = OPEN_ROWS + ("and p.id=%s" if a.id else "") + " order by p.id"
    rows = c.execute(q, (event(), a.id) if a.id else (event(),)).fetchall()
    for r in rows:
        try:
            run_one(c, r)
        except Exception as e:
            c.execute("update event_agent.promises set status='needs_you', research=%s, updated_at=now() where id=%s",
                      (f"agent failed: {e}"[:300], r[0]))
