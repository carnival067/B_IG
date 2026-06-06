from __future__ import annotations

from typing import Any

import httpx

from b_ig.broker.base import Broker
from b_ig.config import Settings
from b_ig.models import Order, Position, Side


class IGAuthError(RuntimeError):
    """Raised when IG authentication fails."""


class IGBroker(Broker):
    """Guarded async IG adapter placeholder for demo/live rollout."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cst: str | None = None
        self._security_token: str | None = None
        self._account_id: str | None = None

    @property
    def connected(self) -> bool:
        return bool(self._cst and self._security_token)

    async def connect(self) -> None:
        self._require_credentials()
        payload = {
            "identifier": self.settings.IG_USERNAME,
            "password": self.settings.IG_PASSWORD.get_secret_value(),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._url("session"),
                json=payload,
                headers=self._headers(version="2", authed=False),
            )
        if response.status_code != 200:
            raise IGAuthError(
                f"IG login failed ({response.status_code}): {response.text[:200]}"
            )
        self._cst = response.headers.get("CST")
        self._security_token = response.headers.get("X-SECURITY-TOKEN")
        if not self.connected:
            raise IGAuthError("IG login succeeded but session tokens are missing")
        self._account_id = response.json().get("currentAccountId")

    async def test_connection(self) -> dict[str, Any]:
        await self.connect()
        balance = await self.account_summary()
        markets = await self.search_markets("EUR")
        return {
            "authenticated": True,
            "account_id": self._account_id,
            "account_type": self.settings.IG_ACCOUNT_TYPE,
            "base_url": self.settings.ig_base_url,
            "balance": balance,
            "market_access": bool(markets),
            "sample_markets": markets[:3],
        }

    async def balance(self) -> float:
        summary = await self.account_summary()
        return float(summary.get("balance") or summary.get("available") or 0.0)

    async def account_summary(self) -> dict[str, Any]:
        await self._ensure_connected()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                self._url("accounts"),
                headers=self._headers(version="1"),
            )
        response.raise_for_status()
        accounts = response.json().get("accounts", [])
        for account in accounts:
            if account.get("accountId") == self._account_id or account.get("preferred"):
                return account.get("balance", {})
        return {}

    async def search_markets(self, query: str) -> list[dict[str, Any]]:
        await self._ensure_connected()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                self._url("markets"),
                params={"searchTerm": query},
                headers=self._headers(version="1"),
            )
        response.raise_for_status()
        return response.json().get("markets", [])

    async def positions(self) -> list[Position]:
        await self._ensure_connected()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                self._url("positions/otc"),
                headers=self._headers(version="2"),
            )
        response.raise_for_status()
        positions: list[Position] = []
        for item in response.json().get("positions", []):
            position = item.get("position", {})
            market = item.get("market", {})
            direction = position.get("direction", "BUY")
            positions.append(
                Position(
                    symbol=market.get("epic", ""),
                    side=Side(direction),
                    size=float(position.get("dealSize", 0) or 0),
                    entry=float(position.get("openLevel", 0) or 0),
                    stop_loss=float(position.get("stopLevel", 0) or 0),
                    take_profit=float(position.get("limitLevel", 0) or 0),
                    opened_at=position.get("createdDateUTC", ""),
                )
            )
        return positions

    async def submit(self, order: Order) -> dict:
        self._require_credentials()
        if not self.settings.live_enabled and self.settings.MODE.value == "LIVE":
            return {"status": "blocked", "reason": "live trading disabled"}
        raise NotImplementedError("IG order placement must be exercised in DEMO before LIVE")

    async def close_all(self, reason: str) -> list[dict]:
        self._require_credentials()
        raise NotImplementedError("IG close-all must be enabled after DEMO validation")

    def _require_credentials(self) -> None:
        if not (
            self.settings.IG_API_KEY.get_secret_value()
            and self.settings.IG_USERNAME
            and self.settings.IG_PASSWORD.get_secret_value()
        ):
            raise RuntimeError("IG credentials are missing")

    async def _ensure_connected(self) -> None:
        if not self.connected:
            await self.connect()

    def _headers(self, version: str = "2", authed: bool = True) -> dict[str, str]:
        headers = {
            "X-IG-API-KEY": self.settings.IG_API_KEY.get_secret_value(),
            "Content-Type": "application/json",
            "Accept": "application/json; charset=UTF-8",
            "Version": version,
        }
        if authed:
            if not self.connected:
                raise IGAuthError("Not authenticated. Call connect() first.")
            headers["CST"] = self._cst or ""
            headers["X-SECURITY-TOKEN"] = self._security_token or ""
        return headers

    def _url(self, path: str) -> str:
        return f"{self.settings.ig_base_url}/{path.lstrip('/')}"
