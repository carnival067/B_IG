from __future__ import annotations

import pandas as pd

from b_ig.ai import TradeScorer
from b_ig.config import Settings
from b_ig.filters.news import NewsFilter
from b_ig.filters.session import SessionFilter
from b_ig.models import Side, SignalSide, Strength, StructureState, TradeSignal
from b_ig.smc import SMCEngine


class SMCStrategy:
    def __init__(
        self,
        settings: Settings,
        smc: SMCEngine | None = None,
        scorer: TradeScorer | None = None,
        session_filter: SessionFilter | None = None,
        news_filter: NewsFilter | None = None,
    ) -> None:
        self.settings = settings
        self.smc = smc or SMCEngine()
        self.scorer = scorer or TradeScorer()
        self.session_filter = session_filter or SessionFilter()
        self.news_filter = news_filter or NewsFilter()
        self.allow_all_sessions = False

    def generate(
        self,
        symbol: str,
        candles: pd.DataFrame,
        htf_candles: dict[str, pd.DataFrame] | None = None,
    ) -> TradeSignal:
        now = self.smc._timestamp(candles.index[-1])  # noqa: SLF001
        session_name = self.session_filter.session_name(now)
        context = self.smc.analyze(symbol, candles, htf_candles, session_name=session_name)
        price = float(candles["close"].iloc[-1])

        if not self.allow_all_sessions and not self.session_filter.tradable(now):
            return self._hold(symbol, price, "session not tradable")
        if self.news_filter.blocked(now):
            return self._hold(symbol, price, "high-impact news pause")

        for side in (Side.BUY, Side.SELL):
            signal = self._try_side(side, context, price)
            if signal.side is not SignalSide.HOLD:
                return signal
        return self._hold(symbol, price, "SMC conditions not aligned")

    def _try_side(self, side: Side, context, price: float) -> TradeSignal:
        desired_structure = StructureState.BULLISH if side is Side.BUY else StructureState.BEARISH
        if context.htf_structure is not desired_structure:
            return self._hold(context.symbol, price, "HTF trend not aligned")
        if context.choch is None or context.choch.side is not side:
            return self._hold(context.symbol, price, "CHoCH missing")
        if context.order_block is None or context.order_block.side is not side:
            return self._hold(context.symbol, price, "order block missing")
        if context.order_block.rank not in {Strength.STRONG, Strength.INSTITUTIONAL}:
            return self._hold(context.symbol, price, "order block too weak")
        if context.fvg is None or context.fvg.side is not side or not context.fvg.fresh:
            return self._hold(context.symbol, price, "fresh FVG missing")
        if context.liquidity_sweep is None or context.liquidity_sweep.side is not side:
            return self._hold(context.symbol, price, "liquidity sweep missing")
        in_ob = self.smc.price_in_zone(price, context.order_block.low, context.order_block.high)
        in_fvg = self.smc.price_in_zone(price, context.fvg.low, context.fvg.high)
        if not (in_ob and in_fvg):
            return self._hold(context.symbol, price, "price not retraced into OB and FVG")
        if side is Side.BUY and context.ema9 <= context.ema20:
            return self._hold(context.symbol, price, "EMA buy confirmation failed")
        if side is Side.SELL and context.ema9 >= context.ema20:
            return self._hold(context.symbol, price, "EMA sell confirmation failed")

        score, reasons = self.scorer.score(context, side)
        if score < self.settings.AI_MIN_SCORE:
            return self._hold(context.symbol, price, f"AI score too low: {score}")
        buffer = self.settings.STOP_BUFFER_PIPS * self._pip_size(context.symbol)
        if side is Side.BUY:
            stop = context.order_block.low - buffer
            take = price + (price - stop) * self.settings.RISK_REWARD
            signal_side = SignalSide.BUY
        else:
            stop = context.order_block.high + buffer
            take = price - (stop - price) * self.settings.RISK_REWARD
            signal_side = SignalSide.SELL
        return TradeSignal(
            symbol=context.symbol,
            side=signal_side,
            score=score,
            entry=price,
            stop_loss=round(stop, 6),
            take_profit=round(take, 6),
            reason="; ".join(reasons),
        )

    def _hold(self, symbol: str, price: float, reason: str) -> TradeSignal:
        return TradeSignal(symbol, SignalSide.HOLD, 0, price, price, price, reason=reason)

    def _pip_size(self, symbol: str) -> float:
        return 0.01 if "JPY" in symbol.upper() else 0.0001
