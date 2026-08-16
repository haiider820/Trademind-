from typing import Literal

from pydantic import BaseModel, Field


class AIAnalyzeRequest(BaseModel):
    symbol: str
    market: Literal["crypto", "forex"]
    timeframe: str
    question: str


class AIAnalyzeResponse(BaseModel):
    summary: str
    confidence: float
    indicators: dict[str, str]


class AIChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    message: str
    market: Literal["crypto", "forex"] = "crypto"
    symbol: str | None = None
    timeframe: str | None = None
    context: str | None = None
    history: list[AIChatMessage] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    confidence: float
    market_bias: Literal["bullish", "bearish", "neutral", "mixed"]
    risk_notes: list[str]
    suggested_action: str
