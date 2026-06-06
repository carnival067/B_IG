from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from b_ig.broker.base import Broker
from b_ig.models import Order, Position


class PaperBroker(Broker):
    name = "PAPER"

    def __init__(self, starting_balance: float = 10_000.0) -> None:
        self.cash = starting_balance
        self._positions: list[Position] = []
        self.history: list[dict] = []

    async def balance(self) -> float:
        return self.cash

    async def positions(self) -> list[Position]:
        return list(self._positions)

    async def submit(self, order: Order) -> dict:
        position = Position(
            symbol=order.symbol,
            side=order.side,
            size=order.size,
            entry=order.entry,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            opened_at=datetime.now(UTC),
        )
        self._positions.append(position)
        event = {"status": "filled", "mode": "PAPER", "order": asdict(order)}
        self.history.append(event)
        return event

    async def close_all(self, reason: str) -> list[dict]:
        closed = [
            {"status": "closed", "symbol": p.symbol, "side": p.side.value, "reason": reason}
            for p in self._positions
        ]
        self._positions.clear()
        self.history.extend(closed)
        return closed
