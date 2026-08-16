from datetime import datetime

from pydantic import BaseModel


class MarketOverview(BaseModel):
    btc_price: float
    eth_price: float
    market_cap: float
    fear_greed_index: int
    btc_dominance: float
    updated_at: datetime
