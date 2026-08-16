from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SignalStatus = Literal["open", "tp_hit", "sl_hit", "closed"]
TradeType = Literal["long", "short"]
RiskLevel = Literal["low", "medium", "high"]


class SignalCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pair: str
    trade_type: TradeType = Field(alias="tradeType")
    entry: float
    sl: float
    tp: float
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    risk_level: RiskLevel = Field(alias="riskLevel")


class SignalUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    status: SignalStatus | None = None
    pnl: float | None = None
    realized_pnl: float | None = None
    tp1_hit: bool | None = None


class SignalOut(BaseModel):
    id: str
    pair: str
    trade_type: TradeType
    entry: float
    sl: float
    tp: float
    status: SignalStatus
    pnl: float
    risk_level: RiskLevel
    created_at: datetime
