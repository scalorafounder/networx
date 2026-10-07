"""Phone listening sessions. The page sends transcript chunks every ~20 seconds, so nothing is
lost if the phone pauses the page. When the person taps Stop (or comes back later), finish()
runs the same agent on everything heard and returns next steps."""
from common import db, set_event
import pipeline


def _ev(session):
    return "listen-" + "".join(ch for ch in session if ch.isalnum())[:24]


def chunk(session, seq, text, place=None):
    c = db()
    c.execute("insert into event_agent.chunks(session,seq,text,place) values(%s,%s,%s,%s)", (session, seq, text, place))
    rows = c.execute("select text from event_agent.chunks where session=%s", (session,)).fetchall()
    return {"ok": True, "words_total": sum(len((r[0] or "").split()) for r in rows)}


def _tips(steps):
    tips = []
    if steps:
        tips.append(f"Send your {len(steps)} draft{'s' if len(steps) != 1 else ''} today, while they still remember you.")
    for s in steps:
        if s["channel"] == "Calendar invite":
            tips.append(f"Confirm the time you promised {s['person']} so it does not slip.")
            break
    tips.append("Message the one person who matters most first. The rest can wait until tomorrow.")
    return tips[:4]


def result(session):
    ev = _ev(session)
    c = db()
    rows = c.execute("select person,who_owes,what,channel,draft,research,status from event_agent.promises where event=%s order by id", (ev,)).fetchall()
    if rows and all(r[6] in ("ready", "done", "needs_you") for r in rows):
        steps = [{"person": r[0], "who_owes": r[1], "what": r[2], "channel": r[3] or "Draft", "draft": r[4] or "", "research": r[5] or ""} for r in rows]
        people = c.execute("select count(*) from event_agent.people where event=%s", (ev,)).fetchone()[0]
        return {"ok": True, "status": "done", "summary": {"people": people, "promises": len(rows)},
                "nextSteps": steps, "tips": _tips(steps)}
    texts = [r[0] or "" for r in c.execute("select text from event_agent.chunks where session=%s", (session,)).fetchall()]
    ch = (len(texts), sum(len(t.split()) for t in texts))
    if ch[0]:
        return {"ok": True, "status": "collecting", "chunks": ch[0], "words": int(ch[1])}
    return {"ok": True, "status": "empty"}


def finish(session):
    ev = _ev(session)
    done = result(session)
    if done["status"] == "done":
        return done
    c = db()
    rows = c.execute("select text, place from event_agent.chunks where session=%s order by seq, id", (session,)).fetchall()
    text = "\n".join((r[0] or "").strip() for r in rows if r[0]).strip()
    if len(text) < 30:
        return {"ok": False, "error": "I did not hear enough yet. Keep listening a little longer."}
    place = next((r[1] for r in rows if r[1]), None)
    set_event(ev)
    pipeline.process(text, "phone-web", 0.0, None, place, False, None)
    return result(session)
