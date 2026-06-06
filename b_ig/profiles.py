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


class ProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, IGProfile] = {}

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


profile_store = ProfileStore()

