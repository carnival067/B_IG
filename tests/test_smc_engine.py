from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from b_ig.models import Side
from b_ig.smc import SMCEngine


def candles() -> pd.DataFrame:
    start = datetime(2026, 1, 1, 8, tzinfo=UTC)
    rows = []
    price = 1.1000
    for i in range(70):
        price -= 0.0004
        rows.append(
            [
                start + timedelta(minutes=5 * i),
                price,
                price + 0.0005,
                price - 0.0005,
                price - 0.0001,
                100,
            ]
        )
    rows[-4] = [rows[-4][0], 1.0700, 1.0710, 1.0670, 1.0680, 120]
    rows[-3] = [rows[-3][0], 1.0680, 1.0690, 1.0660, 1.0670, 140]
    rows[-2] = [rows[-2][0], 1.0670, 1.0680, 1.0640, 1.0675, 150]
    rows[-1] = [rows[-1][0], 1.0675, 1.0810, 1.0630, 1.0800, 300]
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return df.set_index("timestamp")


def test_detects_bullish_liquidity_sweep() -> None:
    sweep = SMCEngine().detect_liquidity_sweep(candles(), Side.BUY)
    assert sweep is not None
    assert sweep.side is Side.BUY


def test_analyze_returns_context() -> None:
    context = SMCEngine().analyze(
        "EURUSD",
        candles(),
        {"M15": candles(), "H1": candles()},
        "LONDON",
    )
    assert context.symbol == "EURUSD"
    assert context.ema9 > 0
