from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pandas as pd


@dataclass
class MarketSimulator:
    """Deterministic M5 candle stream for paper trading and dashboard charts."""

    symbol: str = "EURUSD"
    max_bars: int = 240
    _candles: pd.DataFrame = field(init=False, repr=False)
    _step: int = 0

    def __post_init__(self) -> None:
        self._candles = self._seed()

    def frame(self) -> pd.DataFrame:
        return self._candles.copy()

    def htf_frames(self) -> dict[str, pd.DataFrame]:
        return {
            "M15": self._resample("15min"),
            "H1": self._resample("1h"),
        }

    def next_frame(self) -> pd.DataFrame:
        last = self._candles.iloc[-1]
        ts = self._candles.index[-1] + timedelta(minutes=5)
        close = float(last["close"])
        wave = math.sin(self._step / 5) * 0.00035
        drift = 0.00005 if (self._step // 40) % 2 == 0 else -0.00004
        open_price = close
        close_price = max(0.5, close + drift + wave)
        high = max(open_price, close_price) + 0.00035 + abs(wave) * 0.3
        low = min(open_price, close_price) - 0.00035 - abs(wave) * 0.3
        volume = 120 + abs(wave) * 250_000 + (self._step % 9) * 8
        self._step += 1
        self._candles.loc[ts] = [open_price, high, low, close_price, volume]
        self._candles = self._candles.tail(self.max_bars)
        return self.frame()

    def candles_json(self, limit: int = 120) -> list[dict]:
        data = self._candles.tail(limit)
        return [
            {
                "time": ts.isoformat(),
                "open": round(float(row.open), 6),
                "high": round(float(row.high), 6),
                "low": round(float(row.low), 6),
                "close": round(float(row.close), 6),
                "volume": round(float(row.volume), 2),
            }
            for ts, row in data.iterrows()
        ]

    def _seed(self) -> pd.DataFrame:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        start = now - timedelta(minutes=5 * 119)
        rows = []
        price = 1.1000
        for i in range(120):
            wave = math.sin(i / 8) * 0.00045
            drift = 0.00003 if i < 80 else -0.00002
            open_price = price
            close_price = max(0.5, price + drift + wave * 0.25)
            high = max(open_price, close_price) + 0.00035
            low = min(open_price, close_price) - 0.00035
            volume = 100 + (i % 11) * 7 + abs(wave) * 150_000
            rows.append(
                (
                    start + timedelta(minutes=5 * i),
                    open_price,
                    high,
                    low,
                    close_price,
                    volume,
                )
            )
            price = close_price
        return pd.DataFrame(
            rows,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        ).set_index("timestamp")

    def _resample(self, rule: str) -> pd.DataFrame:
        frame = self._candles.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        return frame.dropna()
