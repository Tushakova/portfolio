"""Public event facts from selected London Meetup group pages.

Group pages publish schema.org Event objects. We read only event facts,
never member profiles, RSVPs, or attendees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.structured_data import extract_schema_events
from src.events.topics import ANALYTICS_ENGINEERING, DATA_ANALYTICS, DATA_SCIENCE


LONDON_TZ = ZoneInfo("Europe/London")


@dataclass(frozen=True)
class MeetupGroup:
    slug: str
    organiser: str
    topics: tuple[str, ...]


GROUPS = (
    MeetupGroup("the-friendly-data-meetup", "The Friendly Data Meetup London", (DATA_ANALYTICS,)),
    MeetupGroup("london-analytics-engineering-meetup", "London Analytics Engineering Meetup", (ANALYTICS_ENGINEERING,)),
    MeetupGroup("london-data-intelligence-network", "London Data Intelligence Network", (DATA_ANALYTICS, DATA_SCIENCE)),
    MeetupGroup("london-dbt-meetup", "London dbt Meetup", (ANALYTICS_ENGINEERING,)),
)


def parse_event(item: dict, group: MeetupGroup, now: datetime | None = None) -> Event | None:
    """Accept only future, scheduled, in-person London events with full facts."""
    url = item.get("url", "")
    if not isinstance(url, str) or urlparse(url).netloc != "www.meetup.com":
        return None
    match = re.fullmatch(rf"/{re.escape(group.slug)}/events/(\d+)/?", urlparse(url).path)
    if not match:
        return None
    if item.get("eventStatus") != "https://schema.org/EventScheduled":
        return None
    if item.get("eventAttendanceMode") != "https://schema.org/OfflineEventAttendanceMode":
        return None

    location = item.get("location")
    if not isinstance(location, dict):
        return None
    address = location.get("address")
    if not isinstance(address, dict) or str(address.get("addressLocality", "")).casefold() != "london":
        return None

    try:
        start = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(item["endDate"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError, TypeError):
        return None
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        return None
    if end <= (now or datetime.now(timezone.utc)):
        return None
    title = item.get("name")
    if not isinstance(title, str) or not title.strip():
        return None

    free = item.get("isAccessibleForFree")
    if not isinstance(free, bool):
        free = None

    return Event(
        id=f"meetup-{match.group(1)}",
        title=title.strip(),
        start_at=start.astimezone(LONDON_TZ).isoformat(),
        end_at=end.astimezone(LONDON_TZ).isoformat(),
        format="in_person",
        organiser=group.organiser,
        source="Meetup",
        source_url=f"https://www.meetup.com/{group.slug}/events/{match.group(1)}/",
        venue_name=location.get("name") or None,
        address=address.get("streetAddress") or None,
        is_free=free,
        price_from_gbp=0.0 if free else None,
        registration_status="unknown",
        topics=group.topics,
    )


def get_events() -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    errors: list[str] = []
    for group in GROUPS:
        url = f"https://www.meetup.com/{group.slug}/"
        try:
            for item in extract_schema_events(fetch_html(url)):
                event = parse_event(item, group)
                if event is not None:
                    events.append(event)
        except (FetchError, ValueError) as exc:
            errors.append(f"Meetup [{group.slug}]: {exc}")
    return events, errors
