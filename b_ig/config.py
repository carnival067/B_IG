from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    MODE: Mode = Mode.PAPER
    ALLOW_LIVE_TRADING: bool = False

    STARTING_BALANCE: float = Field(default=10_000.0, gt=0)
    RISK_PER_TRADE: float = Field(default=0.01, gt=0, le=0.02)
    LEVERAGE: float = Field(default=25.0, gt=0)
    RISK_REWARD: float = Field(default=5.0, ge=1.0)
    STOP_BUFFER_PIPS: float = Field(default=3.0, ge=0.0, le=10.0)
    AI_MIN_SCORE: int = Field(default=80, ge=0, le=100)

    SYMBOLS: str = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,BTCUSDT"
    PRIMARY_TIMEFRAME: str = "M5"
    HTF_TIMEFRAMES: str = "M15,H1"

    IG_API_KEY: SecretStr = SecretStr("")
    IG_USERNAME: str = ""
    IG_PASSWORD: SecretStr = SecretStr("")
    IG_ACCOUNT_TYPE: str = "DEMO"

    DATABASE_URL: str = "postgresql+asyncpg://b_ig:b_ig@localhost:5432/b_ig"
    ECONOMIC_CALENDAR_URL: str = ""

    @property
    def symbols(self) -> list[str]:
        return [s.strip() for s in self.SYMBOLS.split(",") if s.strip()]

    @property
    def htf_timeframes(self) -> list[str]:
        return [s.strip() for s in self.HTF_TIMEFRAMES.split(",") if s.strip()]

    @property
    def live_enabled(self) -> bool:
        return self.MODE is Mode.LIVE and self.ALLOW_LIVE_TRADING

    @property
    def ig_base_url(self) -> str:
        if self.IG_ACCOUNT_TYPE.upper() == "LIVE":
            return "https://api.ig.com/gateway/deal"
        return "https://demo-api.ig.com/gateway/deal"


@lru_cache
def get_settings() -> Settings:
    return Settings()
