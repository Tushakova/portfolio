"""Royal Statistical Society event source."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EVENTS_URL = "https://rss.org.uk/training-events/events/"
SOURCE_NAME = "Royal Statistical Society"

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "LondonDataRadar/0.1 (+https://tushakova.co.uk)"

EXCLUDED_EVENT_TYPES = frozenset(
    {
        "RSS Training",
    }
)


class RSSSourceError(RuntimeError):
    """Raised when Royal Statistical Society data cannot be retrieved."""


@dataclass(frozen=True)
class RawRSSEvent:
    """Event data extracted from RSS before normalisation."""

    title: str
    source_url: str
    date_text: str
    location_text: str
    event_type: str

    price_text: str | None = None


def should_include_event(event: RawRSSEvent) -> bool:
    """Return whether an RSS event is relevant to London Data Radar."""
    if event.event_type in EXCLUDED_EVENT_TYPES:
        return False

    location = event.location_text.casefold()

    return "london" in location


def fetch_events_page() -> str:
    """Fetch the RSS events listing page."""
    request = Request(
        EVENTS_URL,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

    except (HTTPError, URLError, TimeoutError) as exc:
        raise RSSSourceError(
            f"Failed to fetch Royal Statistical Society events: {exc}"
        ) from exc


def parse_events_page(html: str) -> list[RawRSSEvent]:
    """Extract relevant event records from RSS HTML."""
    raise NotImplementedError("RSS parser has not been implemented yet.")


def get_events() -> list[RawRSSEvent]:
    """Retrieve relevant raw RSS events."""
    html = fetch_events_page()
    events = parse_events_page(html)

    return [
        event
        for event in events
        if should_include_event(event)
    ]
