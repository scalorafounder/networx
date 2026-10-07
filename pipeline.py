"""The whole agent in one call: text in, drafts on your phone.
Any device that can produce a transcript (Bee, Plaud, Pocket, Omi, a phone web page) calls process().
"""
import os, re, time
from concurrent.futures import ThreadPoolExecutor
import catch, do
from common import db, EVENT, log

KEY = re.compile(r"connect|linkedin|intro|call|send|deck|coffee|email|meet", re.I)


def heard(text, pace=0.0):
    lines = [re.sub(r"^\d\d:\d\d:\d\d ", "", l.strip()) for l in text.splitlines() if l.strip()]
    shown = [l for i, l in enumerate(lines) if KEY.search(l) or i % 9 == 0][:40]
    c = db()
    for l in shown:
        log("heard", l[:220], c=c)
        time.sleep(pace)
    return len(lines)


def process(text, source="api", pace=0.0, status=None, place=None):
    st = status or (lambda s: None)
    st("listening")
    n = heard(text, pace)
    st("catching")
    if place:
        os.environ["EVENT_PLACE"] = place   # do.py adds it to the draft prompt
        text = "Where: " + place + "\n" + text
    else:
        os.environ.pop("EVENT_PLACE", None)
    data = catch.extract(text)
    catch.save(data)
    st("working")
    c = db()
    rows = c.execute("""select p.id,p.person,p.who_owes,p.what,p.by_when,p.quote,pe.company from event_agent.promises p
        left join event_agent.people pe on pe.event=p.event and pe.name=p.person
        where p.event=%s and p.status='open' order by p.id""", (EVENT,)).fetchall()

    def one(r):
        try:
            do.run_one(db(), r)
        except Exception as e:
            c2 = db()
            c2.execute("update event_agent.promises set status='needs_you', research=%s where id=%s", (f"agent failed: {e}"[:300], r[0]))
            log("sent", "Needs you: " + str(e)[:100], promise_id=r[0], person=r[1], c=c2)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, rows))
    fire_recap(st)
    st("done")
    return {"lines": n, "people": len(data.get("people", [])), "promises": len(rows)}


def reset():
    c = db()
    for t in ("events", "promises", "people"):
        c.execute(f"delete from event_agent.{t} where event=%s", (EVENT,))


def fire_recap(st):
    """Fire the 30 minute timer on the Agent37 box now and wait for its recap."""
    import os, pathlib
    cron_id = os.environ.get("CRON_ID", "").strip()
    if not cron_id:
        f = pathlib.Path(__file__).with_name(".cron")
        cron_id = f.read_text().strip() if f.exists() else ""
    if not cron_id:
        return  # no timer set up: skip cleanly
    import a37
    c = db()
    before = c.execute("select count(*) from event_agent.runs where kind='recap'").fetchone()[0]
    st("recap")
    a37.run_cron(cron_id)
    for _ in range(45):
        time.sleep(2)
        if c.execute("select count(*) from event_agent.runs where kind='recap'").fetchone()[0] > before:
            break
