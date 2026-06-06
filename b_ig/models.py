from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StructureState(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    TRANSITIONAL = "TRANSITIONAL"


class Strength(StrEnum):
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"
    INSTITUTIONAL = "INSTITUTIONAL"


@dataclass(slots=True)
class OrderBlock:
    side: Side
    high: float
    low: float
    midpoint: float
    volume: float
    created_at: datetime
    strength_score: float
    rank: Strength


@dataclass(slots=True)
class FairValueGap:
    side: Side
    high: float
    low: float
    gap_size: float
    fill_percent: float
    age: int
    strength: Strength
    created_at: datetime

    @property
    def fresh(self) -> bool:
        return self.age <= 30 and self.fill_percent < 0.5


@dataclass(slots=True)
class LiquiditySweep:
    side: Side
    level: float
    swept_at: datetime
    quality: float


@dataclass(slots=True)
class Choch:
    side: Side
    broken_level: float
    confirmed_at: datetime
    displacement: float
    volume_confirmed: bool
    confidence: float


@dataclass(slots=True)
class MarketContext:
    symbol: str
    structure: StructureState
    htf_structure: StructureState
    choch: Choch | None
    order_block: OrderBlock | None
    fvg: FairValueGap | None
    liquidity_sweep: LiquiditySweep | None
    ema9: float
    ema20: float
    volatility: float
    session_name: str
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TradeSignal:
    symbol: str
    side: SignalSide
    score: int
    entry: float
    stop_loss: float
    take_profit: float
    size: float = 0.0
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Order:
    symbol: str
    side: Side
    size: float
    entry: float
    stop_loss: float
    take_profit: float
    reason: str


@dataclass(slots=True)
class Position:
    symbol: str
    side: Side
    size: float
    entry: float
    stop_loss: float
    take_profit: float
    opened_at: datetime

