from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pandas as pd

from b_ig.broker.base import Broker
from b_ig.data import MarketSimulator
from b_ig.models import SignalSide
from b_ig.risk import RiskManager
from b_ig.strategy import SMCStrategy


@dataclass
class TradingBot:
    strategy: SMCStrategy
    broker: Broker
    risk: RiskManager
    markets: dict[str, MarketSimulator]
    running: bool = False
    events: list[dict] = field(default_factory=list)
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)

    async def evaluate(
        self,
        symbol: str,
        candles: pd.DataFrame,
        htf_candles: dict[str, pd.DataFrame] | None = None,
    ) -> dict:
        positions = await self.broker.positions()
        if any(position.symbol == symbol for position in positions):
            event = {
                "symbol": symbol,
                "status": "hold",
                "reason": "position already open",
                "score": 0,
            }
            self.events.append(event)
            return event
        signal = self.strategy.generate(symbol, candles, htf_candles)
        if signal.side is SignalSide.HOLD:
            event = {
                "symbol": symbol,
                "status": "hold",
                "reason": signal.reason,
                "score": signal.score,
            }
            self.events.append(event)
            return event
        equity = await self.broker.balance()
        signal = self.risk.size_signal(signal, equity)
        order = self.risk.order_from_signal(signal)
        approved, reason = self.risk.validate_order(order, equity)
        if not approved:
            event = {
                "symbol": symbol,
                "status": "rejected",
                "reason": reason,
                "score": signal.score,
            }
            self.events.append(event)
            return event
        result = await self.broker.submit(order)
        result["symbol"] = symbol
        result["score"] = signal.score
        result["reason"] = signal.reason
        self.events.append(result)
        return result

    async def tick(self, symbol: str | None = None) -> dict:
        if symbol:
            return await self._tick_symbol(symbol)
        results = []
        for market_symbol in self.symbols:
            results.append(await self._tick_symbol(market_symbol))
        return {"status": "scanned", "results": results}

    async def _tick_symbol(self, symbol: str) -> dict:
        market = self.markets[symbol]
        candles = market.next_frame()
        return await self.evaluate(symbol, candles, market.htf_frames())

    def start_auto(self, interval_seconds: int = 5) -> dict:
        if self.running:
            return {"status": "already_running"}
        self.running = True
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        return {"status": "started", "mode": "paper_auto", "interval_seconds": interval_seconds}

    async def _run_loop(self, interval_seconds: int) -> None:
        while self.running:
            await self.tick()
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    @property
    def last_event(self) -> dict | None:
        return self.events[-1] if self.events else None

    @property
    def symbols(self) -> list[str]:
        return list(self.markets)

    def market(self, symbol: str | None = None) -> MarketSimulator:
        symbol = symbol or self.symbols[0]
        if symbol not in self.markets:
            raise KeyError(symbol)
        return self.markets[symbol]
