# Plug Networx into your life

## The contract

- Input: text that was said, plus an optional place. Send it to `POST /api/ingest`.
- Output: drafts show on the screen by default, so the demo needs no messaging app. A messaging app (Telegram, WhatsApp, Slack or Discord) is optional.

Nothing is ever sent to the other person. You get a draft and you tap send.

## What you need (the barriers)

| You need | Where to get it | Cost | Time | Skill |
|---|---|---|---|---|
| Agent37 account and API key | agent37.com, then Dashboard, API keys | Paid credits. `setup.py` caps the box at 5 dollars of credit. Check their price page. | 5 min | No code |
| Supabase project (the database) | supabase.com, New project. The free plan allows 2 projects. Copy the connection string from Project settings, Database. No command line needed: open the SQL editor, paste `schema.sql`, press Run. | Free tier | 10 min | Copy and paste |
| A messaging app (optional). Easiest is Telegram. | In Telegram, message @BotFather, send `/newbot`, follow the steps, copy the token. Then message your new bot once. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy the number after `"chat":{"id":`. | Free | 5 min | Copy and paste |
| OpenAI key (optional) | platform.openai.com, API keys | Pay as you go, needs credit | 5 min | No code |
| A place to run `server.py` | Your laptop works. Any small server also works (1 GB is enough). Or use Docker. | Free on a laptop | 10 min | Copy and paste |
| A public address (only if your recorder is not on your own network) | A tunnel tool such as cloudflared or ngrok | Free tier | 10 min | Developer |

## Setup in three steps

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`. Fill in AGENT37_API_KEY, DATABASE_URL and your messaging app lines.
3. `python setup.py` then `python server.py`

`setup.py` is written from the Agent37 docs. It has not been run end to end yet. If a step fails, the message names what to fix. Run it again. It skips steps already done. To remove the box: `python setup.py --teardown`.

## Input recipes

### Plain curl (the base for everything else)

```
curl -X POST http://localhost:8790/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-Token: YOUR_INGEST_TOKEN" \
  -d '{"text":"Nice to meet you Sam. I will send you the deck tomorrow.","source":"curl","location":{"lat":37.77,"lng":-122.42,"label":"Corgi Cafe, SF"}}'
```

- `text` is needed and must be at least 20 characters.
- `location` is optional. `label` is a name people can read. If you only send lat and lng, the numbers are shown. You can also send `"place":"Corgi Cafe, SF"` instead.
- Leave out `X-Token` if you did not set INGEST_TOKEN.
- Check the server is alive: `curl http://localhost:8790/api/health` gives `{"ok":true,"box":true,"db":true}`.

### Bee

Tested with a real Bee transcript replayed through the whole pipeline. Live push from Bee is not wired up. Export or copy the transcript text and POST it as above with `"source":"bee"`.

### Plaud, Pocket

Not tested. Both let you export a transcript. Export the text, then POST it with the curl above.

### Omi

Not tested. Omi can call a webhook when it has a transcript. Point it at your public `/api/ingest`. Omi's body is shaped differently from ours, so you will likely need a small step in between (Zapier or Make, below) that turns it into `{"text": ..., "source": "omi"}`.

### Phone web page: `/listen`

Open `http://YOUR_ADDRESS:8790/listen` on your phone. Tap start and talk. It asks once for your location and sends it. It only works while the page is open and the screen is on. A phone browser pauses the page when you lock the phone. For all day recording you need a wearable or a native app. Phone browsers also only allow the microphone on https or localhost, so use a tunnel for a phone on your Wi-Fi.

### iPhone Shortcuts (not tested)

New shortcut, then:
1. "Dictate Text" (or "Ask for Input").
2. "Get Current Location".
3. "Get Contents of URL". URL: `https://YOUR_ADDRESS/api/ingest`. Method: POST. Request body: JSON. Fields: `text` = the dictated text, `source` = `iphone`, `place` = the location's name.
4. If you use a token, add a header `X-Token`.

### Android: HTTP Shortcuts app (not tested)

New shortcut, method POST, URL `https://YOUR_ADDRESS/api/ingest`, body type JSON:
`{"text":"{text}","source":"android","place":"{place}"}`. Make `text` and `place` ask-on-run variables. Tasker can do the same with its HTTP Request action.

### Zapier or Make (not tested)

Use a "Webhooks, send POST" step. URL: your `/api/ingest`. Body: JSON with `text` and `source`. Put it after any step that produces a transcript (an email from a recorder app, a Google Doc, a Drive file).

## Output recipes

Set `OUTPUT` in `.env`. You can use more than one: `OUTPUT=telegram,slack`.

| Platform | Set these | Status |
|---|---|---|
| Screen (default) | Nothing. Set `OUTPUT=screen` or leave it empty. Drafts show in the right pane and are saved in the database. | Works, nothing is sent |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Tested |
| WhatsApp | Twilio account with the WhatsApp sandbox. `TWILIO_SID`, `TWILIO_TOKEN`, `WHATSAPP_FROM`, `WHATSAPP_TO` | Written, not tested |
| Slack | Create an app, turn on Incoming Webhooks, add one to a channel. `SLACK_WEBHOOK_URL` | Written, not tested |
| Discord | Channel settings, Integrations, Webhooks, New webhook, copy URL. `DISCORD_WEBHOOK_URL` | Written, not tested |

## Share one setup with a teammate

Your teammate can use the same Agent37 box and database. In their own `.env` they need the same AGENT37_API_KEY, AGENT37_INSTANCE, CRON_ID and DATABASE_URL. Share them privately (a password manager or a direct message). Never put them in git. Then they run `python server.py`. They do not run `setup.py`.

The safe way to share the database is a separate role that can only read and write the `event_agent` schema. In the Supabase SQL editor, create a role, grant it usage on `event_agent` and select, insert, update and delete on its tables. Give your teammate that role's connection string, not your main password. Not tested here. Note that you both write to the same rows, so set a different EVENT_NAME each if you want separate demos.

## Troubleshooting

1. "Missing environment variable X". Put X in `.env` (same folder as `server.py`) and restart.
2. The database says the schema does not exist. Paste `schema.sql` into the Supabase SQL editor and run it, or run `python setup.py`.
3. Database connection fails. Use the connection string from Project settings, Database. Replace the password placeholder with your real password. If the password has odd characters, URL-encode them.
4. `/api/ingest` says 401. You set INGEST_TOKEN, so send the header `X-Token` with the same value.
5. Nothing arrives in your messaging app. Open `/api/health`. Then check the server window for errors. For Telegram, send your bot a message first. For Slack and Discord, check the webhook URL.
6. The agent says "failed" on a promise. Usually the Agent37 box has no credit left or the instance id is wrong. Check `AGENT37_INSTANCE`.
7. The `/listen` page cannot hear. Use Chrome on Android or Safari on iPhone, allow the microphone, and use https or localhost.

## What is tested and what is not

Tested: Bee transcript replay, the Agent37 box, Supabase, Telegram.

Not tested: `setup.py`, `/api/health`, location input, WhatsApp, Slack, Discord, Docker, Plaud, Pocket, Omi, iPhone Shortcuts, Android, Zapier and Make. The `/listen` page cannot work in the background.
