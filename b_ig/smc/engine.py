from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from b_ig.models import (
    Choch,
    FairValueGap,
    LiquiditySweep,
    MarketContext,
    OrderBlock,
    Side,
    Strength,
    StructureState,
)
from b_ig.smc.indicators import atr, ema


class SMCEngine:
    """Detect SMC components on M5 with optional HTF confirmation."""

    def __init__(self, swing_window: int = 3) -> None:
        self.swing_window = swing_window

    def analyze(
        self,
        symbol: str,
        candles: pd.DataFrame,
        htf_candles: dict[str, pd.DataFrame] | None = None,
        session_name: str = "UNKNOWN",
    ) -> MarketContext:
        candles = candles.copy()
        self._validate(candles)
        structure = self.market_structure(candles)
        htf_structure = self._htf_structure(htf_candles) if htf_candles else structure
        choch = self.detect_choch(candles, structure)
        ob = self.detect_order_block(candles, choch)
        fvg = self.detect_fvg(candles, choch.side if choch else None)
        sweep = self.detect_liquidity_sweep(candles, choch.side if choch else None)
        ema9 = float(ema(candles["close"], 9).iloc[-1])
        ema20 = float(ema(candles["close"], 20).iloc[-1])
        vol = float(atr(candles).iloc[-1])
        return MarketContext(
            symbol=symbol,
            structure=structure,
            htf_structure=htf_structure,
            choch=choch,
            order_block=ob,
            fvg=fvg,
            liquidity_sweep=sweep,
            ema9=ema9,
            ema20=ema20,
            volatility=vol,
            session_name=session_name,
        )

    def market_structure(self, candles: pd.DataFrame) -> StructureState:
        swings = self._swings(candles)
        highs = swings["highs"][-3:]
        lows = swings["lows"][-3:]
        if len(highs) < 2 or len(lows) < 2:
            return StructureState.TRANSITIONAL
        hh = highs[-1][1] > highs[-2][1]
        hl = lows[-1][1] > lows[-2][1]
        lh = highs[-1][1] < highs[-2][1]
        ll = lows[-1][1] < lows[-2][1]
        if hh and hl:
            return StructureState.BULLISH
        if lh and ll:
            return StructureState.BEARISH
        if abs(highs[-1][1] - highs[-2][1]) < candles["close"].iloc[-1] * 0.0005:
            return StructureState.RANGING
        return StructureState.TRANSITIONAL

    def detect_choch(self, candles: pd.DataFrame, structure: StructureState) -> Choch | None:
        swings = self._swings(candles)
        if len(swings["highs"]) < 2 or len(swings["lows"]) < 2:
            return None
        last = candles.iloc[-1]
        last_close = float(last["close"])
        last_range = float(last["high"] - last["low"])
        avg_range = float((candles["high"] - candles["low"]).tail(20).mean())
        displacement_ok = avg_range > 0 and last_range >= avg_range * 1.35
        volume_confirmed = self._volume_confirmed(candles)
        now = self._timestamp(candles.index[-1])

        previous_lh = swings["highs"][-1][1]
        previous_hl = swings["lows"][-1][1]
        if structure in {StructureState.BEARISH, StructureState.TRANSITIONAL}:
            if last_close > previous_lh and displacement_ok:
                return Choch(
                    Side.BUY,
                    previous_lh,
                    now,
                    last_range / avg_range if avg_range else 0.0,
                    volume_confirmed,
                    80.0 + (10.0 if volume_confirmed else 0.0),
                )
        if structure in {StructureState.BULLISH, StructureState.TRANSITIONAL}:
            if last_close < previous_hl and displacement_ok:
                return Choch(
                    Side.SELL,
                    previous_hl,
                    now,
                    last_range / avg_range if avg_range else 0.0,
                    volume_confirmed,
                    80.0 + (10.0 if volume_confirmed else 0.0),
                )
        return None

    def detect_order_block(self, candles: pd.DataFrame, choch: Choch | None) -> OrderBlock | None:
        if choch is None:
            return None
        search = candles.iloc[-15:-1]
        if search.empty:
            return None
        if choch.side is Side.BUY:
            candidates = search[search["close"] < search["open"]]
        else:
            candidates = search[search["close"] > search["open"]]
        if candidates.empty:
            return None
        candle = candidates.iloc[-1]
        volume = float(candle.get("volume", 0.0))
        avg_volume = float(candles.get("volume", pd.Series([0.0])).tail(30).mean() or 0.0)
        body = abs(float(candle["close"] - candle["open"]))
        avg_body = abs(candles["close"] - candles["open"]).tail(30).mean()
        score = 55.0
        if avg_volume and volume >= avg_volume * 1.2:
            score += 15.0
        if avg_body and body >= avg_body:
            score += 10.0
        if choch.confidence >= 85:
            score += 15.0
        rank = self._rank(score)
        high = float(candle["high"])
        low = float(candle["low"])
        return OrderBlock(
            side=choch.side,
            high=high,
            low=low,
            midpoint=(high + low) / 2,
            volume=volume,
            created_at=self._timestamp(candidates.index[-1]),
            strength_score=min(score, 100.0),
            rank=rank,
        )

    def detect_fvg(self, candles: pd.DataFrame, side: Side | None = None) -> FairValueGap | None:
        found: list[FairValueGap] = []
        for i in range(max(2, len(candles) - 40), len(candles)):
            c1 = candles.iloc[i - 2]
            c3 = candles.iloc[i]
            created_at = self._timestamp(candles.index[i])
            if float(c1["high"]) < float(c3["low"]):
                found.append(self._build_fvg(Side.BUY, c1, c3, i, len(candles), created_at))
            if float(c1["low"]) > float(c3["high"]):
                found.append(self._build_fvg(Side.SELL, c1, c3, i, len(candles), created_at))
        if side:
            found = [g for g in found if g.side is side]
        fresh = [g for g in found if g.fresh]
        return fresh[-1] if fresh else (found[-1] if found else None)

    def detect_liquidity_sweep(
        self,
        candles: pd.DataFrame,
        side: Side | None = None,
    ) -> LiquiditySweep | None:
        lookback = candles.tail(30)
        if len(lookback) < 10:
            return None
        last = lookback.iloc[-1]
        prior = lookback.iloc[:-1]
        now = self._timestamp(lookback.index[-1])
        tolerance = float(lookback["close"].iloc[-1]) * 0.0005

        equal_lows = prior["low"].nsmallest(3)
        equal_highs = prior["high"].nlargest(3)
        sell_side_level = float(equal_lows.mean())
        buy_side_level = float(equal_highs.mean())

        if side in {Side.BUY, None}:
            swept = float(last["low"]) < sell_side_level - tolerance
            reclaimed = float(last["close"]) > sell_side_level
            if swept and reclaimed:
                return LiquiditySweep(Side.BUY, sell_side_level, now, 90.0)
        if side in {Side.SELL, None}:
            swept = float(last["high"]) > buy_side_level + tolerance
            reclaimed = float(last["close"]) < buy_side_level
            if swept and reclaimed:
                return LiquiditySweep(Side.SELL, buy_side_level, now, 90.0)
        return None

    def price_in_zone(self, price: float, low: float, high: float) -> bool:
        return low <= price <= high

    def _htf_structure(self, htf_candles: dict[str, pd.DataFrame]) -> StructureState:
        states = [self.market_structure(c) for c in htf_candles.values() if len(c) >= 20]
        if not states:
            return StructureState.TRANSITIONAL
        if all(s is StructureState.BULLISH for s in states):
            return StructureState.BULLISH
        if all(s is StructureState.BEARISH for s in states):
            return StructureState.BEARISH
        return StructureState.TRANSITIONAL

    def _swings(self, candles: pd.DataFrame) -> dict[str, list[tuple[int, float]]]:
        highs: list[tuple[int, float]] = []
        lows: list[tuple[int, float]] = []
        w = self.swing_window
        for i in range(w, len(candles) - w):
            window = candles.iloc[i - w : i + w + 1]
            high = float(candles["high"].iloc[i])
            low = float(candles["low"].iloc[i])
            if high >= float(window["high"].max()):
                highs.append((i, high))
            if low <= float(window["low"].min()):
                lows.append((i, low))
        return {"highs": highs, "lows": lows}

    def _build_fvg(
        self,
        side: Side,
        c1: pd.Series,
        c3: pd.Series,
        index: int,
        total: int,
        created_at: datetime,
    ) -> FairValueGap:
        if side is Side.BUY:
            low = float(c1["high"])
            high = float(c3["low"])
            fill = max(0.0, min(1.0, (high - float(c3["close"])) / max(high - low, 1e-12)))
        else:
            low = float(c3["high"])
            high = float(c1["low"])
            fill = max(0.0, min(1.0, (float(c3["close"]) - low) / max(high - low, 1e-12)))
        gap_size = high - low
        score = 50.0 + min(gap_size / max(float(c3["close"]) * 0.0005, 1e-12), 30.0)
        return FairValueGap(
            side=side,
            high=high,
            low=low,
            gap_size=gap_size,
            fill_percent=fill,
            age=total - index - 1,
            strength=self._rank(score),
            created_at=created_at,
        )

    def _volume_confirmed(self, candles: pd.DataFrame) -> bool:
        if "volume" not in candles:
            return False
        vol = candles["volume"].tail(20)
        return bool(float(vol.iloc[-1]) >= float(vol.mean()) * 1.1)

    def _rank(self, score: float) -> Strength:
        if score >= 90:
            return Strength.INSTITUTIONAL
        if score >= 75:
            return Strength.STRONG
        if score >= 60:
            return Strength.MEDIUM
        return Strength.WEAK

    def _timestamp(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def _validate(self, candles: pd.DataFrame) -> None:
        required = {"open", "high", "low", "close"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"missing candle columns: {sorted(missing)}")
        if len(candles) < 30:
            raise ValueError("at least 30 candles are required")

