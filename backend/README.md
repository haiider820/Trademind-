# TradeMind Backend (FastAPI)

## Run locally

1. Create virtualenv and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy env file:

```bash
cp .env.example .env
```

3. Start API:

```bash
uvicorn app.main:app --reload --port 8000
```

4. Open docs:
- `http://localhost:8000/docs`

## Database migrations

Run in Supabase SQL editor:

1. [001_initial_schema.sql](D:/My Projects/crypto/backend/sql/001_initial_schema.sql)
2. [002_runtime_updates.sql](D:/My Projects/crypto/backend/sql/002_runtime_updates.sql) for device tokens, profile trigger, and news external ID.

## Folder layout

- `app/api/v1/endpoints` route handlers
- `app/schemas` request/response schemas
- `app/core` settings and shared config
- `sql` initial Supabase schema

## News pipeline

- Free RSS aggregation from CoinDesk, Cointelegraph, Decrypt, Binance, and Reuters.
- Sentiment from headline heuristics, with optional Gemini refinement when `GEMINI_API_KEY` is configured.

## Notifications

- Backend uses Firebase Admin SDK (FCM v1).
- Set `FIREBASE_SERVICE_ACCOUNT_PATH` to your service-account JSON path and `FIREBASE_PROJECT_ID`.
