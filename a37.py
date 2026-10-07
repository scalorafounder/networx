"""Thin Agent37 client: hosting API + the box's own chat API."""
import requests
from common import env

API = "https://api.agent37.com/v1"


def _h():
    return {"Authorization": f"Bearer {env('AGENT37_API_KEY')}"}


def box():
    return env("AGENT37_INSTANCE")


def exec_(command, user=None):
    body = {"command": command}
    if user:
        body["user"] = user
    r = requests.post(f"{API}/instances/{box()}/exec", headers=_h(), json=body, timeout=800)
    r.raise_for_status()
    return r.json()


def upload(local, remote):
    import base64, os
    b = base64.b64encode(open(local, "rb").read()).decode()
    d = os.path.dirname(remote)
    return exec_(f"mkdir -p {d} && echo {b} | base64 -d > {remote}")


def ask(text, session_id=None, timeout=600):
    body = {"input": text, "stream": False}
    if session_id:
        body["session_id"] = session_id
    r = requests.post(f"https://{box()}.agent37.app/v1/responses",
                      headers={"X-Agent37-Key": env("AGENT37_API_KEY")}, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def crons():
    return requests.get(f"{API}/instances/{box()}/crons", headers=_h(), timeout=30).json()


def make_cron(name, prompt, schedule):
    r = requests.post(f"{API}/instances/{box()}/crons", headers=_h(), json={
        "name": name, "prompt": prompt, "schedule": schedule, "timezone": "America/Los_Angeles"}, timeout=30)
    r.raise_for_status()
    return r.json()


def run_cron(cron_id):
    r = requests.post(f"{API}/instances/{box()}/crons/{cron_id}/run", headers=_h(), timeout=60)
    r.raise_for_status()
    return r.json()
