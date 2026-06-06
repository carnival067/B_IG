from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


class SessionFilter:
    """Session filter using UTC market hours."""

    crypto_quotes = ("USDT", "USDC", "BTC", "ETH")

    def is_crypto(self, symbol: str) -> bool:
        upper = symbol.upper()
        return any(upper.endswith(quote) for quote in self.crypto_quotes)

    def session_name(self, now: datetime) -> str:
        utc = now.astimezone(ZoneInfo("UTC"))
        hour = utc.hour
        if 12 <= hour < 16:
            return "OVERLAP"
        if 7 <= hour < 12:
            return "LONDON"
        if 16 <= hour < 21:
            return "NEW_YORK"
        if utc.weekday() >= 5:
            return "WEEKEND"
        return "ASIAN_OR_LOW_LIQUIDITY"

    def tradable(self, now: datetime) -> bool:
        return self.session_name(now) in {"LONDON", "NEW_YORK", "OVERLAP"}

    def tradable_for_symbol(self, symbol: str, now: datetime) -> bool:
        if self.is_crypto(symbol):
            return True
        return self.tradable(now)

    def session_name_for_symbol(self, symbol: str, now: datetime) -> str:
        if self.is_crypto(symbol):
            return "CRYPTO_24_7"
        return self.session_name(now)
