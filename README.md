# TradeMind AI

Flutter + FastAPI trading assistant app scaffold.

## Project Docs

- [MVP Build Plan](docs/MVP_BUILD_PLAN.md)
- [API Contracts](docs/API_CONTRACTS.md)
- [Required Keys and Setup](docs/REQUIRED_KEYS_AND_SETUP.md)
- [Backend Guide](backend/README.md)

## Run Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Run Flutter

```bash
flutter pub get
flutter run
```

If you are using a separate backend host, override `API_BASE_URL` with `--dart-define`.
