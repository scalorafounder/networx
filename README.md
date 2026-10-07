# Networx

Networx listens to your event conversations and catches the promises you and others make.
An Agent37 cloud box researches each one and writes a follow-up draft.
Drafts are saved to Supabase and sent to your phone on Telegram. Nothing is ever sent to the other person.

## Quickstart (3 steps)

Full guide with every account you need, cost and time: [docs/INTEGRATE.md](docs/INTEGRATE.md).

1. `git clone https://github.com/scalorafounder/networx`, then `cd networx`, then `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in the keys (the file explains each one).
3. `python setup.py` (makes the tables, the Agent37 box and the recap timer), then `python server.py`

Open http://localhost:8790/agent. Press "Replay sample" to run `sample/charlie.txt`. It is a scripted, made-up chat between you and a fictional founder named Priya. Nobody real is in it.

There is also a short deck at http://localhost:8790/deck/ . Press R on the deck to run the demo.

Input: text plus an optional place, sent to `POST /api/ingest`. Output: Telegram, WhatsApp, Slack or Discord. Docker files are included but untested.

## What you need (env vars)

| Name | Needed | What it is |
|---|---|---|
| AGENT37_API_KEY | yes | Your Agent37 API key |
| AGENT37_INSTANCE | yes | The id of your Agent37 box (see below) |
| DATABASE_URL | yes | Postgres link from Supabase |
| TELEGRAM_BOT_TOKEN | yes | Token from @BotFather |
| TELEGRAM_CHAT_ID | yes | Your chat id (message your bot, then check getUpdates) |
| OPENAI_API_KEY | no | If set, OpenAI reads the transcript. If not set, the Agent37 box does it. |
| CONTEXT | no | A few lines about you, so the agent knows who is who. You can also put them in `context.txt`. |
| CRON_ID | no | Id of an Agent37 timer that sends a recap. If empty, the recap step is skipped. |
| EVENT_NAME | no | Label for this event |
| INGEST_TOKEN | no | If set, `/api/ingest` needs header `X-Token` |
| OUTPUT | no | `telegram` (default), `whatsapp`, `slack`, `discord`, or a comma list |
| SLACK_WEBHOOK_URL, DISCORD_WEBHOOK_URL | only for those | Webhook links |
| TWILIO_SID, TWILIO_TOKEN, WHATSAPP_FROM, WHATSAPP_TO | only for WhatsApp | Twilio details |

The code reads environment variables and a local `.env` file. Nothing else.

## Set up the pieces

Create the Agent37 box:

```
curl -X POST https://api.agent37.com/v1/instances \
  -H "Authorization: Bearer $AGENT37_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template": "agent37-hermes"}'
```

Put the id it gives you in `AGENT37_INSTANCE`.

Create the tables: open the Supabase SQL editor, paste `schema.sql`, run it.

## How it works

1. Listen. Text comes in.
2. Catch. `catch.py` finds the people and the promises.
3. Remember. They are saved in Supabase (status: open, doing, ready, needs_you).
4. Do. `do.py` sends each promise to the Agent37 box. It researches and writes a draft.
5. Tell. The draft goes to your phone. `recap.py` sends a summary later.

## Integrations

### Input: anything that can POST a transcript

```
curl -X POST http://localhost:8790/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-Token: YOUR_INGEST_TOKEN" \
  -d '{"text": "Nice to meet you Sam. I will send you the deck tomorrow and we should grab coffee next week.", "source": "manual"}'
```

Text must be at least 20 characters. Leave out the X-Token header if you did not set INGEST_TOKEN. If your server is not public, use a tunnel so the device can reach it.

Recipes. Be honest with yourself: only Bee is tested.

- Bee: tested. We replayed a real Bee transcript through the full pipeline. Live push from Bee is not wired. Export or copy the transcript and POST it.
- Plaud: untested. Plaud exports transcripts. Export the text, then POST it with the curl above (`"source": "plaud"`).
- Pocket: untested. Same idea. Export the text, then POST it.
- Omi: untested. Omi can send transcripts to a webhook URL. Point its webhook at your public `/api/ingest`. The body shape may differ from ours, so you may need a small adapter that turns it into `{"text", "source"}`.

Phone web page: open `/listen` on your phone. You talk, it sends the transcript to the server. It only works while the page stays open and the screen stays on. Background recording needs a native app or a wearable.

### Output

- Telegram: works. Tested.
- WhatsApp through Twilio: set `OUTPUT=whatsapp` and the four Twilio vars. The adapter is written in `notify.py` but has not been tested live.

## What is tested

Tested: Bee transcript replay, the Agent37 box, Supabase, Telegram.
Not tested: Plaud, Pocket, Omi, WhatsApp, the `/listen` page in the background, running without an OpenAI key at scale.

## License

MIT
