"""Shared HTTP utilities for event ingestion."""

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REQUEST_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "LondonDataRadar/0.1 "
    "(+https://tushakova.co.uk)"
)


class FetchError(RuntimeError):
    """Raised when an event source cannot be retrieved."""


def fetch_html(url: str) -> str:
    """Fetch an HTML page using a bounded network request."""

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            return response.read().decode(
                charset,
                errors="replace",
            )

    except (HTTPError, URLError, TimeoutError) as exc:
        raise FetchError(
            f"Failed to fetch {url}: {exc}"
        ) from exc
