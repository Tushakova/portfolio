"""Ingestion for standalone event websites."""

from __future__ import annotations

from dataclasses import dataclass

from src.events.http import fetch_html


@dataclass(frozen=True)
class EventPage:
    """A known event page awaiting extraction."""

    url: str
    source: str


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


def fetch_event_pages() -> list[tuple[EventPage, str]]:
    """Fetch configured standalone event pages."""

    pages: list[tuple[EventPage, str]] = []

    for event_page in EVENT_PAGES:
        html = fetch_html(event_page.url)
        pages.append((event_page, html))

    return pages
