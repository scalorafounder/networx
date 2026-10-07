"""Output. Pick where the agent talks to you with OUTPUT (a comma list is fine, for example OUTPUT=telegram,slack).

  telegram  needs TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID      TESTED
  whatsapp  needs TWILIO_SID, TWILIO_TOKEN, WHATSAPP_FROM, WHATSAPP_TO   written, NOT tested live
  slack     needs SLACK_WEBHOOK_URL (incoming webhook)       written, NOT tested live
  screen    needs nothing. Drafts stay on the screen and in the database. This is the default when no messaging vars are set.
  discord   needs DISCORD_WEBHOOK_URL (channel webhook)      written, NOT tested live
"""
import os
import requests
from common import env, telegram


def whatsapp(text):
    sid, tok = env("TWILIO_SID"), env("TWILIO_TOKEN")
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, tok),
                      data={"From": "whatsapp:" + env("WHATSAPP_FROM"), "To": "whatsapp:" + env("WHATSAPP_TO"), "Body": text[:1500]}, timeout=20)
    r.raise_for_status()
    return r.json()["sid"]


def slack(text):
    r = requests.post(env("SLACK_WEBHOOK_URL"), json={"text": text}, timeout=20)
    r.raise_for_status()
    return "slack"


def discord(text):
    r = requests.post(env("DISCORD_WEBHOOK_URL"), json={"content": text[:1900]}, timeout=20)
    r.raise_for_status()
    return "discord"


def screen(text):
    return "screen"


def output():
    """The chosen output, or the detected default: screen unless a messaging app is set up."""
    o = os.environ.get("OUTPUT", "").strip().lower()
    if o:
        return o
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        return "telegram"
    if os.environ.get("SLACK_WEBHOOK_URL"):
        return "slack"
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        return "discord"
    if os.environ.get("TWILIO_SID"):
        return "whatsapp"
    return "screen"


CHANNELS = {"screen": screen, "telegram": telegram, "whatsapp": whatsapp, "slack": slack, "discord": discord}


def send(text):
    names = [n.strip() for n in output().split(",") if n.strip()]
    for n in names:
        if n not in CHANNELS:
            raise RuntimeError(f"OUTPUT has '{n}'. Use one or more of: {', '.join(CHANNELS)}")
    result, errors = None, []
    for n in names:
        try:
            r = CHANNELS[n](text)
            result = result or r
        except Exception as e:
            errors.append(f"{n}: {e}")
    if errors and result is None:
        raise RuntimeError("; ".join(errors))
    return result
