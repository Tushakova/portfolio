"""Ingestion for selected standalone event websites."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.topics import (
    AI_ML,
    DATA_ANALYTICS,
    DATA_ENGINEERING,
)


LONDON_TZ = ZoneInfo("Europe/London")


@dataclass(frozen=True)
class EventPage:
    """Configuration for a standalone event website."""

    url: str
    source: str
    parser: Callable[[str, str], Event]


class EventParseError(RuntimeError):
    """Raised when a known event page no longer matches expectations."""


def page_text(html: str) -> str:
    """Return visible page text with whitespace normalised."""
    soup = BeautifulSoup(html, "html.parser")
    return " ".join(soup.stripped_strings)


def london_datetime(
    value: str,
    date_format: str,
) -> str:
    """Parse a London local datetime and return timezone-aware ISO 8601."""
    parsed = datetime.strptime(value, date_format)
    return parsed.replace(tzinfo=LONDON_TZ).isoformat()


def require_match(
    pattern: str,
    text: str,
    description: str,
    flags: int = re.IGNORECASE,
) -> re.Match[str]:
    """Return a required regex match or fail loudly."""
    match = re.search(pattern, text, flags)

    if match is None:
        raise EventParseError(
            f"Could not extract {description}"
        )

    return match


def parse_measurecamp(html: str, source_url: str) -> Event:
    """Parse the current MeasureCamp London event."""

    text = page_text(html)

    date_match = require_match(
        r"Saturday\s+(\d{1,2}\s+[A-Za-z]{3},?\s+\d{4})",
        text,
        "MeasureCamp date",
    )

    time_match = require_match(
        r"Starting at\s+(\d{1,2}\.\d{2})\s*am",
        text,
        "MeasureCamp start time",
    )

    venue_match = require_match(
        r"(Etc Venues Fenchurch Street)",
        text,
        "MeasureCamp venue",
    )

    address_match = require_match(
        r"(8 Fenchurch Pl,\s*London\s+EC3M\s+4PB)",
        text,
        "MeasureCamp address",
    )

    date_text = date_match.group(1).replace(",", "")
    time_text = time_match.group(1).replace(".", ":")

    start_at = london_datetime(
        f"{date_text} {time_text}",
        "%d %b %Y %H:%M",
    )

    lowered = text.casefold()

    if "waitlist" in lowered:
        registration_status = "waitlist"
    elif "sold out" in lowered:
        registration_status = "sold_out"
    else:
        registration_status = "unknown"

    is_free = (
        "free-to-attend" in lowered
        or "free to attend" in lowered
    )

    return Event(
        id="measurecamp-london-19-2026",
        title="MeasureCamp London 19",
        start_at=start_at,
        end_at=None,
        format="in_person",
        organiser="MeasureCamp London",
        source="MeasureCamp London",
        source_url=source_url,
        venue_name=venue_match.group(1),
        address=address_match.group(1),
        is_free=is_free,
        price_from_gbp=0.0 if is_free else None,
        registration_status=registration_status,
        topics=(DATA_ANALYTICS,),
    )


def parse_big_data_ldn(html: str, source_url: str) -> Event:
    """Parse the current Big Data LDN event."""

    text = page_text(html)

    dates_match = require_match(
        r"23[\s–-]+24\s+September\s+2026",
        text,
        "Big Data LDN dates",
    )

    require_match(
        r"Olympia(?:,)?\s+London",
        text,
        "Big Data LDN venue",
    )

    price_match = require_match(
        r"BDL Visitor Pass.*?£\s*(\d+(?:\.\d+)?)",
        text,
        "Big Data LDN visitor price",
    )

    address_match = require_match(
        r"(Hammersmith Road\s+London\s+W14\s+8UX)",
        text,
        "Big Data LDN address",
    )

    # Opening hours published for Wednesday and Thursday.
    start_at = london_datetime(
        "23 September 2026 09:00",
        "%d %B %Y %H:%M",
    )

    end_at = london_datetime(
        "24 September 2026 17:30",
        "%d %B %Y %H:%M",
    )

    price = float(price_match.group(1))

    return Event(
        id="big-data-ldn-2026",
        title="Big Data LDN 2026",
        start_at=start_at,
        end_at=end_at,
        format="in_person",
        organiser="Big Data LDN",
        source="Big Data LDN",
        source_url=source_url,
        venue_name="Olympia London",
        address=address_match.group(1),
        is_free=False,
        price_from_gbp=price,
        registration_status="open",
        topics=(
            DATA_ANALYTICS,
            AI_ML,
            DATA_ENGINEERING,
        ),
    )


EVENT_PAGES = (
    EventPage(
        url="https://london.measurecamp.org/registration/",
        source="MeasureCamp London",
        parser=parse_measurecamp,
    ),
    EventPage(
        url="https://www.bigdataldn.com/",
        source="Big Data LDN",
        parser=parse_big_data_ldn,
    ),
)


def get_events() -> tuple[list[Event], list[str]]:
    """Retrieve canonical events from configured standalone sources."""

    events: list[Event] = []
    errors: list[str] = []

    for page in EVENT_PAGES:
        try:
            html = fetch_html(page.url)
            event = page.parser(html, page.url)
            events.append(event)

        except (FetchError, EventParseError) as exc:
            errors.append(f"{page.source}: {exc}")

    return events, errors


def main() -> None:
    """Run standalone ingestion as a diagnostic."""

    events, errors = get_events()

    for event in events:
        print(f"\n✓ {event.title}")
        print(f"  Start:        {event.start_at}")
        print(f"  End:          {event.end_at}")
        print(f"  Venue:        {event.venue_name}")
        print(f"  Address:      {event.address}")
        print(f"  Free:         {event.is_free}")
        print(f"  Price from:   {event.price_from_gbp}")
        print(f"  Registration: {event.registration_status}")
        print(f"  Topics:       {', '.join(event.topics)}")

    for error in errors:
        print(f"\n✗ {error}")

    print(
        f"\nResult: {len(events)} event(s), "
        f"{len(errors)} error(s)"
    )


if __name__ == "__main__":
    main()
