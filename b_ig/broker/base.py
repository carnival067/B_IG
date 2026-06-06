from __future__ import annotations

import abc

from b_ig.models import Order, Position


class Broker(abc.ABC):
    @abc.abstractmethod
    async def balance(self) -> float:
        raise NotImplementedError

    @abc.abstractmethod
    async def positions(self) -> list[Position]:
        raise NotImplementedError

    @abc.abstractmethod
    async def submit(self, order: Order) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    async def close_all(self, reason: str) -> list[dict]:
        raise NotImplementedError

