from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pandas as pd

from b_ig.config import Settings
from b_ig.data.base import MarketDataSource


class BinanceFuturesMarket(MarketDataSource):
    intervals = {"M5": "5m", "M15": "15m", "H1": "1h"}

    def __init__(self, symbol: str, settings: Settings) -> None:
        self.symbol = symbol.upper()
        self.settings = settings
        self._frames: dict[str, pd.DataFrame] = {}

    async def next_frame(self) -> pd.DataFrame:
        await self.refresh()
        return self.frame()

    async def refresh(self) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            for timeframe, interval in self.intervals.items():
                response = await client.get(
                    f"{self.settings.binance_base_url}/fapi/v1/klines",
                    params={"symbol": self.symbol, "interval": interval, "limit": 250},
                )
                response.raise_for_status()
                self._frames[timeframe] = self._to_frame(response.json())

    def frame(self) -> pd.DataFrame:
        return self._frames.get("M5", self._empty()).copy()

    def htf_frames(self) -> dict[str, pd.DataFrame]:
        return {
            timeframe: self._frames.get(timeframe, self._empty()).copy()
            for timeframe in ("M15", "H1")
        }

    def candles_json(self, limit: int = 120) -> list[dict]:
        data = self.frame().tail(limit)
        return [
            {
                "time": ts.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
            }
            for ts, row in data.iterrows()
        ]

    def _to_frame(self, rows: list[list]) -> pd.DataFrame:
        parsed = [
            (
                datetime.fromtimestamp(float(row[0]) / 1000, tz=UTC),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            )
            for row in rows
        ]
        return pd.DataFrame(
            parsed,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        ).set_index("timestamp")

    def _empty(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
