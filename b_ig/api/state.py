from __future__ import annotations

from functools import lru_cache

from b_ig.broker import PaperBroker
from b_ig.config import get_settings
from b_ig.data import MarketSimulator
from b_ig.execution import TradingBot
from b_ig.risk import RiskManager
from b_ig.strategy import SMCStrategy


@lru_cache
def get_bot() -> TradingBot:
    settings = get_settings()
    broker = PaperBroker(settings.STARTING_BALANCE)
    risk = RiskManager(settings)
    strategy = SMCStrategy(settings)
    symbols = settings.symbols or ["EURUSD"]
    markets = {symbol: MarketSimulator(symbol) for symbol in symbols}
    return TradingBot(strategy=strategy, broker=broker, risk=risk, markets=markets)
