from __future__ import annotations

from decimal import Decimal

import pytest

from b_ig.broker.binance_futures import BinanceAuthError, BinanceFuturesBroker
from b_ig.config import Settings


def test_binance_demo_guard_blocks_live_environment() -> None:
    broker = BinanceFuturesBroker(
        Settings(
            BINANCE_ENV="LIVE",
            BINANCE_API_KEY="key",
            BINANCE_API_SECRET="secret",
        )
    )
    with pytest.raises(BinanceAuthError, match="DEMO"):
        broker._require_demo_configuration(require_auto=False)  # noqa: SLF001


def test_binance_quantity_flooring() -> None:
    broker = BinanceFuturesBroker(Settings())
    assert broker._floor(Decimal("1.23456"), Decimal("0.001")) == Decimal(  # noqa: SLF001
        "1.234"
    )
