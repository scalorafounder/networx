"""Settings for Networx. Everything comes from environment variables
(or a local .env file). Nothing is read from anywhere else."""
import os
from pathlib import Path

EVENT = os.environ.get("EVENT_NAME", "My event")


def _dotenv():
    p = Path(__file__).with_name(".env")
    if p.exists():
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_dotenv()


def env(key):
    v = os.environ.get(key)
    if not v:
        raise RuntimeError(f"Missing environment variable {key}. Set it in your shell or in .env (see .env.example).")
    return v


def db():
    import psycopg
    return psycopg.connect(env("DATABASE_URL"), autocommit=True)


def telegram(text):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
                      json={"chat_id": env("TELEGRAM_CHAT_ID"), "text": text}, timeout=20)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


def log(kind, text, promise_id=None, person=None, c=None):
    """One row in the live feed. The screen shows these as they happen."""
    c = c or db()
    c.execute("insert into event_agent.events(event,kind,promise_id,person,text) values(%s,%s,%s,%s,%s)",
              (EVENT, kind, promise_id, person, text))
