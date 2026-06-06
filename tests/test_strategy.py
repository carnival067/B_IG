from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from b_ig.config import Settings
from b_ig.filters.news import NewsFilter
from b_ig.filters.session import SessionFilter
from b_ig.models import (
    Choch,
    FairValueGap,
    LiquiditySweep,
    MarketContext,
    OrderBlock,
    Side,
    SignalSide,
    Strength,
    StructureState,
)
from b_ig.strategy import SMCStrategy


class AlwaysSession(SessionFilter):
    def session_name(self, now: datetime) -> str:
        return "LONDON"

    def tradable(self, now: datetime) -> bool:
        return True

    def tradable_for_symbol(self, symbol: str, now: datetime) -> bool:
        return True

    def session_name_for_symbol(self, symbol: str, now: datetime) -> str:
        return "LONDON"


class StubSMC:
    def analyze(self, symbol, candles, htf_candles=None, session_name="LONDON"):
        now = datetime.now(UTC)
        return MarketContext(
            symbol=symbol,
            structure=StructureState.BULLISH,
            htf_structure=StructureState.BULLISH,
            choch=Choch(Side.BUY, 1.101, now, 2.0, True, 90),
            order_block=OrderBlock(
                Side.BUY,
                1.1010,
                1.1000,
                1.1005,
                200,
                now,
                92,
                Strength.INSTITUTIONAL,
            ),
            fvg=FairValueGap(Side.BUY, 1.1012, 1.1002, 0.001, 0.1, 1, Strength.STRONG, now),
            liquidity_sweep=LiquiditySweep(Side.BUY, 1.099, now, 90),
            ema9=1.1010,
            ema20=1.1000,
            volatility=0.001,
            session_name=session_name,
        )

    def price_in_zone(self, price, low, high):
        return low <= price <= high

    def _timestamp(self, value):
        return value


def test_strategy_emits_buy_when_all_conditions_align() -> None:
    now = datetime(2026, 1, 1, 8, tzinfo=UTC)
    candles = pd.DataFrame(
        [[1.1005, 1.1010, 1.1000, 1.1006, 100]],
        columns=["open", "high", "low", "close", "volume"],
        index=[now],
    )
    strategy = SMCStrategy(
        Settings(AI_MIN_SCORE=80),
        smc=StubSMC(),
        session_filter=AlwaysSession(),
        news_filter=NewsFilter(),
    )
    signal = strategy.generate("EURUSD", candles)
    assert signal.side is SignalSide.BUY
    assert signal.score >= 80
    assert signal.take_profit > signal.entry


def test_crypto_symbol_is_not_blocked_by_session_filter() -> None:
    now = datetime(2026, 1, 3, 2, tzinfo=UTC)
    candles = pd.DataFrame(
        [[1.1005, 1.1010, 1.1000, 1.1006, 100]],
        columns=["open", "high", "low", "close", "volume"],
        index=[now],
    )
    strategy = SMCStrategy(
        Settings(AI_MIN_SCORE=80),
        smc=StubSMC(),
        news_filter=NewsFilter(),
    )
    crypto_signal = strategy.generate("BTCUSDT", candles)
    forex_signal = strategy.generate("EURUSD", candles)
    assert crypto_signal.reason != "session not tradable"
    assert forex_signal.reason == "session not tradable"
