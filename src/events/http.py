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


def fetch_html(url: str, *, timeout: int = REQUEST_TIMEOUT_SECONDS,
               attempts: int = 2, max_bytes: int | None = None) -> str:
    """Fetch an HTML page using a bounded network request."""

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    for attempt in range(attempts):
        try:
            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                charset = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )

                raw = response.read(max_bytes + 1) if max_bytes else response.read()
                if max_bytes and len(raw) > max_bytes:
                    raise FetchError("Page exceeds the inspection size limit")
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            # An unavailable page is not repaired by an immediate retry.
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt == attempts - 1:
                raise FetchError(f"Failed to fetch {url}: {exc}") from exc
