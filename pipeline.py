"""The whole agent in one call: text in, drafts out.
Any device that can produce a transcript (Bee, Plaud, Pocket, Omi, a phone web page) calls process().
"""
import os, re, time
from concurrent.futures import ThreadPoolExecutor
import catch, do
from common import db, event, set_event, log

KEY = re.compile(r"connect|linkedin|intro|call|send|deck|coffee|email|meet|invite", re.I)
SPEAKER = re.compile(r"^[A-Z][A-Za-z.' ]+( \([^)]*\))?:")


def clean(l):
    return re.sub(r"^\d\d:\d\d:\d\d ", "", l.strip())


def heard(text, pace=0.0):
    lines = [clean(l) for l in text.splitlines() if l.strip()]
    labeled = sum(1 for l in lines if SPEAKER.match(l)) >= max(2, len(lines) // 2)
    shown = lines[:60] if labeled else [l for i, l in enumerate(lines) if KEY.search(l) or i % 9 == 0][:40]
    c = db()
    for l in shown:
        log("heard", l[:260], c=c)
        time.sleep(pace)
    return lines


def process(text, source="api", pace=0.0, status=None, place=None, recap=True, context=None):
    st = status or (lambda s: None)
    ev = event()
    st("listening")
    if context:
        log("context", context, c=db())
    lines = heard(text, pace)
    st("catching")
    numbered = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines))
    if place:
        os.environ["EVENT_PLACE"] = place   # do.py adds it to the draft prompt
        numbered = "Where: " + place + "\n" + numbered
    else:
        os.environ.pop("EVENT_PLACE", None)
    data = catch.extract(numbered)
    catch.save(data, "\n".join(lines))
    st("working")
    c = db()
    rows = c.execute(do.OPEN_ROWS + " order by p.id", (ev,)).fetchall()

    def one(r):
        set_event(ev)
        try:
            do.run_one(db(), r)
        except Exception as e:
            c2 = db()
            c2.execute("update event_agent.promises set status='needs_you', research=%s where id=%s", (f"agent failed: {e}"[:300], r[0]))
            log("sent", "Needs you: " + str(e)[:100], promise_id=r[0], person=r[1], c=c2)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, rows))
    if recap:
        t_left = time.time()
        log("left", "You left the venue (sample). Writing your briefing.", c=db())
        fire_recap(st)
        log("briefing", f"Briefing ready {round(time.time() - t_left)} seconds after you left.", c=db())
    st("done")
    return {"lines": len(lines), "people": len(data.get("people", [])), "promises": len(rows)}


def reset():
    c = db()
    for t in ("events", "promises", "people"):
        c.execute(f"delete from event_agent.{t} where event=%s", (event(),))


def fire_recap(st):
    """Fire the 30 minute timer on the Agent37 box now and wait for its recap."""
    import pathlib
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
    for _ in range(18):
        time.sleep(2)
        if c.execute("select count(*) from event_agent.runs where kind='recap'").fetchone()[0] > before:
            break
