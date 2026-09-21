"""Royal Statistical Society event source."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


EVENTS_URL = "https://rss.org.uk/training-events/events/"
SOURCE_NAME = "Royal Statistical Society"

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "LondonDataRadar/0.1 (+https://tushakova.co.uk)"

EXCLUDED_EVENT_TYPES = frozenset(
    {
        "RSS Training",
    }
)

KNOWN_EVENT_TYPES = frozenset(
    {
        "Conference",
        "Local Group Meeting",
        "Other Event (non-RSS)",
        "RSS Event",
        "RSS Training",
        "Section Group Meeting",
    }
)


class RSSSourceError(RuntimeError):
    """Raised when Royal Statistical Society event data cannot be retrieved."""


@dataclass(frozen=True)
class RawRSSEvent:
    """Event data extracted from RSS before canonical normalisation."""

    title: str
    source_url: str
    date_text: str
    location_text: str
    event_type: str
    price_text: str | None = None


def fetch_page(url: str) -> str:
    """Fetch an RSS page and return decoded HTML."""
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

    except (HTTPError, URLError, TimeoutError) as exc:
        raise RSSSourceError(f"Failed to fetch RSS page {url}: {exc}") from exc


def clean_text(value: str) -> str:
    """Collapse repeated whitespace in source text."""
    return " ".join(value.split())


def parse_events_page(html: str) -> list[RawRSSEvent]:
    """Extract candidate events from the RSS listing page."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[RawRSSEvent] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if "/training-events/events/events-" not in href:
            continue

        title = clean_text(link.get_text(" ", strip=True))

        if not title:
            continue

        container = link.find_parent(["article", "li", "div"])

        if container is None:
            continue

        text = clean_text(container.get_text(" ", strip=True))

        event_type = next(
            (
                event_type
                for event_type in KNOWN_EVENT_TYPES
                if event_type.casefold() in text.casefold()
            ),
            None,
        )

        if event_type is None:
            continue

        date_match = re.search(
            r"\b\d{1,2}\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
            text,
            flags=re.IGNORECASE,
        )

        if date_match is None:
            continue

        date_text = date_match.group(0)

        location_text = text

        for removable in (date_text, title, event_type):
            location_text = location_text.replace(removable, " ")

        location_text = clean_text(location_text)

        events.append(
            RawRSSEvent(
                title=title,
                source_url=urljoin(EVENTS_URL, href),
                date_text=date_text,
                location_text=location_text,
                event_type=event_type,
            )
        )

    return deduplicate_raw_events(events)


def deduplicate_raw_events(events: list[RawRSSEvent]) -> list[RawRSSEvent]:
    """Remove duplicate listing entries using their canonical source URL."""
    unique: dict[str, RawRSSEvent] = {}

    for event in events:
        unique[event.source_url] = event

    return list(unique.values())


def should_include_event(event: RawRSSEvent) -> bool:
    """Return whether an RSS event belongs in London Data Radar."""
    if event.event_type in EXCLUDED_EVENT_TYPES:
        return False

    return "london" in event.location_text.casefold()


def parse_price_text(html: str) -> str | None:
    """Extract simple pricing information from an RSS detail page."""
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))

    free_match = re.search(
        r"\b(?:free of charge|free to attend)\b",
        text,
        flags=re.IGNORECASE,
    )

    if free_match:
        return free_match.group(0)

    return None


def enrich_event(event: RawRSSEvent) -> RawRSSEvent:
    """Add information available only on the RSS detail page."""
    html = fetch_page(event.source_url)

    return RawRSSEvent(
        title=event.title,
        source_url=event.source_url,
        date_text=event.date_text,
        location_text=event.location_text,
        event_type=event.event_type,
        price_text=parse_price_text(html),
    )


def get_events() -> list[RawRSSEvent]:
    """Retrieve relevant London events from RSS."""
    html = fetch_page(EVENTS_URL)
    events = parse_events_page(html)

    relevant_events = [
        event
        for event in events
        if should_include_event(event)
    ]

    return [
        enrich_event(event)
        for event in relevant_events
    ]
