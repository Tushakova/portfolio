
"""Royal Statistical Society event ingestion."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.topics import (
    AI_ML,
    DATA_ANALYTICS,
    DATA_SCIENCE,
    STATISTICS,
)


EVENTS_URL = "https://rss.org.uk/training-events/events/"
SOURCE_NAME = "Royal Statistical Society"

LONDON_TZ = ZoneInfo("Europe/London")

EVENT_TYPES = (
    "RSS Event",
    "Section Group Meeting",
    "Local Group Meeting",
    "Other Event (non-RSS)",
    "Conference",
    "RSS Training",
)


class RSSParseError(RuntimeError):
    """Raised when an RSS event page cannot be parsed safely."""


def clean_text(value: str) -> str:
    """Collapse repeated whitespace."""
    return " ".join(value.split())


def page_lines(html: str) -> list[str]:
    """Return non-empty visible-text lines from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")

    return [
        clean_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if clean_text(line)
    ]


def discover_event_urls(html: str) -> list[str]:
    """Discover unique RSS event detail URLs from the listing page."""
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        absolute_url = urljoin(EVENTS_URL, link["href"])
        path = urlparse(absolute_url).path.casefold()

        if "/training-events/events/events-20" not in path:
            continue

        # Category/listing pages end at a broad event-type path.
        # Real event pages have a deeper slug.
        parts = [
            part
            for part in path.split("/")
            if part
        ]

        if len(parts) < 5:
            continue

        urls.add(absolute_url)

    return sorted(urls)


def extract_title(html: str) -> str:
    """Extract the event title."""
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find(["h1", "h2"])

    if heading is None:
        raise RSSParseError("event title not found")

    title = clean_text(heading.get_text(" ", strip=True))

    if not title:
        raise RSSParseError("event title is empty")

    return title


def extract_event_type(text: str) -> str:
    """Extract the RSS event classification."""
    for event_type in EVENT_TYPES:
        if event_type.casefold() in text.casefold():
            return event_type

    raise RSSParseError("event type not found")


def extract_datetimes(
    text: str,
) -> tuple[str, str | None]:
    """Extract timezone-aware start and end timestamps."""

    match = re.search(
        r"Date:\s*"
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}),\s*"
        r"(\d{1,2}[.:]\d{2})\s*(AM|PM)"
        r"(?:\s*-\s*"
        r"(\d{1,2}[.:]\d{2})\s*(AM|PM))?",
        text,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise RSSParseError("event date/time not found")

    date_text = match.group(1)

    def parse_time(
        time_text: str,
        meridiem: str,
    ) -> datetime:
        normalised_time = time_text.replace(".", ":")

        parsed = datetime.strptime(
            f"{date_text} {normalised_time} {meridiem.upper()}",
            "%d %B %Y %I:%M %p",
        )

        return parsed.replace(tzinfo=LONDON_TZ)

    start = parse_time(
        match.group(2),
        match.group(3),
    )

    end = None

    if match.group(4) and match.group(5):
        end = parse_time(
            match.group(4),
            match.group(5),
        )

    return (
        start.isoformat(),
        end.isoformat() if end else None,
    )


def extract_location(lines: list[str]) -> tuple[str, str | None]:
    """Extract the displayed RSS location."""

    for index, line in enumerate(lines):
        if not line.casefold().startswith("location:"):
            continue

        location = clean_text(
            line.split(":", 1)[1]
        )

        address = None

        # RSS sometimes puts the fuller venue/address on the next line.
        if index + 1 < len(lines):
            candidate = lines[index + 1]

            if candidate not in EVENT_TYPES:
                if (
                    "london" in candidate.casefold()
                    and candidate != location
                ):
                    address = candidate

        return location, address

    raise RSSParseError("event location not found")


def infer_topics(title: str, text: str) -> tuple[str, ...]:
    """Assign controlled topics using conservative deterministic rules."""

    haystack = f"{title} {text}".casefold()
    topics: list[str] = []

    if any(
        term in haystack
        for term in (
            "data",
            "analytics",
            "analyst",
            "survey",
        )
    ):
        topics.append(DATA_ANALYTICS)

    if any(
        term in haystack
        for term in (
            "artificial intelligence",
            " ai ",
            "machine learning",
        )
    ):
        topics.append(AI_ML)

    if "data science" in haystack:
        topics.append(DATA_SCIENCE)

    if any(
        term in haystack
        for term in (
            "statistics",
            "statistical",
            "statistician",
        )
    ):
        topics.append(STATISTICS)

    return tuple(dict.fromkeys(topics))


def stable_event_id(url: str) -> str:
    """Create a stable ID from the RSS event URL."""
    slug = urlparse(url).path.rstrip("/").split("/")[-1]

    return f"rss-{slug}"


def parse_event_page(
    html: str,
    source_url: str,
) -> Event | None:
    """Parse one RSS detail page into a canonical Event."""

    lines = page_lines(html)
    text = " ".join(lines)

    event_type = extract_event_type(text)

    # Product rule: expensive professional training is not Radar content.
    if event_type == "RSS Training":
        return None

    location, address = extract_location(lines)

    # V1 is specifically London in-person discovery.
    if "london" not in f"{location} {address or ''}".casefold():
        return None

    title = extract_title(html)
    start_at, end_at = extract_datetimes(text)

    lowered = text.casefold()

    is_free: bool | None = None
    price_from_gbp: float | None = None

    if (
        "free of charge" in lowered
        or "free to attend" in lowered
    ):
        is_free = True
        price_from_gbp = 0.0

    registration_status = (
        "open"
        if "book now" in lowered
        else "unknown"
    )

    return Event(
        id=stable_event_id(source_url),
        title=title,
        start_at=start_at,
        end_at=end_at,
        format="in_person",
        organiser=SOURCE_NAME,
        source=SOURCE_NAME,
        source_url=source_url,
        venue_name=location,
        address=address,
        is_free=is_free,
        price_from_gbp=price_from_gbp,
        registration_status=registration_status,
        topics=infer_topics(title, text),
    )


def get_events() -> tuple[list[Event], list[str]]:
    """Discover and ingest relevant RSS events."""

    events: list[Event] = []
    errors: list[str] = []

    try:
        listing_html = fetch_html(EVENTS_URL)
    except FetchError as exc:
        return [], [f"{SOURCE_NAME}: {exc}"]

    urls = discover_event_urls(listing_html)

    for url in urls:
        try:
            html = fetch_html(url)
            event = parse_event_page(html, url)

            if event is not None:
                events.append(event)

        except (FetchError, RSSParseError, ValueError) as exc:
            errors.append(
                f"{SOURCE_NAME} [{url}]: {exc}"
            )

    return events, errors
