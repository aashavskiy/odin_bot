# Odin Bot Deploy Notes

## Context Summary (2026-02-01)
- Cloud Run deploy pipeline fixed and working; last successful deploy from GitHub Actions.
- Service URL: `https://odin-bot-j3hrwb34la-uc.a.run.app`
- Bot token verified via `getMe`: `@AAshavskiyOdinBot` (id `7858967289`).

## Current Issue
- Telegram webhook keeps getting cleared (`getWebhookInfo` shows `url: ""`).
- This is **not** due to the app itself; code only calls `delete_webhook` on shutdown.
- Something outside this repo is likely calling `deleteWebhook` or running polling mode with the same token.

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
- Workflow hardened and set to use vars/secrets:
  - `.github/workflows/deploy.yml`
- Pinned `httpx==0.27.2` for OpenAI client compatibility:
  - `requirements.txt`

## External Actions Taken
- Enabled Cloud Resource Manager API and Firestore API in project `odin-gatekeeper`.
- Firestore database NOT created (user declined).
- Webhook was repeatedly re-set manually via Telegram API.

## Known Good Env Vars (Cloud Run)
- `BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`, `GCP_PROJECT_ID`, `WEBHOOK_BASE`, `WEBHOOK_PATH`
- `FIRESTORE_DISABLED=1`

## What To Check Next
1) Identify external process clearing webhook:
   - Any local script using polling mode?
   - Another deployment with same token?
2) Consider removing `delete_webhook` on shutdown if you want to avoid the app clearing it at stop time.

## Useful Commands
```bash
curl -s "https://api.telegram.org/bot<token>/getWebhookInfo"
curl -s -X POST "https://api.telegram.org/bot<token>/setWebhook" -d "url=https://odin-bot-j3hrwb34la-uc.a.run.app/webhook"

gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"odin-bot\" AND httpRequest.requestUrl:\"/webhook\"" \
  --project odin-gatekeeper --limit 20 --format="table(timestamp, httpRequest.status)"
```
