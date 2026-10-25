"""Public event facts from selected London Meetup group pages.

Group pages publish schema.org Event objects. We read only event facts,
never member profiles, RSVPs, or attendees.
"""

from __future__ import annotations

import re
import ipaddress
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.structured_data import extract_schema_events
from src.events.topics import (
    ANALYTICS_ENGINEERING, CAREERS, DATA_ANALYTICS, DATA_SCIENCE, DATA_ENGINEERING,
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
    MeetupGroup("experimentation-london", "Experimentation London Meetup", (EXPERIMENTATION,)),
)

# Public London-wide listings discover events from groups outside GROUPS.
# We still validate every event's topic, venue/mode and date below.
SEARCH_URLS = (
    "https://www.meetup.com/find/gb--london/data-science/",
    "https://www.meetup.com/find/?keywords=analytics&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/gb--london/machine-learning/",
    "https://www.meetup.com/find/?keywords=data%20career&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/?keywords=experimentation&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/?keywords=A%2FB%20testing&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/?keywords=conversion%20rate%20optimisation&location=gb--london&source=EVENTS",
    "https://www.meetup.com/find/?keywords=product%20analytics&location=gb--london&source=EVENTS",
)

EXPERIMENTATION_TITLE = re.compile(
    r"\b(?:experimentation|a\s*[/–-]\s*b\s+test(?:s|ing)?|split[ -]test(?:s|ing)?|"
    r"experiment\s+design|controlled\s+experiments?|causal\s+inference|incrementality|"
    r"cro|conversion(?:\s+rate)?\s+optimi[sz]ation|customer\s+experience\s+optimi[sz]ation)\b",
    re.IGNORECASE,
)

TECHNICAL_TITLE = re.compile(
    r"\b(?:data\s+(?:science|analys(?:is|t|ts)|analytics|visuali[sz]ation)|"
    r"analytics?|experimentation|a/b\s+test(?:ing)?|conversion|"
    r"cro|optimi[sz]ation|experiment\s+design|controlled\s+experiments?|"
    r"split[ -]test(?:s|ing)?|causal\s+inference|incrementality|statistics?|statistical|"
    r"bayesian|power\s*bi|tableau|dbt|databricks|pytorch|"
    r"sql|python|pydata|data\s+at\s+scale|knowledge\s+graphs?|graph\s+analytics|"
    r"machine\s+learning|product\s+insights?)\b",
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
        # Some organisers include a postcode in addressLocality.
        if isinstance(address, dict) and re.fullmatch(
            r"London(?:\s+[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})?",
            str(address.get("addressLocality", "")).strip(), re.I,
        ):
            return place
    return None


def discovered_topics(title: str) -> tuple[str, ...]:
    """Assign search-result topics from visible titles, not the search query."""
    if re.search(r"data science|pytorch|machine learning|pydata", title, re.I):
        base = DATA_SCIENCE
    elif EXPERIMENTATION_TITLE.search(title):
        base = EXPERIMENTATION
    elif re.search(r"database|data\s+engineering|data\s+at\s+scale|\betl\b", title, re.I):
        base = DATA_ENGINEERING
    elif re.search(r"statistic|bayesian", title, re.I):
        base = STATISTICS
    else:
        base = DATA_ANALYTICS
    # A data-science event about A/B tests should still be filterable as experimentation.
    return tuple(dict.fromkeys((base,) + ((EXPERIMENTATION,) if EXPERIMENTATION_TITLE.search(title) else ())))


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
        topics=tuple(dict.fromkeys(group.topics
        + ((EXPERIMENTATION,) if EXPERIMENTATION_TITLE.search(title) else ())
        + ((CAREERS,) if is_career_event(title) else ())
        + ((CAREER_FAIRS,) if is_career_fair(title) else ()))),
    )


MAX_ORGANISER_PAGES = 6


def organiser_links(description: str) -> list[str]:
    """Read explicitly labelled organiser/booking links, not arbitrary sponsors."""
    soup = BeautifulSoup(description, "html.parser")
    links = [(a.get_text(" ", strip=True), a.get("href", "")) for a in soup.find_all("a")]
    links += re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", description)
    result = []
    for label, url in links:
        if not re.search(r"website|register|registration|ticket|full\s+(?:address|details)|event\s+details", label, re.I):
            continue
        try:
            parts = urlparse(url)
            host = parts.hostname or ""
            if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
                continue
            if not host or "." not in host or host.endswith((".local", ".internal")):
                continue
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                continue
            if host in ("meetup.com", "www.meetup.com"):
                continue
        except ValueError:
            continue
        if url not in result:
            result.append(url)
    return result[:2]


def resolve_event(item: dict, group: MeetupGroup, cache: dict, now: datetime | None = None,
                  discovered: bool = False) -> Event | None:
    """Fill a missing Meetup venue only from the linked page's matching Event.

    Exact normalised title AND start instant must agree. No city is inferred
    from the group name, search query, page footer or sponsor name.
    """
    event = parse_event(item, group, now, discovered)
    if event is not None or london_place(item.get("location")) is not None:
        return event
    # An explicit foreign venue must never be overwritten by a London page.
    locations = item.get("location")
    locations = locations if isinstance(locations, list) else [locations]
    if any(isinstance(loc, dict) and isinstance(loc.get("address"), dict)
           and str(loc["address"].get("addressLocality", "")).strip() for loc in locations):
        return None
    if item.get("eventStatus") != "https://schema.org/EventScheduled" or item.get("eventAttendanceMode") not in (
        "https://schema.org/OfflineEventAttendanceMode", "https://schema.org/MixedEventAttendanceMode",
    ) or not TECHNICAL_TITLE.search(str(item.get("name", ""))):
        return None
    try:
        start = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
        if start.tzinfo is None or start < (now or datetime.now(timezone.utc)):
            return None
    except (KeyError, TypeError, AttributeError, ValueError):
        return None
    title_key = re.sub(r"\W+", " ", str(item.get("name", "")).casefold()).strip()
    for url in organiser_links(str(item.get("description", ""))):
        if url not in cache:
            if len(cache) >= MAX_ORGANISER_PAGES:
                continue
            # Failed pages consume budget too and are not requested repeatedly.
            cache[url] = None
            cache[url] = extract_schema_events(fetch_html(url, timeout=10, attempts=1, max_bytes=2_000_000))
        if cache[url] is None:
            raise FetchError(f"Linked organiser page unavailable: {url}")
        for detail in cache[url]:
            detail_key = re.sub(r"\W+", " ", str(detail.get("name", "")).casefold()).strip()
            try:
                detail_start = datetime.fromisoformat(detail["startDate"].replace("Z", "+00:00"))
            except (KeyError, TypeError, AttributeError, ValueError):
                continue
            if detail_key != title_key or detail_start != start or london_place(detail.get("location")) is None:
                continue
            enriched = deepcopy(item)
            for field in ("location", "endDate", "eventStatus", "eventAttendanceMode"):
                if detail.get(field):
                    enriched[field] = detail[field]
            event = parse_event(enriched, group, now, discovered)
            if event:
                # The booking page is also the evidence for the resolved venue/time.
                return replace(event, source="Meetup / organiser", source_url=url)
    return None


def get_events() -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    errors: list[str] = []
    cache: dict = {}
    previous = {}
    try:
        for raw in json.loads(Path('data/events.json').read_text()).get('events', []):
            if raw.get('id', '').startswith('meetup-'):
                previous[raw['id']] = Event(**{**raw, 'topics': tuple(raw.get('topics', []))})
    except (OSError, ValueError, TypeError, KeyError):
        pass

    def resolve(item, group, discovered=False):
        try:
            return resolve_event(item, group, cache, discovered=discovered)
        except FetchError as exc:
            # A new optional booking site must not disable every configured source.
            # As with RSS, retain prior verified facts on a transient detail failure.
            print(f"WARNING: Meetup linked organiser: {exc}")
            match = re.search(r'/events/(\d+)/?', str(item.get('url', '')))
            return previous.get(f'meetup-{match.group(1)}') if match else None
    pages = [(f"https://www.meetup.com/{g.slug}/", g) for g in GROUPS]
    pages += [(url, None) for url in SEARCH_URLS]

    def read_page(page):
        url, group = page
        try:
            return url, group, extract_schema_events(fetch_html(url)), None
        except (FetchError, ValueError) as exc:
            return url, group, [], str(exc)

    # Fetch independent indexes together, then resolve in stable source order.
    # Organiser enrichment remains serial with one shared bounded cache.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read_page, pages))
    for page_url, configured_group, items, failure in results:
        if failure:
            errors.append(f"Meetup [{page_url}]: {failure}")
            continue
        accepted = 0
        for item in items:
            group = configured_group
            if group is None:
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
            event = resolve(item, group, discovered=configured_group is None)
            if event is not None:
                events.append(event)
                accepted += 1
        print(f"Meetup [{page_url}]: {len(items)} record(s), {accepted} accepted")
    return events, errors
