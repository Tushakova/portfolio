"""Royal Statistical Society event ingestion."""

from __future__ import annotations

import re
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.topics import (
    AI_ML,
    CAREERS,
    CAREER_FAIRS,
    DATA_ANALYTICS,
    DATA_SCIENCE,
    STATISTICS,
    is_career_event,
    is_career_fair,
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

        # RSS event detail pages currently live below paths such as:
        # /training-events/events/events-2026/rss-events/event-slug/
        if "/training-events/events/events-20" not in path:
            continue

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        # Ignore broad listing/category pages.
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

    title = clean_text(
        heading.get_text(" ", strip=True)
    )

    if not title:
        raise RSSParseError("event title is empty")

    return title


def extract_event_type(text: str) -> str:
    """Extract the RSS event classification."""
    text_lower = text.casefold()

    for event_type in EVENT_TYPES:
        if event_type.casefold() in text_lower:
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

        return parsed.replace(
            tzinfo=LONDON_TZ
        )

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


def extract_location(
    lines: list[str],
) -> tuple[str | None, str | None]:
    """
    Extract the displayed RSS location.

    RSS pages are not fully consistent about separating venue name
    from address. Preserve the information conservatively rather than
    guessing at an address structure.
    """

    for index, line in enumerate(lines):
        if not line.casefold().startswith("location:"):
            continue

        location = clean_text(
            line.split(":", 1)[1]
        )

        if not location:
            location = None

        detail = None

        if index + 1 < len(lines):
            candidate = clean_text(
                lines[index + 1]
            )

            if (
                candidate
                and candidate not in EVENT_TYPES
                and "date:" not in candidate.casefold()
            ):
                detail = candidate

        # Some RSS pages put only "London" after Location:
        # and the fuller venue/address on the following line.
        if detail and "london" in detail.casefold():
            return location, detail

        return location, None

    raise RSSParseError("event location not found")


def infer_topics(title: str) -> tuple[str, ...]:
    """
    Infer only topics explicitly supported by the event title.

    Deliberately avoid classifying from the entire page because RSS
    navigation and boilerplate contain unrelated data/AI terminology.
    """

    title_lower = title.casefold()
    topics: list[str] = []

    if any(
        term in title_lower
        for term in (
            "data",
            "analytics",
            "analyst",
            "survey",
        )
    ):
        topics.append(DATA_ANALYTICS)

    if any(
        term in title_lower
        for term in (
            "artificial intelligence",
            "machine learning",
        )
    ):
        topics.append(AI_ML)

    if "data science" in title_lower:
        topics.append(DATA_SCIENCE)

    if any(
        term in title_lower
        for term in (
            "statistics",
            "statistical",
        )
    ):
        topics.append(STATISTICS)

    if is_career_event(title):
        topics.append(CAREERS)
    if is_career_fair(title):
        topics.append(CAREER_FAIRS)

    return tuple(
        dict.fromkeys(topics)
    )


def stable_event_id(url: str) -> str:
    """Create a stable ID from the RSS event URL."""
    slug = (
        urlparse(url)
        .path.rstrip("/")
        .split("/")[-1]
    )

    if not slug:
        raise RSSParseError(
            "could not create event ID from URL"
        )

    return f"rss-{slug}"


def parse_event_page(
    html: str,
    source_url: str,
) -> Event | None:
    """Parse one RSS detail page into a canonical Event."""

    lines = page_lines(html)
    text = " ".join(lines)

    event_type = extract_event_type(text)

    # London Data Radar is aimed at accessible events rather than
    # professional paid training courses.
    if event_type == "RSS Training":
        return None

    location, location_detail = extract_location(
        lines
    )

    location_text = " ".join(
        value
        for value in (
            location,
            location_detail,
        )
        if value
    )

    title = extract_title(html)
    has_london_venue = "london" in location_text.casefold()
    has_online = "online" in location_text.casefold() or "virtual" in location_text.casefold()
    if not has_london_venue and not has_online:
        return None
    # Online events should clearly be about the radar's subject rather
    # than generic membership, training or professional administration.
    if not has_london_venue and not infer_topics(title):
        return None
    event_format = "hybrid" if has_london_venue and has_online else (
        "online" if has_online else "in_person"
    )
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

    if "waitlist" in lowered:
        registration_status = "waitlist"
    elif "sold out" in lowered:
        registration_status = "sold_out"
    elif "book now" in lowered:
        registration_status = "open"
    else:
        registration_status = "unknown"

    # RSS does not consistently separate venue and address.
    # Prefer the fuller location string for display when available.
    venue_name = (
        location_detail
        or location
        or None
    )

    address = (
        location_detail
        or location
        or None
    )

    return Event(
        id=stable_event_id(source_url),
        title=title,
        start_at=start_at,
        end_at=end_at,
        format=event_format,
        organiser=SOURCE_NAME,
        source=SOURCE_NAME,
        source_url=source_url,
        venue_name=venue_name,
        address=address,
        is_free=is_free,
        price_from_gbp=price_from_gbp,
        registration_status=registration_status,
        topics=infer_topics(title),
    )


def get_events() -> tuple[list[Event], list[str]]:
    """Discover and ingest relevant RSS events."""

    events: list[Event] = []
    errors: list[str] = []

    try:
        listing_html = fetch_html(EVENTS_URL)
    except FetchError as exc:
        return [], [
            f"{SOURCE_NAME}: {exc}"
        ]

    urls = discover_event_urls(
        listing_html
    )

    # Keep previously verified event facts if one detail page temporarily
    # fails, so an otherwise healthy daily refresh does not erase it.
    cached: dict[str, Event] = {}
    try:
        dataset = json.loads(Path("data/events.json").read_text(encoding="utf-8"))
        for raw in dataset.get("events", []):
            if raw.get("source") == SOURCE_NAME:
                cached[raw["source_url"]] = Event(**{
                    **raw, "topics": tuple(raw.get("topics", []))
                })
    except (OSError, ValueError, TypeError, KeyError):
        pass

    fetched = 0
    failed = 0

    for url in urls:
        try:
            html = fetch_html(url)
            fetched += 1

            event = parse_event_page(
                html,
                url,
            )

            if event is not None:
                events.append(event)

        except (
            FetchError,
            RSSParseError,
            ValueError,
        ) as exc:
            failed += 1
            print(f"WARNING: {SOURCE_NAME} [{url}]: {exc}")
            if url in cached:
                events.append(cached[url])

    if failed and not fetched:
        errors.append(f"{SOURCE_NAME}: all event detail pages failed")

    return events, errors
