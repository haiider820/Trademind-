from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException

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


async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    service = SupabaseService()
    role = await service.get_profile_role(user.id)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
