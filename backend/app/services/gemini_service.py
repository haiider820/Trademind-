from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.config import settings

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_api_key() -> str:
    return (
        settings.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()


class GeminiService:
    def __init__(self) -> None:
        self.api_key = _gemini_api_key()
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._client.aclose()

    def _build_prompt(self, user_text: str, context: str | None = None) -> str:
        parts = [
            "You are TradeMind AI, a practical crypto and forex trading assistant.",
            "Keep answers concise, actionable, and focused on risk management.",
            "Never promise profits or guarantees.",
        ]
        if context:
            parts.append(f"Context: {context}")
        parts.append(f"User question: {user_text}")
        return "\n".join(parts)

    @staticmethod
    def _normalize_history(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not history:
            return []

        normalized: list[dict[str, Any]] = []
        last_role: str | None = None
        for message in history:
            role = str(message.get("role", "user")).lower()
            if role in {"assistant", "model"}:
                role = "model"
            else:
                role = "user"

            content = message.get("content") or message.get("text") or ""
            if not content:
                continue
            if not normalized and role == "model":
                continue
            if last_role == role:
                continue
            normalized.append({"role": role, "parts": [{"text": str(content)}]})
            last_role = role
        return normalized

    async def _request_generate_content(
        self,
        model: str,
        *,
        prompt: str,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key is missing")

        payload: dict[str, Any] = {
            "contents": self._normalize_history(history) + [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 700,
            },
        }

        response = await self._client.post(
            f"{GEMINI_BASE_URL}/{model}:generateContent",
            params={"key": self.api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
            reply = "".join(texts).strip()
            if reply:
                return reply
        raise RuntimeError("Gemini returned an empty response")

    async def generate_reply(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        prompt = self._build_prompt(user_text, context)
        errors: list[str] = []
        for model in GEMINI_MODELS:
            try:
                return await self._request_generate_content(model, prompt=prompt, history=history)
            except Exception as exc:
                errors.append(f"{model}: {exc}")
        raise RuntimeError("Gemini request failed. " + " | ".join(errors))

    async def chat(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)

    async def analyze_market(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)

    async def generate_chat_reply(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)

    async def generate_analysis(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)

    async def generate_response(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)

    async def reply(
        self,
        user_text: str,
        *,
        history: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        return await self.generate_reply(user_text, history=history, context=context)
