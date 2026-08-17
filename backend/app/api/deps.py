from __future__ import annotations

from dataclasses import dataclass
import hmac

import httpx
from fastapi import Depends, Header, HTTPException

from app.core.config import settings
from app.services.supabase_service import SupabaseService


@dataclass
class AuthUser:
    id: str
    email: str | None
    token: str


def _extract_bearer_token(value: str | None) -> str:
    if not value or not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return value.split(" ", 1)[1].strip()


async def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _extract_bearer_token(authorization)
    service = SupabaseService()
    try:
        payload = await service.get_user_from_jwt(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return AuthUser(id=payload["id"], email=payload.get("email"), token=token)


async def get_prediction_service_caller(
    authorization: str | None = Header(default=None),
) -> AuthUser:
    """Authenticate the internal prediction caller without accepting user JWTs."""
    if not settings.prediction_service_token:
        raise HTTPException(status_code=503, detail="Prediction service temporarily unavailable")

    try:
        token = _extract_bearer_token(authorization)
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication") from exc

    if not hmac.compare_digest(token, settings.prediction_service_token):
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Never place the actual service credential in the request context or logs.
    return AuthUser(id="prediction-service", email=None, token="")


async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    service = SupabaseService()
    role = await service.get_profile_role(user.id)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
