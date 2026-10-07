"""One command setup.   python setup.py        (or: python setup.py --teardown)

Reads env vars (or .env). Does these steps, and skips what is already done:
  a) puts the tables in your database (schema.sql)
  b) creates your Agent37 box
  c) installs the packages on the box, copies the files, writes the box .env
  d) creates the 30 minute recap timer
  e) saves AGENT37_INSTANCE and CRON_ID into your local .env
Status: written from the Agent37 docs, NOT yet tested end to end.
"""
import base64, os, sys
from pathlib import Path
import requests
import common                       # loads .env
from common import env

API = "https://api.agent37.com/v1"
HERE = Path(__file__).parent
ENVF = HERE / ".env"
REMOTE = "/home/node/event-agent"
FILES = ["common.py", "recap.py", "notify.py"]
PASS = ["DATABASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OUTPUT", "TWILIO_SID", "TWILIO_TOKEN",
        "WHATSAPP_FROM", "WHATSAPP_TO", "SLACK_WEBHOOK_URL", "DISCORD_WEBHOOK_URL", "EVENT_NAME"]
NEED = {"telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "whatsapp": ["TWILIO_SID", "TWILIO_TOKEN", "WHATSAPP_FROM", "WHATSAPP_TO"],
        "slack": ["SLACK_WEBHOOK_URL"], "discord": ["DISCORD_WEBHOOK_URL"]}


def say(s):
    print(s, flush=True)


def hdr():
    return {"Authorization": f"Bearer {env('AGENT37_API_KEY')}"}


def save_env(k, v):
    lines = ENVF.read_text().splitlines() if ENVF.exists() else []
    lines = [l for l in lines if not l.startswith(k + "=")] + [f"{k}={v}"]
    ENVF.write_text("\n".join(lines) + "\n")
    os.environ[k] = v


def exec_(box, cmd):
    r = requests.post(f"{API}/instances/{box}/exec", headers=hdr(), json={"command": cmd}, timeout=800)
    r.raise_for_status()
    return r.json()


def upload(box, local, remote):
    b = base64.b64encode(Path(local).read_bytes()).decode()
    return exec_(box, f"mkdir -p {os.path.dirname(remote)} && echo {b} | base64 -d > {remote}")


def teardown():
    box = os.environ.get("AGENT37_INSTANCE")
    if not box:
        sys.exit("AGENT37_INSTANCE is not set, so there is no box to delete.")
    r = requests.delete(f"{API}/instances/{box}", headers=hdr(), timeout=60)
    r.raise_for_status()
    for k in ("AGENT37_INSTANCE", "CRON_ID"):
        if ENVF.exists():
            ENVF.write_text("\n".join(l for l in ENVF.read_text().splitlines() if not l.startswith(k + "=")) + "\n")
    say(f"Deleted box {box}. Your database is untouched.")


def main():
    env("AGENT37_API_KEY"); env("DATABASE_URL")
    outs = [o.strip().lower() for o in os.environ.get("OUTPUT", "telegram").split(",") if o.strip()]
    for o in outs:
        if o not in NEED:
            sys.exit(f"OUTPUT has '{o}'. Use one or more of: {', '.join(NEED)}")
        for k in NEED[o]:
            env(k)                  # stops with a clear message if missing
    say("a) Putting the tables in your database...")
    with common.db() as c:
        c.execute((HERE / "schema.sql").read_text())
    say("   done.")

    box = os.environ.get("AGENT37_INSTANCE")
    if box:
        say(f"b) Box already set ({box}). Skipping create.")
    else:
        say("b) Creating your Agent37 box (takes a minute)...")
        body = {"name": "networx", "template": "agent37-hermes", "budget": {"credit_micros": 5000000},
                "env": {k: os.environ[k] for k in PASS if os.environ.get(k)}}
        r = requests.post(f"{API}/instances", headers=hdr(), json=body, timeout=300)
        if not r.ok:
            sys.exit(f"Agent37 said no ({r.status_code}): {r.text[:300]}")
        j = r.json()
        box = j.get("id") or j.get("instance_id") or (j.get("instance") or {}).get("id")
        if not box:
            sys.exit(f"Box was created but I could not find its id in: {str(j)[:300]}")
        save_env("AGENT37_INSTANCE", box)
        say(f"   box {box}")

    say("c) Installing packages and copying files to the box...")
    exec_(box, "python3 -m venv /home/node/.venv 2>/dev/null; /home/node/.venv/bin/pip install -q 'psycopg[binary]' requests")
    for f in FILES:
        upload(box, HERE / f, f"{REMOTE}/{f}")
    keys = " ".join(f"-e ^{k}=" for k in PASS)
    exec_(box, f"mkdir -p {REMOTE} && env | grep {keys} > {REMOTE}/.env; true")
    say("   done.")

    if os.environ.get("CRON_ID"):
        say("d) Recap timer already set. Skipping.")
    else:
        say("d) Creating the 30 minute recap timer...")
        prompt = (f"Run `cd {REMOTE} && /home/node/.venv/bin/python3 recap.py` and report the output in one line.")
        r = requests.post(f"{API}/instances/{box}/crons", headers=hdr(), json={
            "name": "networx-recap", "prompt": prompt, "schedule": "*/30 * * * *", "timezone": os.environ.get("TZ_NAME", "America/Los_Angeles")}, timeout=60)
        if not r.ok:
            sys.exit(f"Could not create the timer ({r.status_code}): {r.text[:300]}")
        j = r.json()
        cid = j.get("id") or j.get("cron_id") or (j.get("cron") or {}).get("id")
        if cid:
            save_env("CRON_ID", str(cid))
    say("e) Saved AGENT37_INSTANCE and CRON_ID in .env.")
    say("\nNext steps:\n  1. python server.py\n  2. Open http://localhost:8790/agent\n  3. Press Replay sample, or POST text to /api/ingest (see docs/INTEGRATE.md)\n"
        "  To remove the box later: python setup.py --teardown")


if __name__ == "__main__":
    teardown() if "--teardown" in sys.argv else main()
