from __future__ import annotations

from b_ig.models import MarketContext, Side, Strength, StructureState


class TradeScorer:
    """Deterministic AI-style score that can later be blended with ML output."""

    def score(self, context: MarketContext, side: Side) -> tuple[int, list[str]]:
        score = 0.0
        reasons: list[str] = []

        desired_structure = StructureState.BULLISH if side is Side.BUY else StructureState.BEARISH
        if context.htf_structure is desired_structure:
            score += 18
            reasons.append("HTF trend aligned")
        if context.structure in {desired_structure, StructureState.TRANSITIONAL}:
            score += 10
            reasons.append("M5 structure tradable")
        if context.choch and context.choch.side is side:
            score += min(18, context.choch.confidence * 0.18)
            reasons.append("CHoCH confirmed")
        if context.order_block and context.order_block.side is side:
            score += self._strength_points(context.order_block.rank, strong=18)
            reasons.append(f"{context.order_block.rank.value} order block")
        if context.fvg and context.fvg.side is side and context.fvg.fresh:
            score += self._strength_points(context.fvg.strength, strong=12)
            reasons.append("fresh FVG")
        if context.liquidity_sweep and context.liquidity_sweep.side is side:
            score += min(12, context.liquidity_sweep.quality * 0.12)
            reasons.append("liquidity sweep complete")
        if (side is Side.BUY and context.ema9 > context.ema20) or (
            side is Side.SELL and context.ema9 < context.ema20
        ):
            score += 8
            reasons.append("EMA confirmation")
        if context.session_name in {"LONDON", "NEW_YORK", "OVERLAP"}:
            score += 6
            reasons.append(f"{context.session_name} session")
        return int(min(round(score), 100)), reasons

    def _strength_points(self, strength: Strength, strong: int) -> float:
        points = {
            Strength.WEAK: 2,
            Strength.MEDIUM: strong * 0.55,
            Strength.STRONG: strong,
            Strength.INSTITUTIONAL: strong + 4,
        }
        return points[strength]

