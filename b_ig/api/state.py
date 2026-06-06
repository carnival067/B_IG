from __future__ import annotations

from functools import lru_cache

from b_ig.broker import BinanceFuturesBroker, PaperBroker
from b_ig.config import get_settings
from b_ig.data import BinanceFuturesMarket, MarketSimulator
from b_ig.execution import TradingBot
from b_ig.risk import RiskManager
from b_ig.strategy import SMCStrategy


@lru_cache
def get_bot() -> TradingBot:
    settings = get_settings()
    risk = RiskManager(settings)
    strategy = SMCStrategy(settings)
    if settings.binance_demo_enabled:
        broker = BinanceFuturesBroker(settings)
        symbols = [symbol for symbol in settings.symbols if symbol.endswith("USDT")]
        symbols = symbols or ["BTCUSDT"]
        markets = {
            symbol: BinanceFuturesMarket(symbol, settings)
            for symbol in symbols
        }
    else:
        broker = PaperBroker(settings.STARTING_BALANCE)
        symbols = settings.symbols or ["EURUSD"]
        markets = {symbol: MarketSimulator(symbol) for symbol in symbols}
    return TradingBot(strategy=strategy, broker=broker, risk=risk, markets=markets)
