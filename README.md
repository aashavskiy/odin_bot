# Odin Telegram Bot (aiogram 3 + OpenAI + Firestore)

Production-ready Telegram bot for a single administrator user.

## Features
- **Strict access control**: only configured admin ID receives responses.
- **Group safety**: bot auto-leaves groups added by anyone else via `on_my_chat_member`.
- **Group interaction rules**: admin must @mention or reply to the bot in groups.
- **Conversation memory**: history stored in Firestore (or in-memory when disabled), with TTL-ready `expires_at`.
- **History compaction**: keeps last N messages plus a rolling summary.
- **Cloud Run ready**: webhook server on port `8080`.
## Notes
- Reminder support has been removed as of 2026-02-03.

## Architecture
- `app/main.py` starts an aiohttp webhook server for aiogram.
- `app/handlers.py` routes messages and membership updates.
- `app/access.py` centralizes access-control logic.
- `app/services/firestore_client.py` stores conversation history.
- `app/services/openai_client.py` wraps OpenAI Responses API.

## Environment Variables
Required:
- `BOT_TOKEN`
- `OPENAI_API_KEY`
- `ADMIN_ID`

Required when Firestore is enabled:
- `GCP_PROJECT_ID`

Optional (webhook + history tuning):
- `WEBHOOK_BASE` (e.g., `https://your-service-xyz.a.run.app`)
- `WEBHOOK_PATH` (default: `/webhook`)
- `FIRESTORE_DISABLED` (set to `1`/`true`/`yes` to use in-memory storage)
- `HISTORY_MAX_MESSAGES` (default: `16`)
- `SUMMARY_TRIGGER` (default: `20`)
- `HISTORY_TTL_DAYS` (default: `7`)

Example `.env`:
```bash
BOT_TOKEN=
OPENAI_API_KEY=
ADMIN_ID=
GCP_PROJECT_ID=
WEBHOOK_BASE=
WEBHOOK_PATH=/webhook
FIRESTORE_DISABLED=0
HISTORY_MAX_MESSAGES=16
SUMMARY_TRIGGER=20
HISTORY_TTL_DAYS=7
```

## Local Development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
export BOT_TOKEN=... \
  OPENAI_API_KEY=... \
  ADMIN_ID=... \
  GCP_PROJECT_ID=... \
  WEBHOOK_BASE=https://your-ngrok-url
python -m app.main
```

Note: The bot runs only in webhook mode. If `WEBHOOK_BASE` is not set, you must set the webhook externally.

## Firestore Setup (2026)
1. In **Google Cloud Console**, create or select a project.
2. Enable **Firestore** and choose **Native mode**.
3. Create a **TTL policy** on the `expires_at` field:
   - Navigate to **Firestore > TTL**.
   - Add a policy for collection group `messages` and field `expires_at`.
   - Add a policy for collection group `summaries` and field `expires_at`.
4. Ensure Cloud Run service account has `roles/datastore.user`.

## OpenAI Setup
1. Create an API key in OpenAI.
2. Store it in `OPENAI_API_KEY`.
3. The bot uses model `gpt-5.2` via the Responses API.

## GitHub Actions Deployment
This repo includes `.github/workflows/deploy.yml` to deploy on every push to `main`.

### Required GitHub Secrets
- `GCP_SA_KEY`: service account JSON with Cloud Run + Cloud Build permissions.
- `GCP_PROJECT_ID`: GCP project ID.
- `GCP_REGION`: e.g. `us-central1` (make sure it's a valid GCP region).
- `BOT_TOKEN`: Telegram bot token.
- `OPENAI_API_KEY`: OpenAI API key.
- `ADMIN_ID`: Telegram admin user id.
- `WEBHOOK_BASE`: Cloud Run URL (after first deploy, optional if you set webhook manually).

### First deploy + webhook
1. First push to `main` triggers deploy (without `WEBHOOK_BASE`).
2. Copy the Cloud Run service URL.
3. Set `WEBHOOK_BASE` to that URL in GitHub Secrets.
4. Re-run the workflow or push again to apply the webhook.

## Testing
```bash
pytest
```

Tests use `pytest-asyncio` and mocks for:
- Telegram API calls
- OpenAI API responses
- Access control rules
- Memory store compaction/TTL

## Cloud Run Deployment (Manual)
```bash
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/odin-bot

gcloud run deploy odin-bot \
  --image gcr.io/$GCP_PROJECT_ID/odin-bot \
  --region $GCP_REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars BOT_TOKEN=$BOT_TOKEN,OPENAI_API_KEY=$OPENAI_API_KEY,GCP_PROJECT_ID=$GCP_PROJECT_ID,ADMIN_ID=$ADMIN_ID,WEBHOOK_BASE=$WEBHOOK_BASE,WEBHOOK_PATH=/webhook,FIRESTORE_DISABLED=$FIRESTORE_DISABLED,HISTORY_MAX_MESSAGES=$HISTORY_MAX_MESSAGES,SUMMARY_TRIGGER=$SUMMARY_TRIGGER,HISTORY_TTL_DAYS=$HISTORY_TTL_DAYS
```
