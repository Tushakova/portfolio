"""Data Science Festival event source."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EVENTS_URL = "https://datasciencefestival.com/events/"
SOURCE_NAME = "Data Science Festival"

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "LondonDataRadar/0.1 (+https://tushakova.co.uk)"


class DSFSourceError(RuntimeError):
    """Raised when Data Science Festival data cannot be retrieved."""


@dataclass(frozen=True)
class RawDSFEvent:
    """Event data extracted from Data Science Festival before normalisation."""

    title: str
    source_url: str
    date_text: str | None = None
    location_text: str | None = None
    price_text: str | None = None


def fetch_events_page() -> str:
    """Fetch the Data Science Festival events page."""
    request = Request(
        EVENTS_URL,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

    except (HTTPError, URLError, TimeoutError) as exc:
        raise DSFSourceError(
            f"Failed to fetch Data Science Festival events: {exc}"
        ) from exc


def parse_events_page(html: str) -> list[RawDSFEvent]:
    """Extract event records from Data Science Festival HTML."""
    raise NotImplementedError("DSF parser has not been implemented yet.")


def get_events() -> list[RawDSFEvent]:
    """Retrieve raw events from Data Science Festival."""
    html = fetch_events_page()
    return parse_events_page(html)
