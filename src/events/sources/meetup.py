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
from src.events.topics import (
    ANALYTICS_ENGINEERING, CAREERS, DATA_ANALYTICS, DATA_SCIENCE,
    EXPERIMENTATION, STATISTICS, CAREER_FAIRS, is_career_event, is_career_fair,
)


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
    MeetupGroup("data-science-festival-london", "Data Science Festival", (DATA_ANALYTICS, DATA_SCIENCE)),
    MeetupGroup("data-pub-social", "Data Pub Social", (DATA_ANALYTICS, DATA_SCIENCE)),
    MeetupGroup("crap-talks-cro-analytics-product-london", "CRAP Talks: CRO, Analytics & Product", (DATA_ANALYTICS,)),
)

# Public London-wide listings discover events from groups outside GROUPS.
# We still validate every event's topic, venue/mode and date below.
SEARCH_URLS = (
    "https://www.meetup.com/find/gb--london/data-science/",
    "https://www.meetup.com/find/?keywords=analytics&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/gb--london/machine-learning/",
    "https://www.meetup.com/find/?keywords=data%20career&location=gb--london&source=EVENTS",
)

TECHNICAL_TITLE = re.compile(
    r"\b(?:data\s+(?:science|analys(?:is|t|ts)|analytics|visuali[sz]ation)|"
    r"analytics?|experimentation|a/b\s+test(?:ing)?|conversion|"
    r"cro|optimi[sz]ation|statistics?|statistical|"
    r"bayesian|power\s*bi|tableau|dbt|databricks|pytorch|"
    r"sql|python|machine\s+learning|product\s+insights?)\b",
    re.IGNORECASE,
)
LOW_VALUE_TITLE = re.compile(
    r"\b(?:internship|training\s+day|certification|bootcamp|"
    r"public\s+speaking|global\s+(?:virtual\s+)?networking|jobexpo)\b",
    re.IGNORECASE,
)


def london_place(location: object) -> dict | None:
    """Return a verified physical London venue, if one is published."""
    places = location if isinstance(location, list) else [location]
    for place in places:
        if not isinstance(place, dict) or place.get("@type") != "Place":
            continue
        address = place.get("address")
        if isinstance(address, dict) and str(address.get("addressLocality", "")).casefold() == "london":
            return place
    return None


def discovered_topics(title: str) -> tuple[str, ...]:
    """Assign search-result topics from visible titles, not the search query."""
    if re.search(r"data science|pytorch|machine learning", title, re.I):
        base = DATA_SCIENCE
    elif re.search(r"experimentation|a/b\s+test|\bcro\b|conversion|optimi[sz]ation", title, re.I):
        base = EXPERIMENTATION
    elif re.search(r"statistic|bayesian", title, re.I):
        base = STATISTICS
    else:
        base = DATA_ANALYTICS
    return (base,)


def parse_event(item: dict, group: MeetupGroup, now: datetime | None = None,
                discovered: bool = False) -> Event | None:
    """Validate relevance and a future scheduled London or online event."""
    url = item.get("url", "")
    if not isinstance(url, str) or urlparse(url).netloc != "www.meetup.com":
        return None
    match = re.fullmatch(rf"/{re.escape(group.slug)}/events/(\d+)/?", urlparse(url).path)
    if not match:
        return None
    if item.get("eventStatus") != "https://schema.org/EventScheduled":
        return None
    mode = item.get("eventAttendanceMode")
    formats = {
        "https://schema.org/OfflineEventAttendanceMode": "in_person",
        "https://schema.org/OnlineEventAttendanceMode": "online",
        "https://schema.org/MixedEventAttendanceMode": "hybrid",
    }
    event_format = formats.get(mode)
    if event_format is None:
        return None

    location = item.get("location")
    physical = london_place(location)
    if event_format != "online" and physical is None:
        return None
    if event_format == "online":
        locations = location if isinstance(location, list) else [location]
        if not any(isinstance(loc, dict) and loc.get("@type") == "VirtualLocation"
                   for loc in locations):
            return None

    try:
        start = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError, TypeError):
        return None
    end_text = item.get("endDate")
    try:
        end = datetime.fromisoformat(end_text.replace("Z", "+00:00")) if end_text else None
    except (AttributeError, ValueError, TypeError):
        return None
    if start.tzinfo is None or (end is not None and (end.tzinfo is None or end <= start)):
        return None
    current = now or datetime.now(timezone.utc)
    if (end is not None and end <= current) or (
        end is None and start.astimezone(LONDON_TZ).date() < current.astimezone(LONDON_TZ).date()
    ):
        return None
    title = item.get("name")
    if not isinstance(title, str) or not title.strip():
        return None
    if LOW_VALUE_TITLE.search(title):
        return None
    if re.search(r"\b(?:investors?|startups?)\b", title, re.I) and \
            re.search(r"\bnetworking\b", title, re.I):
        return None
    # Curated groups can publish a generic series title, but independent
    # groups discovered by the search index must explicitly name the topic.
    if discovered and not TECHNICAL_TITLE.search(title):
        return None
    if not discovered and not (TECHNICAL_TITLE.search(title) or
                               re.search(r"\bdata\b", title, re.I) or
                               is_career_event(title) or
                               (re.search(r"\b(?:meetup|talks)\b", title, re.I)
                                and TECHNICAL_TITLE.search(group.organiser))):
        return None

    organiser = item.get("organizer")
    organiser_name = (organiser.get("name") if isinstance(organiser, dict) else None)
    if not isinstance(organiser_name, str) or not organiser_name.strip():
        organiser_name = group.organiser
    address = physical.get("address") if physical else None
    address = address if isinstance(address, dict) else {}

    free = item.get("isAccessibleForFree")
    if not isinstance(free, bool):
        free = None

    return Event(
        id=f"meetup-{match.group(1)}",
        title=title.strip(),
        start_at=start.astimezone(LONDON_TZ).isoformat(),
        end_at=end.astimezone(LONDON_TZ).isoformat() if end else None,
        format=event_format,
        organiser=organiser_name,
        source="Meetup",
        source_url=f"https://www.meetup.com/{group.slug}/events/{match.group(1)}/",
        venue_name=(physical.get("name") or None) if physical else None,
        address=address.get("streetAddress") or None,
        is_free=free,
        price_from_gbp=0.0 if free else None,
        registration_status="unknown",
        topics=group.topics + ((CAREERS,) if is_career_event(title) else ())
        + ((CAREER_FAIRS,) if is_career_fair(title) else ()),
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
    for search_url in SEARCH_URLS:
        try:
            for item in extract_schema_events(fetch_html(search_url)):
                url = item.get("url", "")
                if not isinstance(url, str):
                    continue
                match = re.fullmatch(r"/([^/]+)/events/\d+/?", urlparse(url).path)
                if not match:
                    continue
                organiser = item.get("organizer")
                name = organiser.get("name") if isinstance(organiser, dict) else None
                title = item.get("name")
                if not isinstance(title, str):
                    continue
                group = MeetupGroup(match.group(1), name or "Meetup", discovered_topics(title))
                event = parse_event(item, group, discovered=True)
                if event is not None:
                    events.append(event)
        except (FetchError, ValueError) as exc:
            errors.append(f"Meetup discovery [{search_url}]: {exc}")
    return events, errors
