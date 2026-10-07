"""One small server. Run: python server.py   then open http://localhost:8790/agent

  GET  /agent        the clean agent view (what it is doing, live)
  GET  /deck/        the presentation (the demo is inside it)
  GET  /listen       phone web page: talk, it sends transcript here (page must stay open)
  GET  /api/state    everything the screen needs
  POST /api/run      replay sample/charlie.txt
  POST /api/ingest   {"text": "...", "source": "plaud", "location": {"lat": 0, "lng": 0, "label": "Corgi Cafe, SF"}}
                     any device or tool can call this. location (or "place": "...") is optional.
  GET  /api/health   {"ok": true, "box": bool, "db": bool}
  POST /api/reset    clear this event's rows
Set INGEST_TOKEN to require header X-Token on /api/ingest.
"""
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pipeline
from common import db, EVENT

HERE = Path(__file__).parent
SAMPLE = HERE / "sample" / "charlie.txt"
STATE = {"phase": "idle", "started": None, "source": None, "error": None, "place": None}
LOCK = threading.Lock()


def set_phase(p):
    STATE["phase"] = p


def run_text(text, source, pace, place=None):
    with LOCK:
        STATE.update(phase="listening", started=time.time(), source=source, error=None, place=place)
        try:
            pipeline.process(text, source, pace, set_phase, place)
        except Exception as e:
            STATE.update(phase="error", error=str(e)[:200])


def sample_text():
    return SAMPLE.read_text(encoding="utf-8").strip()


def place_of(b):
    """Read the optional place: {"location": {"lat","lng","label"}} or {"place": "..."}."""
    loc = b.get("location")
    if isinstance(loc, dict):
        label = (loc.get("label") or "").strip()
        if label:
            return label[:120]
        if loc.get("lat") is not None and loc.get("lng") is not None:
            return "%.4f, %.4f" % (float(loc["lat"]), float(loc["lng"]))
    p = (b.get("place") or "").strip()
    return p[:120] or None


def health():
    out = {"ok": True, "box": False, "db": False}
    try:
        db().execute("select 1")
        out["db"] = True
    except Exception:
        pass
    try:
        import a37, requests
        r = requests.get(f"{a37.API}/instances/{a37.box()}", headers=a37._h(), timeout=10)
        out["box"] = r.ok
    except Exception:
        pass
    return out


def state():
    c = db()
    people = [dict(zip(("name", "company", "what"), r)) for r in c.execute(
        "select name,company,what_they_do from event_agent.people where event=%s order by id", (EVENT,)).fetchall()]
    cols = ("id", "person", "who_owes", "what", "status", "channel", "draft", "research")
    promises = [dict(zip(cols, r)) for r in c.execute(
        "select id,person,who_owes,what,status,channel,draft,research from event_agent.promises where event=%s order by id", (EVENT,)).fetchall()]
    events = [dict(zip(("id", "kind", "promise_id", "person", "text", "t"), r)) for r in c.execute(
        "select id,kind,promise_id,person,text,extract(epoch from ts) from event_agent.events where event=%s order by id desc limit 80", (EVENT,)).fetchall()][::-1]
    recap = c.execute("select note,extract(epoch from created_at) from event_agent.runs where kind='recap' order by id desc limit 1").fetchone()
    return {"phase": STATE["phase"], "started": STATE["started"], "source": STATE["source"], "error": STATE["error"], "place": STATE["place"], "output": __import__("notify").output(),
            "now": time.time(), "people": people, "promises": promises, "events": events,
            "recap": {"text": recap[0], "t": recap[1]} if recap else None}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ct="application/json", code=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, default=float)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Headers", "Content-Type, X-Token"),
                     ("Access-Control-Allow-Methods", "GET, POST, OPTIONS")):
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/health":
            return self.send(health())
        if p == "/api/state":
            return self.send(state())
        if p in ("/", "/agent"):
            return self.send((HERE / "ui" / "agent.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if p == "/listen":
            return self.send((HERE / "ui" / "listen.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if p.startswith("/deck"):
            rel = p[len("/deck"):].lstrip("/") or "index.html"
            f = (HERE / "deck" / rel).resolve()
            if HERE / "deck" in f.parents and f.is_file():
                ct = {".html": "text/html; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".js": "text/javascript", ".css": "text/css"}.get(f.suffix, "application/octet-stream")
                return self.send(f.read_bytes(), ct)
        self.send({"error": "not found"}, code=404)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/run":
            if STATE["phase"] not in ("idle", "done", "error"):
                return self.send({"ok": False, "why": "already running"}, code=409)
            pipeline.reset()
            threading.Thread(target=run_text, args=(sample_text(), "bee-replay", 0.12), daemon=True).start()
            return self.send({"ok": True})
        if p == "/api/ingest":
            tok = os.environ.get("INGEST_TOKEN")
            if tok and self.headers.get("X-Token") != tok:
                return self.send({"error": "bad token"}, code=401)
            b = self.body()
            text = (b.get("text") or "").strip()
            if len(text) < 20:
                return self.send({"error": "text too short"}, code=400)
            threading.Thread(target=run_text, args=(text, b.get("source", "api"), 0.0, place_of(b)), daemon=True).start()
            return self.send({"ok": True, "queued_chars": len(text)})
        if p == "/api/reset":
            pipeline.reset()
            STATE.update(phase="idle", started=None)
            return self.send({"ok": True})
        self.send({"error": "not found"}, code=404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8790"))
    print(f"event agent on http://localhost:{port}/agent")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
