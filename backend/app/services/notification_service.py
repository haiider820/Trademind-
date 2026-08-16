from __future__ import annotations

from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings


class NotificationService:
    def __init__(self) -> None:
        self._enabled = False
        self._init_firebase()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _init_firebase(self) -> None:
        path_value = settings.firebase_service_account_path.strip()
        if not path_value:
            return
        cred_path = Path(path_value)
        if not cred_path.exists():
            return
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(str(cred_path)))
            self._enabled = True
        except Exception:
            self._enabled = False

    def send_signal_alert(self, tokens: list[str], title: str, body: str, data: dict[str, str]) -> dict:
        if not self._enabled or not tokens:
            return {"success_count": 0, "failure_count": 0}
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
        return {"success_count": response.success_count, "failure_count": response.failure_count}
