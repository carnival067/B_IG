from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

HIGH_IMPACT_KEYWORDS = ("FOMC", "CPI", "NFP", "INTEREST RATE", "RATE DECISION")


@dataclass(slots=True)
class NewsEvent:
    name: str
    starts_at: datetime
    impact: str = "HIGH"


class NewsFilter:
    def __init__(self, pause_minutes: int = 30) -> None:
        self.pause = timedelta(minutes=pause_minutes)
        self.events: list[NewsEvent] = []

    def set_events(self, events: list[NewsEvent]) -> None:
        self.events = events

    def blocked(self, now: datetime) -> bool:
        for event in self.events:
            high_impact = event.impact.upper() == "HIGH" or any(
                key in event.name.upper() for key in HIGH_IMPACT_KEYWORDS
            )
            if high_impact and event.starts_at - self.pause <= now <= event.starts_at + self.pause:
                return True
        return False
