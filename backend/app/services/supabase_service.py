from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class SupabaseService:
    def __init__(self) -> None:
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL is missing")
        if not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")
        self._rest_url = f"{settings.supabase_url}/rest/v1"
        self._auth_url = f"{settings.supabase_url}/auth/v1"

    async def get_user_from_jwt(self, jwt_token: str) -> dict[str, Any]:
        headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {jwt_token}",
        }
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(f"{self._auth_url}/user", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_profile_role(self, user_id: str) -> str | None:
        rows = await self.select(
            "profiles",
            query=f"id=eq.{user_id}&select=role&limit=1",
            use_service_key=True,
        )
        if not rows:
            return None
        return rows[0].get("role")

    async def select(
        self,
        table: str,
        query: str = "",
        *,
        use_service_key: bool = True,
        user_jwt: str | None = None,
    ) -> list[dict[str, Any]]:
        headers = self._headers(use_service_key=use_service_key, user_jwt=user_jwt)
        url = f"{self._rest_url}/{table}"
        if query:
            url = f"{url}?{query}"
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def insert(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        use_service_key: bool = True,
        user_jwt: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(use_service_key=use_service_key, user_jwt=user_jwt)
        headers["Prefer"] = "return=representation"
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self._rest_url}/{table}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            rows = response.json()
            return rows[0] if rows else {}

    async def upsert(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        on_conflict: str,
        use_service_key: bool = True,
        user_jwt: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(use_service_key=use_service_key, user_jwt=user_jwt)
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self._rest_url}/{table}?on_conflict={on_conflict}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            rows = response.json()
            return rows[0] if rows else {}

    async def update(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        query: str,
        use_service_key: bool = True,
        user_jwt: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(use_service_key=use_service_key, user_jwt=user_jwt)
        headers["Prefer"] = "return=representation"
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.patch(
                f"{self._rest_url}/{table}?{query}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            rows = response.json()
            return rows[0] if rows else {}

    def _headers(self, *, use_service_key: bool, user_jwt: str | None) -> dict[str, str]:
        key = settings.supabase_service_role_key if use_service_key else settings.supabase_anon_key
        headers = {"apikey": key, "Content-Type": "application/json"}
        if user_jwt:
            headers["Authorization"] = f"Bearer {user_jwt}"
        elif use_service_key:
            headers["Authorization"] = f"Bearer {settings.supabase_service_role_key}"
        return headers
