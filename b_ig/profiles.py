from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import SecretStr

from b_ig.config import Settings


@dataclass(slots=True)
class IGProfile:
    name: str
    api_key: str
    username: str
    password: str
    account_type: str = "DEMO"
    connected: bool = False
    account_id: str | None = None
    last_checked: datetime | None = None
    last_error: str | None = None

    def settings(self, base: Settings) -> Settings:
        return base.model_copy(
            update={
                "IG_API_KEY": SecretStr(self.api_key),
                "IG_USERNAME": self.username,
                "IG_PASSWORD": SecretStr(self.password),
                "IG_ACCOUNT_TYPE": self.account_type,
            }
        )

    def public(self) -> dict:
        return {
            "name": self.name,
            "username": self.username,
            "account_type": self.account_type,
            "connected": self.connected,
            "account_id": self.account_id,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_error": self.last_error,
            "api_key_masked": self._mask(self.api_key),
            "password_saved": bool(self.password),
        }

    def mark_connected(self, account_id: str | None) -> None:
        self.connected = True
        self.account_id = account_id
        self.last_error = None
        self.last_checked = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        self.connected = False
        self.last_error = error
        self.last_checked = datetime.now(UTC)

    def _mask(self, value: str) -> str:
        if len(value) <= 6:
            return "***" if value else ""
        return f"{value[:3]}...{value[-3:]}"


@dataclass(slots=True)
class BinanceProfile:
    name: str
    api_key: str
    api_secret: str
    environment: str = "DEMO"
    connected: bool = False
    balance: float | None = None
    last_checked: datetime | None = None
    last_error: str | None = None
    active: bool = False

    def settings(self, base: Settings) -> Settings:
        return base.model_copy(
            update={
                "BINANCE_API_KEY": SecretStr(self.api_key),
                "BINANCE_API_SECRET": SecretStr(self.api_secret),
                "BINANCE_ENV": self.environment,
            }
        )

    def public(self) -> dict:
        return {
            "name": self.name,
            "broker": "BINANCE",
            "environment": self.environment,
            "connected": self.connected,
            "balance": self.balance,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_error": self.last_error,
            "active": self.active,
            "api_key_masked": self._mask(self.api_key),
            "secret_saved": bool(self.api_secret),
        }

    def mark_connected(self, balance: float) -> None:
        self.connected = True
        self.balance = balance
        self.last_error = None
        self.last_checked = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        self.connected = False
        self.balance = None
        self.last_error = error
        self.last_checked = datetime.now(UTC)

    def _mask(self, value: str) -> str:
        if len(value) <= 8:
            return "***" if value else ""
        return f"{value[:4]}...{value[-4:]}"


class ProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, IGProfile] = {}
        self._binance_profiles: dict[str, BinanceProfile] = {}

    def upsert_ig(
        self,
        name: str,
        api_key: str,
        username: str,
        password: str,
        account_type: str,
    ) -> IGProfile:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("profile name is required")
        profile = IGProfile(
            name=clean_name,
            api_key=api_key.strip(),
            username=username.strip(),
            password=password,
            account_type=account_type.strip().upper() or "DEMO",
        )
        self._profiles[clean_name] = profile
        return profile

    def get(self, name: str) -> IGProfile:
        profile = self._profiles.get(name)
        if profile is None:
            raise KeyError(name)
        return profile

    def list_public(self) -> list[dict]:
        return [profile.public() for profile in self._profiles.values()]

    def upsert_binance(
        self,
        name: str,
        api_key: str,
        api_secret: str,
        environment: str,
    ) -> BinanceProfile:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("profile name is required")
        clean_environment = environment.strip().upper() or "DEMO"
        if clean_environment != "DEMO":
            raise ValueError("only Binance DEMO profiles are supported")
        if not api_key.strip() or not api_secret:
            raise ValueError("Binance API key and secret are required")
        profile = BinanceProfile(
            name=clean_name,
            api_key=api_key.strip(),
            api_secret=api_secret,
            environment=clean_environment,
        )
        self._binance_profiles[clean_name] = profile
        return profile

    def get_binance(self, name: str) -> BinanceProfile:
        profile = self._binance_profiles.get(name)
        if profile is None:
            raise KeyError(name)
        return profile

    def list_binance_public(self) -> list[dict]:
        return [profile.public() for profile in self._binance_profiles.values()]

    def activate_binance(self, name: str) -> BinanceProfile:
        profile = self.get_binance(name)
        if not profile.connected:
            raise ValueError("test the Binance demo connection before activation")
        for item in self._binance_profiles.values():
            item.active = False
        profile.active = True
        return profile


profile_store = ProfileStore()
