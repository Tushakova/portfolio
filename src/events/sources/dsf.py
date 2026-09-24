"""Discover future data-career days on the organiser's own website.

The organiser's main page has a separate Upcoming/Past navigation. We
check actual dates on detail pages, so old career-day navigation links never
become upcoming events just because they are still indexed or linked.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.topics import CAREERS, DATA_ANALYTICS, DATA_SCIENCE

BASE_URL = "https://datasciencefestival.com/"
INDEX_URLS = (BASE_URL, urljoin(BASE_URL, "events/"))
LONDON_TZ = ZoneInfo("Europe/London")


class DSFParseError(ValueError):
    """An advertised career event lacks a verifiable date or location."""


def discover_career_urls(html: str) -> set[str]:
    """Only discover career-day detail pages on the organiser's domain."""
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()
    for link in soup.select("a[href]"):
        url = urljoin(BASE_URL, link["href"])
        parsed = urlparse(url)
        if parsed.netloc != "datasciencefestival.com":
            continue
        if not re.fullmatch(r"/event/career-day-20\d{2}/?", parsed.path):
            continue
        urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/")
    return urls


def parse_career_day(html: str, url: str, now: datetime | None = None) -> Event | None:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h3", string=re.compile(r"Career Day 20\d{2}", re.I))
    if heading is None:
        raise DSFParseError(f"Career day heading missing: {url}")
    # The first text after the event heading contains the primary event date
    # and venue. Ignore the many dates of individual talks further down.
    event_intro = heading.parent.get_text(" ", strip=True)[:350]
    match = re.search(
        r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})"
        r"\s*\|\s*([^|.]{1,90}?London)\b",
        event_intro,
        re.IGNORECASE,
    )
    if match is None:
        raise DSFParseError(f"Career day date or London venue missing: {url}")
    try:
        date = datetime.strptime(" ".join(match.group(i) for i in (1, 2, 3)), "%d %B %Y")
    except ValueError as exc:
        raise DSFParseError(f"Invalid career day date: {url}") from exc
    start = date.replace(tzinfo=LONDON_TZ)
    if start.date() < (now or datetime.now(LONDON_TZ)).astimezone(LONDON_TZ).date():
        return None
    title = f"DSF Career Day {match.group(3)}"
    return Event(
        id=f"dsf-career-day-{match.group(3)}",
        title=title,
        start_at=start.isoformat(),
        end_at=None,
        format="in_person",
        organiser="Data Science Festival",
        source="Data Science Festival",
        source_url=url,
        venue_name=match.group(4).strip(),
        is_free=None,
        registration_status="unknown",
        topics=(CAREERS, DATA_ANALYTICS, DATA_SCIENCE),
        time_tbc=True,
    )


def get_events() -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    errors: list[str] = []
    urls: set[str] = set()
    for listing in INDEX_URLS:
        try:
            urls.update(discover_career_urls(fetch_html(listing)))
        except FetchError as exc:
            errors.append(f"Data Science Festival listing: {exc}")
    current_year = datetime.now(LONDON_TZ).year
    for url in sorted(urls):
        year = int(re.search(r"career-day-(20\d{2})", url).group(1))
        if year < current_year:
            continue
        try:
            event = parse_career_day(fetch_html(url), url)
            if event is not None:
                events.append(event)
        except (FetchError, DSFParseError) as exc:
            errors.append(f"Data Science Festival career day: {exc}")
    return events, errors
