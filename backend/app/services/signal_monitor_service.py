from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.services.binance_service import BinanceService
from app.services.notification_service import NotificationService
from app.services.supabase_service import SupabaseService


@dataclass
class SignalMonitorConfig:
    interval_seconds: int = 15
    batch_limit: int = 100


class SignalMonitorService:
    def __init__(self, config: SignalMonitorConfig | None = None) -> None:
        self.config = config or SignalMonitorConfig()
        self._binance = BinanceService()
        self._notifications = NotificationService()
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._binance.close()

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.scan_and_update()
            except Exception:
                pass
            await asyncio.sleep(self.config.interval_seconds)

    async def scan_and_update(self) -> None:
        service = SupabaseService()
        rows = await service.select(
            "signals",
        query=(
                "select=id,pair,trade_type,entry,sl,tp,tp1,tp2,tp3,tp1_hit,realized_pnl,status,pnl,risk_level,created_at"
                f"&status=eq.open&limit={self.config.batch_limit}"
            ),
            use_service_key=True,
        )
        if not rows:
            return

        price_map = await self._build_price_map(rows)
        for row in rows:
            await self._process_signal(service, row, price_map)

    async def _build_price_map(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        try:
            prices = await self._binance.get_all_prices()
        except Exception:
            prices = []

        price_map = {item["symbol"].upper(): float(item["price"]) for item in prices if item.get("symbol")}
        for row in rows:
            pair = str(row.get("pair", "")).upper()
            if pair and pair not in price_map:
                try:
                    price_map[pair] = await self._binance.get_price(pair)
                except Exception:
                    continue
        return price_map

    async def _process_signal(self, service: SupabaseService, row: dict[str, Any], price_map: dict[str, float]) -> None:
        pair = str(row.get("pair", "")).upper()
        if not pair:
            return

        current_price = price_map.get(pair)
        if current_price is None:
            return

        trade_type = str(row.get("trade_type", "")).lower()
        entry = float(row.get("entry", 0) or 0)
        sl = float(row.get("sl", 0) or 0)
        tp = float(row.get("tp", 0) or 0)
        tp1 = float(row.get("tp1", 0) or 0)
        tp1_hit = bool(row.get("tp1_hit", False))
        signal_id = str(row.get("id", ""))

        if entry <= 0 or sl <= 0 or tp <= 0 or not signal_id:
            return

        pnl = self._calculate_pnl(trade_type, entry, current_price)
        status = self._derive_status(trade_type, current_price, sl, tp)

        payload: dict[str, Any] = {"pnl": pnl}
        if tp1 > 0 and not tp1_hit:
            if self._tp_hit(trade_type, current_price, tp1):
                payload["tp1_hit"] = True
                payload["sl"] = entry
        if status != "open":
            payload["status"] = status
            payload["realized_pnl"] = pnl
        elif payload.get("tp1_hit"):
            payload["status"] = "open"

        updated = await service.update(
            "signals",
            payload=payload,
            query=f"id=eq.{signal_id}",
            use_service_key=True,
        )

        if status != "open" and self._notifications.enabled:
            await self._send_status_notification(service, updated, status, signal_id)

    @staticmethod
    def _calculate_pnl(trade_type: str, entry: float, current_price: float) -> float:
        if entry <= 0:
            return 0.0
        if trade_type == "short":
            return ((entry - current_price) / entry) * 100
        return ((current_price - entry) / entry) * 100

    @staticmethod
    def _derive_status(trade_type: str, price: float, sl: float, tp: float) -> str:
        if trade_type == "short":
            if price <= tp:
                return "tp_hit"
            if price >= sl:
                return "sl_hit"
            return "open"

        if price >= tp:
            return "tp_hit"
        if price <= sl:
            return "sl_hit"
        return "open"

    @staticmethod
    def _tp_hit(trade_type: str, price: float, target: float) -> bool:
        if trade_type == "short":
            return price <= target
        return price >= target

    async def _send_status_notification(
        self,
        service: SupabaseService,
        updated: dict[str, Any],
        status: str,
        signal_id: str,
    ) -> None:
        try:
            rows = await service.select(
                "device_tokens",
                query="is_active=eq.true&select=token",
                use_service_key=True,
            )
        except Exception:
            return

        tokens = [r.get("token", "") for r in rows if r.get("token")]
        if not tokens:
            return

        title = f"Signal Update: {updated.get('pair', '')}"
        body = f"Auto-triggered {status.replace('_', ' ').upper()} for {updated.get('pair', '')}"
        try:
            self._notifications.send_signal_alert(
                tokens=tokens,
                title=title,
                body=body,
                data={"type": "signal_status", "signal_id": signal_id, "status": status},
            )
        except Exception:
            return


signal_monitor_service = SignalMonitorService()
