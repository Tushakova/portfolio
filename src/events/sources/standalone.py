"""Ingestion for standalone event websites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.events.http import FetchError, fetch_html
from src.events.structured_data import extract_schema_events


@dataclass(frozen=True)
class EventPage:
    """A known standalone event page."""

    url: str
    source: str


@dataclass(frozen=True)
class StandaloneResult:
    """Result of attempting to extract events from one page."""

    page: EventPage
    events: tuple[dict[str, Any], ...]
    error: str | None = None


EVENT_PAGES = (
    EventPage(
        url="https://london.measurecamp.org/registration/",
        source="MeasureCamp London",
    ),
    EventPage(
        url="https://www.bigdataldn.com/",
        source="Big Data LDN",
    ),
)


def ingest_page(page: EventPage) -> StandaloneResult:
    """Fetch a standalone page and extract structured events."""
    try:
        html = fetch_html(page.url)
    except FetchError as exc:
        return StandaloneResult(
            page=page,
            events=(),
            error=str(exc),
        )

    events = tuple(extract_schema_events(html))

    if not events:
        return StandaloneResult(
            page=page,
            events=(),
            error="No schema.org Event data found",
        )

    return StandaloneResult(
        page=page,
        events=events,
    )


def get_events() -> list[StandaloneResult]:
    """Attempt ingestion for all configured standalone pages."""
    return [
        ingest_page(page)
        for page in EVENT_PAGES
    ]
