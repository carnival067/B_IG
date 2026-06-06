from __future__ import annotations

import abc

import pandas as pd


class MarketDataSource(abc.ABC):
    symbol: str

    @abc.abstractmethod
    async def next_frame(self) -> pd.DataFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def frame(self) -> pd.DataFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def htf_frames(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError

    @abc.abstractmethod
    def candles_json(self, limit: int = 120) -> list[dict]:
        raise NotImplementedError

