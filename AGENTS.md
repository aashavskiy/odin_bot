# Odin Bot Deploy Notes

## Context Summary (2026-02-01, update)
- Cloud Run deploy pipeline fixed and working; last successful deploy from GitHub Actions.
- Service URL: `https://odin-bot-j3hrwb34la-uc.a.run.app`
- Bot token verified via `getMe`: `@AAshavskiyOdinBot` (id `7858967289`).

## Context Summary (2026-02-02, reminders update)
- Added natural-language reminders (no commands required).
- Delivery uses Cloud Tasks + Firestore + Cloud Scheduler sweep (no missed reminders; late delivery allowed).
- Cloud Tasks API enabled; queue `reminders` in `us-central1`.
- Cloud Scheduler job `reminders-sweep` runs every minute.
- Tasks endpoints protected with `X-Tasks-Token` (env `TASKS_TOKEN`).
- When user text doesn't match expected reminder input (e.g., timezone), fall back to LLM first before asking again.

## Current Issue
- Telegram webhook keeps getting cleared (`getWebhookInfo` shows `url: ""`).
- This is **not** due to the app itself; code only calls `delete_webhook` on shutdown.
- Something outside this repo is likely calling `deleteWebhook` or running polling mode with the same token.
  - User asked to avoid touching other apps; still unresolved.
  - Deploys can fail if Telegram rate-limits `setWebhook` during startup; now handled gracefully.

## What Was Changed in Repo
- Added fallback for OpenAI Responses API:
  - If `responses` is missing, use `chat.completions`.
  - Added error logging + fallback reply on OpenAI failure.
  - Files: `app/services/openai_client.py`, `app/handlers.py`
- Added in-memory storage when Firestore is disabled:
  - `FIRESTORE_DISABLED=1` env in workflow.
  - Files: `app/services/memory_store.py`, `app/main.py`, `app/config.py`
- Added logging for access decision:
  - `app/handlers.py` logs `message_received ... will_respond=...`
- Webhook set on startup with `drop_pending_updates=True`:
  - `app/main.py`
- Added summary-based memory + TTL:
  - Last 16 messages + summary, TTL 7 days.
  - Files: `app/services/openai_client.py`, `app/services/memory_store.py`,
    `app/services/firestore_client.py`, `app/handlers.py`, `app/config.py`
- Workflow hardened and set to use vars/secrets:
  - `.github/workflows/deploy.yml`
- Pinned `httpx==0.27.2` for OpenAI client compatibility:
  - `requirements.txt`
- Removed webhook deletion on shutdown:
  - `app/main.py` (later commit)
- Added OpenAI error fallback reply to user:
  - `app/handlers.py`
- Added reminder system:
  - NL reminder parsing via OpenAI (confidence threshold 0.7).
  - Firestore collections: `users`, `pending_reminders`, `reminders`.
  - Cloud Tasks endpoints: `/tasks/remind`, `/tasks/sweep`.
  - Files: `app/handlers.py`, `app/reminders.py`, `app/tasks.py`,
    `app/services/firestore_client.py`, `app/services/openai_client.py`,
    `app/main.py`, `.github/workflows/deploy.yml`.
- Added LLM-based timezone resolution fallback:
  - If awaiting timezone and local parsing fails, call OpenAI to resolve IANA TZ.
  - Files: `app/handlers.py`, `app/services/openai_client.py`.
- Added LLM timezone inference for initial reminder requests when no saved TZ:
  - If reminder text includes a location, resolve TZ before prompting the user.
  - File: `app/handlers.py`.
- Added fast-response guardrails:
  - Local arithmetic responses to bypass OpenAI latency.
  - Fast model response truncation + stop sequence.

## External Actions Taken
- Enabled Cloud Resource Manager API and Firestore API in project `odin-gatekeeper`.
- Firestore database created (Native) in `us-central1`.
- Service account granted `roles/datastore.user`.
- Webhook was repeatedly re-set manually via Telegram API.
- Enabled Cloud Tasks API and Cloud Scheduler API.
- Created Cloud Tasks queue `reminders` in `us-central1`.
- Created Cloud Scheduler job `reminders-sweep` (every minute).
- Set Cloud Run env: `TASKS_LOCATION`, `TASKS_QUEUE`, `TASKS_BASE`, `TASKS_TOKEN`.

## Known Good Env Vars (Cloud Run)
- `BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`, `GCP_PROJECT_ID`, `WEBHOOK_BASE`, `WEBHOOK_PATH`
- `HISTORY_MAX_MESSAGES=16`, `SUMMARY_TRIGGER=20`, `HISTORY_TTL_DAYS=7`
- `FIRESTORE_DISABLED=0` (now enabled)
- Reminders:
  - `TASKS_LOCATION=us-central1`, `TASKS_QUEUE=reminders`, `TASKS_BASE=https://odin-bot-j3hrwb34la-uc.a.run.app`
  - `TASKS_TOKEN` (secret), `REMINDER_CONFIDENCE_THRESHOLD=0.7`

## Recent Deploy Failure and Fix
- Deploy failed due to syntax error in `app/services/memory_store.py` (extra `]`).
- Fixed in commit `df37830` and pushed; new deploy should be running after this fix.

## What To Check Next
1) Identify external process clearing webhook:
   - Any local script using polling mode?
   - Another deployment with same token?
2) Verify latest deploy after `df37830` succeeds and bot responds.
3) Configure Firestore TTL policies in console:
   - collection group `messages`, field `expires_at`
   - collection group `summaries`, field `expires_at`

## Useful Commands
```bash
curl -s "https://api.telegram.org/bot<token>/getWebhookInfo"
curl -s -X POST "https://api.telegram.org/bot<token>/setWebhook" -d "url=https://odin-bot-j3hrwb34la-uc.a.run.app/webhook"

gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"odin-bot\" AND httpRequest.requestUrl:\"/webhook\"" \
  --project odin-gatekeeper --limit 20 --format="table(timestamp, httpRequest.status)"

# Reminders infra
gcloud tasks queues describe reminders --project odin-gatekeeper --location us-central1
gcloud scheduler jobs describe reminders-sweep --project odin-gatekeeper --location us-central1
```
