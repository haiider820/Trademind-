from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TradeMind API"
    app_env: str = "development"
    app_version: str = "0.1.0"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    binance_base_url: str = "https://api.binance.com"
    gemini_api_key: str = ""
    newsapi_api_key: str = ""
    finnhub_api_key: str = ""
    news_use_gemini_sentiment: bool = True
    firebase_project_id: str = ""
    firebase_service_account_path: str = ""

    # PHASE 1 PROVISIONAL VALUE: replace after confirming TradeMind's live interval.
    # The offline data pipeline reads this setting; it is not hardcoded in ML code.
    trading_candle_interval: str = "15m"

    # PHASE 1 PROVISIONAL VALUE: confirm that live execution is spot-only before production use.
    trading_market_mode: str = "spot"

    # Phase 1 long-only label: future close return must exceed the greater of this
    # ATR(14) multiple and the round-trip transaction-cost floor.
    ml_entry_atr_multiple: float = 1.25
    ml_round_trip_cost_floor: float = 0.003
    ml_label_horizons_bars: str = "4,8,16"
    ml_holdout_fraction: float = 0.20

    # Phase 2 sequence benchmark.  GRU is intentionally small for an offline CPU baseline.
    # The 4-bar target is the Phase 1 stability-selected horizon; no live integration is implied.
    ml_sequence_window_bars: int = 32
    ml_sequence_training_stride: int = 4
    ml_neural_hidden_size: int = 24
    ml_neural_batch_size: int = 1024
    ml_neural_epochs: int = 8
    ml_neural_learning_rate: float = 0.001
    ml_neural_inner_validation_fraction: float = 0.10

    # Phase 3 offline self-learning simulation.  These values do not schedule or deploy anything.
    # Candidates train only on outcomes resolved before their evaluation chunk.
    ml_retraining_chunk_count: int = 3
    ml_retraining_neural_epochs: int = 3
    # Every resolved decision outcome is retained; older baseline rows are evenly time-spaced
    # to keep per-chunk Random Forest retraining within the available CPU-memory budget.
    ml_retraining_tree_base_row_cap: int = 50000
    # Retraining candidates use a smaller forest and bootstrap fraction than the fixed Phase 1
    # incumbent, explicitly recorded in their artifact metadata for fair audit interpretation.
    ml_retraining_tree_n_estimators: int = 48
    ml_retraining_tree_max_samples: float = 0.35
    ml_promotion_min_average_precision_gain: float = 0.001
    ml_promotion_min_signal_count: int = 100

    # Phase 4 in-process serving. The bundle path is relative to backend/ and is replaced only
    # by a validated workflow commit; loading remains local to the FastAPI process.
    ml_model_bundle_path: str = "models/current/model_bundle.json"
    ml_serving_horizon_bars: int = 4
    ml_serving_require_audit: bool = True

    # Prediction route security. The service token is server-only and must be provisioned
    # in the runtime secret store; it is intentionally blank in source control.
    prediction_service_token: str = ""
    prediction_rate_limit_window_seconds: int = 60
    prediction_rate_limit_max_requests: int = 120
    prediction_max_body_bytes: int = 65536
    prediction_timeout_seconds: float = 8.0

    # Browser CORS is disabled outside local development. These explicit origins are only
    # useful for a local browser build and are never enabled by production app environments.
    cors_local_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    # Public Kaggle source approved for Phase 1 historical OHLCV acquisition.
    ml_kaggle_dataset: str = "andreidiaconescu/binancepricedata"
    ml_kaggle_dataset_version: int = 3
    ml_training_symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
