"""Canonical event model used by London Data Radar."""

from dataclasses import asdict, dataclass
from typing import Literal


EventFormat = Literal["in_person", "online", "hybrid"]

EventStatus = Literal[
    "scheduled",
    "cancelled",
    "postponed",
]

RegistrationStatus = Literal[
    "open",
    "waitlist",
    "sold_out",
    "closed",
    "unknown",
]


@dataclass(frozen=True)
class Event:
    """Source-independent representation of an event."""

    id: str
    title: str
    start_at: str
    format: EventFormat
    organiser: str
    source: str
    source_url: str

    end_at: str | None = None

    venue_name: str | None = None
    address: str | None = None

    is_free: bool | None = None
    price_from_gbp: float | None = None

    registration_status: RegistrationStatus = "unknown"

    topics: tuple[str, ...] = ()
    status: EventStatus = "scheduled"
    time_tbc: bool = False

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation."""
        data = asdict(self)
        data["topics"] = list(self.topics)
        return data
