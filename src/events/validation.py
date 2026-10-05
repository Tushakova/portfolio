"""Validation and deduplication for canonical events."""

from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urlsplit, parse_qsl, urlencode

from src.events.models import Event
from src.events.topics import ALL_TOPICS


class EventValidationError(ValueError):
    """Raised when canonical event data violates the contract."""


def parse_timestamp(
    value: str,
    field_name: str,
    event_id: str,
) -> datetime:
    """Parse and validate a timezone-aware ISO timestamp."""

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EventValidationError(
            f"{event_id}: invalid {field_name}: {value}"
        ) from exc

    if timestamp.tzinfo is None:
        raise EventValidationError(
            f"{event_id}: {field_name} must include a timezone"
        )

    return timestamp


def validate_event(event: Event) -> None:
    """Validate one canonical event."""

    if not event.id.strip():
        raise EventValidationError("event ID cannot be empty")

    if not event.title.strip():
        raise EventValidationError(
            f"{event.id}: title cannot be empty"
        )

    if event.format not in ("in_person", "online", "hybrid"):
        raise EventValidationError(f"{event.id}: unknown event format")

    if not event.source_url.startswith(("http://", "https://")):
        raise EventValidationError(
            f"{event.id}: invalid source URL"
        )

    start = parse_timestamp(
        event.start_at,
        "start_at",
        event.id,
    )

    if event.end_at is not None:
        end = parse_timestamp(
            event.end_at,
            "end_at",
            event.id,
        )

        if end <= start:
            raise EventValidationError(
                f"{event.id}: end_at must be after start_at"
            )

    unknown_topics = set(event.topics) - ALL_TOPICS

    if unknown_topics:
        raise EventValidationError(
            f"{event.id}: unknown topics: "
            f"{sorted(unknown_topics)}"
        )

    if event.is_free is True:
        if event.price_from_gbp not in (None, 0, 0.0):
            raise EventValidationError(
                f"{event.id}: free event cannot have a positive price"
            )

    if (
        event.price_from_gbp is not None
        and event.price_from_gbp < 0
    ):
        raise EventValidationError(
            f"{event.id}: price cannot be negative"
        )


def validate_events(events: list[Event]) -> None:
    """Validate a complete event collection."""

    seen_ids: set[str] = set()

    for event in events:
        validate_event(event)

        if event.id in seen_ids:
            raise EventValidationError(
                f"duplicate event ID: {event.id}"
            )

        seen_ids.add(event.id)


def deduplicate_events(events: list[Event]) -> list[Event]:
    """Remove exact URL duplicates while preserving first occurrence."""

    unique: list[Event] = []
    seen_urls: set[tuple] = set()
    seen_online: set[tuple] = set()

    for event in events:
        parts = urlsplit(event.source_url)
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query)
                                 if not k.lower().startswith("utm_")
                                 and k.lower() not in {"gclid", "fbclid", "msclkid"}))
        url = (parts.hostname or "").lower().removeprefix("www.") + parts.path.rstrip("/") + "?" + query
        instant = datetime.fromisoformat(event.start_at)
        key = (url, instant)
        title = re.sub(r"\W+", " ", event.title.casefold()).strip()
        end = datetime.fromisoformat(event.end_at) if event.end_at else None
        online_key = (title, instant, end)
        online_duplicate = event.format == "online" and len(title) >= 20 and online_key in seen_online
        if key in seen_urls or online_duplicate:
            continue

        seen_urls.add(key)
        if event.format == "online" and len(title) >= 20:
            seen_online.add(online_key)
        unique.append(event)

    return unique
