"""CHECK LATER: runs on the Agent37 box on a timer. Re-checks open promises and
sends one recap to the wearer: "You met N people. M promises. X ready, Y need you."
Reads DATABASE_URL and the OUTPUT settings from the box env. With OUTPUT=screen nothing is sent."""
from common import db, EVENT
from notify import send as telegram

c = db()
people = c.execute("select count(*) from event_agent.people where event=%s", (EVENT,)).fetchone()[0]
rows = c.execute("select status,count(*) from event_agent.promises where event=%s group by 1", (EVENT,)).fetchall()
n = dict(rows); total = sum(n.values())
ready = n.get("ready", 0) + n.get("done", 0)
need = n.get("needs_you", 0) + n.get("open", 0) + n.get("doing", 0)
msg = (f"Recap. You met {people} {'person' if people == 1 else 'people'}. {total} promises. {ready} drafts ready, {need} still need you.\n"
       "Nothing has been sent to anyone. Tap each draft to send it yourself.")
mid = telegram(msg)
c.execute("insert into event_agent.runs(kind,note) values('recap',%s)", (msg,))
print("recap saved" if mid == "screen" else "recap sent", mid)
