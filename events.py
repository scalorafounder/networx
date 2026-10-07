"""Which event are you at, and when are you free? Plain logic on sample data.

detect(): closest venue wins. If two venues are too close to tell apart, the event
actually in progress wins. If it is still a tie, ask the person with one tap.
free_slot(): first free 30 minutes next week, from a busy list.
The RSVPs and busy times below are SAMPLE data. Swap in your Google Calendar reader.
"""
import datetime as dt
import math

SAMPLE_RSVPS = [
    {"title": "Founders & Funders Mixer", "start": "17:30", "end": "19:30", "address": "Pier 70, San Francisco", "lat": 37.7616, "lng": -122.3866},
    {"title": "AI Builders Happy Hour", "start": "18:00", "end": "20:00", "address": "Dogpatch Studio, San Francisco", "lat": 37.7581, "lng": -122.3879},
]
SAMPLE_BUSY_NEXT_WEEK = [("Mon", "10:00", "12:00"), ("Tue", "11:00", "12:30"), ("Wed", "14:00", "15:00")]
TOO_CLOSE_M = 120


def meters(a, b):
    r = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def detect(rsvps, lat, lng, now_hhmm):
    ranked = sorted(({**r, "meters": round(meters((lat, lng), (r["lat"], r["lng"])))} for r in rsvps), key=lambda r: r["meters"])
    best = ranked[0]
    if len(ranked) == 1:
        return {"event": best["title"], "reason": "your only RSVP today", "ask": False, "meters": best["meters"]}
    gap = ranked[1]["meters"] - best["meters"]
    if gap >= TOO_CLOSE_M:
        return {"event": best["title"], "reason": f"closest venue ({best['meters']} m away, next one {ranked[1]['meters']} m)", "ask": False, "meters": best["meters"]}
    live = [r for r in ranked if r["start"] <= now_hhmm <= r["end"]]
    if len(live) == 1:
        return {"event": live[0]["title"], "reason": "venues too close to separate, so the event in progress", "ask": False, "meters": live[0]["meters"]}
    return {"event": best["title"], "reason": "too close to call, one tap to confirm", "ask": True, "meters": best["meters"]}


def free_slot(busy=None, today=None):
    busy = SAMPLE_BUSY_NEXT_WEEK if busy is None else busy
    today = today or dt.date.today()
    monday = today + dt.timedelta(days=(7 - today.weekday()))
    names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for i, n in enumerate(names):
        day = monday + dt.timedelta(days=i)
        for h in range(11, 17):
            for m in (0, 30):
                s = f"{h:02d}:{m:02d}"
                e = f"{h:02d}:{m + 30:02d}" if m == 0 else f"{h + 1:02d}:00"
                if not any(b[0] == n and not (e <= b[1] or s >= b[2]) for b in busy):
                    return {"day": day.strftime("%A %B %d").replace(" 0", " "), "start": s, "end": e}
    return None


def sample_context(now_hhmm="18:05"):
    # the sample person stands at the Founders & Funders Mixer
    d = detect(SAMPLE_RSVPS, 37.7614, -122.3869, now_hhmm)
    d["considered"] = len(SAMPLE_RSVPS)
    return d
