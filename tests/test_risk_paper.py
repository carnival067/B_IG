from __future__ import annotations

import asyncio

from b_ig.broker import PaperBroker
from b_ig.config import Settings
from b_ig.models import SignalSide, TradeSignal
from b_ig.risk import RiskManager


def test_paper_order_flow() -> None:
    asyncio.run(_paper_order_flow())


async def _paper_order_flow() -> None:
    settings = Settings(STARTING_BALANCE=10_000, RISK_PER_TRADE=0.01)
    risk = RiskManager(settings)
    signal = TradeSignal("EURUSD", SignalSide.BUY, 90, 1.1000, 1.0980, 1.1100)
    sized = risk.size_signal(signal, 10_000)
    order = risk.order_from_signal(sized)
    approved, reason = risk.validate_order(order, 10_000)
    assert approved, reason
    broker = PaperBroker(10_000)
    result = await broker.submit(order)
    assert result["status"] == "filled"
    assert len(await broker.positions()) == 1
