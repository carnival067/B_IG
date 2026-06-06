from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from b_ig.broker.base import Broker
from b_ig.config import Settings
from b_ig.models import Order, Position, Side


class BinanceAuthError(RuntimeError):
    """Raised when Binance Futures authentication or configuration fails."""


class BinanceFuturesBroker(Broker):
    name = "BINANCE_DEMO"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._symbol_rules: dict[str, dict[str, Decimal]] = {}

    async def test_connection(self) -> dict[str, Any]:
        self._require_demo_configuration(require_auto=False)
        server_time = await self._public("GET", "/fapi/v1/time")
        balance = await self.balance()
        positions = await self.positions()
        return {
            "authenticated": True,
            "environment": self.settings.BINANCE_ENV.upper(),
            "base_url": self.settings.binance_base_url,
            "server_time": server_time.get("serverTime"),
            "balance": balance,
            "positions": len(positions),
            "auto_trading": self.settings.BINANCE_AUTO_TRADING,
        }

    async def balance(self) -> float:
        self._require_demo_configuration(require_auto=False)
        rows = await self._signed("GET", "/fapi/v2/balance")
        for row in rows:
            if row.get("asset") == "USDT":
                return float(row.get("availableBalance") or row.get("balance") or 0.0)
        return 0.0

    async def positions(self) -> list[Position]:
        self._require_demo_configuration(require_auto=False)
        rows = await self._signed("GET", "/fapi/v2/positionRisk")
        positions: list[Position] = []
        for row in rows:
            amount = float(row.get("positionAmt") or 0.0)
            if amount == 0:
                continue
            side = Side.BUY if amount > 0 else Side.SELL
            positions.append(
                Position(
                    symbol=str(row.get("symbol", "")),
                    side=side,
                    size=abs(amount),
                    entry=float(row.get("entryPrice") or 0.0),
                    stop_loss=0.0,
                    take_profit=0.0,
                    opened_at=datetime.now(UTC),
                )
            )
        return positions

    async def submit(self, order: Order) -> dict:
        self._require_demo_configuration(require_auto=True)
        symbol = order.symbol.upper()
        await self._configure_symbol(symbol)
        quantity = await self._normalize_quantity(symbol, order.size)
        if quantity <= 0:
            return {"status": "rejected", "reason": "quantity below Binance minimum"}

        entry = await self._signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": order.side.value,
                "type": "MARKET",
                "quantity": self._format_decimal(quantity),
                "newOrderRespType": "RESULT",
            },
        )
        exit_side = Side.SELL if order.side is Side.BUY else Side.BUY
        try:
            stop = await self._protective_order(
                symbol,
                exit_side,
                "STOP_MARKET",
                order.stop_loss,
            )
            take = await self._protective_order(
                symbol,
                exit_side,
                "TAKE_PROFIT_MARKET",
                order.take_profit,
            )
        except Exception:
            await self._flatten(symbol, exit_side, quantity)
            raise

        return {
            "status": "submitted",
            "mode": "BINANCE_DEMO",
            "entry": entry,
            "stop": stop,
            "take_profit": take,
        }

    async def close_all(self, reason: str) -> list[dict]:
        self._require_demo_configuration(require_auto=True)
        results = []
        for position in await self.positions():
            exit_side = Side.SELL if position.side is Side.BUY else Side.BUY
            result = await self._flatten(
                position.symbol,
                exit_side,
                Decimal(str(position.size)),
            )
            results.append(
                {"symbol": position.symbol, "reason": reason, "result": result}
            )
        return results

    async def _configure_symbol(self, symbol: str) -> None:
        await self._signed(
            "POST",
            "/fapi/v1/leverage",
            {"symbol": symbol, "leverage": self.settings.BINANCE_LEVERAGE},
        )
        try:
            await self._signed(
                "POST",
                "/fapi/v1/marginType",
                {
                    "symbol": symbol,
                    "marginType": self.settings.BINANCE_MARGIN_TYPE.upper(),
                },
            )
        except httpx.HTTPStatusError as exc:
            if '"code":-4046' not in exc.response.text.replace(" ", ""):
                raise

    async def _protective_order(
        self,
        symbol: str,
        side: Side,
        order_type: str,
        trigger_price: float,
    ) -> dict:
        price = await self._normalize_price(symbol, trigger_price)
        return await self._signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side.value,
                "type": order_type,
                "stopPrice": self._format_decimal(price),
                "closePosition": "true",
                "workingType": "MARK_PRICE",
            },
        )

    async def _flatten(
        self,
        symbol: str,
        side: Side,
        quantity: Decimal,
    ) -> dict:
        with_context = {"symbol": symbol}
        try:
            await self._signed("DELETE", "/fapi/v1/allOpenOrders", with_context)
        except httpx.HTTPError:
            pass
        return await self._signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side.value,
                "type": "MARKET",
                "quantity": self._format_decimal(quantity),
                "reduceOnly": "true",
            },
        )

    async def _normalize_quantity(self, symbol: str, quantity: float) -> Decimal:
        rules = await self._rules(symbol)
        value = self._floor(Decimal(str(quantity)), rules["step_size"])
        if value < rules["min_qty"]:
            return Decimal("0")
        return value

    async def _normalize_price(self, symbol: str, price: float) -> Decimal:
        rules = await self._rules(symbol)
        return self._floor(Decimal(str(price)), rules["tick_size"])

    async def _rules(self, symbol: str) -> dict[str, Decimal]:
        if symbol in self._symbol_rules:
            return self._symbol_rules[symbol]
        info = await self._public(
            "GET",
            "/fapi/v1/exchangeInfo",
            {"symbol": symbol},
        )
        symbols = info.get("symbols", [])
        if not symbols:
            raise ValueError(f"Binance symbol not found: {symbol}")
        filters = {item["filterType"]: item for item in symbols[0]["filters"]}
        lot = filters["LOT_SIZE"]
        price_filter = filters["PRICE_FILTER"]
        rules = {
            "step_size": Decimal(lot["stepSize"]),
            "min_qty": Decimal(lot["minQty"]),
            "tick_size": Decimal(price_filter["tickSize"]),
        }
        self._symbol_rules[symbol] = rules
        return rules

    async def _public(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method,
                f"{self.settings.binance_base_url}{path}",
                params=params,
            )
        response.raise_for_status()
        return response.json()

    async def _signed(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload["recvWindow"] = 5000
        query = urlencode(payload)
        secret = self.settings.BINANCE_API_SECRET.get_secret_value().encode()
        payload["signature"] = hmac.new(
            secret,
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-MBX-APIKEY": self.settings.BINANCE_API_KEY.get_secret_value(),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method,
                f"{self.settings.binance_base_url}{path}",
                params=payload,
                headers=headers,
            )
        response.raise_for_status()
        return response.json()

    def _require_demo_configuration(self, require_auto: bool) -> None:
        if self.settings.BINANCE_ENV.upper() != "DEMO":
            raise BinanceAuthError("Only Binance DEMO is enabled in this build")
        if not self.settings.binance_configured:
            raise BinanceAuthError("Binance demo API credentials are missing")
        if require_auto and not self.settings.binance_demo_enabled:
            raise BinanceAuthError(
                "Automatic Binance demo trading requires BROKER=BINANCE, "
                "MODE=DEMO, and BINANCE_AUTO_TRADING=true"
            )

    def _floor(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

    def _format_decimal(self, value: Decimal) -> str:
        return format(value.normalize(), "f")
