"""Bounded verification of search candidates against organiser event facts.

Search snippets are not evidence. Candidates and their extracted facts stay in
memory; this module does not publish them or write Brave results to disk.
"""
from __future__ import annotations

import ipaddress
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.events.http import fetch_html
from src.events.discovery_html import extract_microdata_events, detail_links
from src.events.models import Event
from src.events.structured_data import extract_schema_events
from src.events.sources.standalone import EVENT_PAGES, EventParseError
from src.events.sources.meetup import TECHNICAL_TITLE, discovered_topics
from src.events.topics import CAREERS, CAREER_FAIRS, is_career_event, is_career_fair
from src.events.validation import validate_event

MAX_PAGES = 48
MAX_WORKERS = 4
MAX_EVENTS_PER_PAGE = 20
LONDON = ZoneInfo("Europe/London")
TRACKING = {"gclid", "fbclid", "msclkid"}
RESTRICTED = re.compile(r"(?:students?\s+(?:and|or)\s+(?:recent\s+)?graduates?|members?\s+only|invitation[ -]only)", re.I)
NON_EVENT = re.compile(r"\b(?:bootcamp|certification|training course|job vacancies)\b", re.I)


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if not k.lower().startswith("utm_") and k.lower() not in TRACKING))
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/") or "/", query, ""))


def public_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        if p.scheme not in ("http", "https") or not host or p.username or p.password:
            return False
        if p.port not in (None, 80, 443) or host.lower() == "localhost" or host.lower().endswith((".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host
    except ValueError:
        return False


def clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer"]):
        node.decompose()
    return " ".join(soup.stripped_strings)


def has_event_path(url: str) -> bool:
    return bool(re.search(r"event|meetup|conference|summit|career|fair|workshop|talk", urlsplit(url).path, re.I))


@dataclass(frozen=True)
class CandidateInspection:
    url: str
    fetched: bool = False
    event_path: bool = False
    topic_evidence: bool = False
    london_evidence: bool = False
    date_evidence: bool = False
    decision: str = "review"
    reason: str = "unverified"
    events: tuple[Event, ...] = ()
    links: tuple[str, ...] = ()
    extraction: str = "none"

    @property
    def plausible(self) -> bool:
        return self.decision == "accepted"


def _text(value: object) -> str:
    return clean_html_text(value) if isinstance(value, str) else ""


def verify_event(item: dict, page_url: str, now: datetime) -> tuple[Event | None, str, str]:
    """Require facts belonging to one event, not keywords elsewhere on the page."""
    name = _text(item.get("name"))
    description = _text(item.get("description"))
    evidence = f"{name} {description}"
    if not name:
        return None, "review", "missing_title"
    if NON_EVENT.search(name) or not TECHNICAL_TITLE.search(evidence):
        return None, "rejected", "off_topic_or_course"
    state = str(item.get("eventStatus", "")).split("/")[-1]
    if state in ("EventCancelled", "EventPostponed"):
        return None, "rejected", "cancelled_or_postponed"
    raw_start = item.get("startDate")
    if not isinstance(raw_start, str):
        return None, "review", "missing_date"
    all_day = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_start))
    try:
        start = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
        if all_day:
            start = start.replace(tzinfo=LONDON)
        if start.tzinfo is None:
            return None, "review", "missing_timezone"
        raw_end = item.get("endDate")
        end_is_date = bool(raw_end and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw_end)))
        end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")) if raw_end else None
        if end_is_date:
            # Inclusive calendar date; internal boundary only, never a claimed closing time.
            end = (end + timedelta(days=1)).replace(tzinfo=LONDON) - timedelta(microseconds=1)
            all_day = True
        if end and (end.tzinfo is None or end <= start):
            return None, "review", "invalid_end_date"
    except (ValueError, TypeError, AttributeError):
        return None, "review", "invalid_date"
    if (end and end <= now) or (not end and start.astimezone(LONDON).date() < now.astimezone(LONDON).date()):
        return None, "rejected", "past_event"
    if RESTRICTED.search(evidence):
        return None, "review", "restricted_audience"

    locations = item.get("location", [])
    locations = locations if isinstance(locations, list) else [locations]
    places = [loc for loc in locations if isinstance(loc, dict) and loc.get("@type") == "Place"]
    virtual = any(isinstance(loc, dict) and loc.get("@type") == "VirtualLocation" for loc in locations)
    physical = None
    confirmed_localities = []
    for place in places:
        addr = place.get("address", {})
        locality = addr.get("addressLocality", "") if isinstance(addr, dict) else addr
        if isinstance(addr, dict) and isinstance(locality, str) and locality.strip():
            confirmed_localities.append(locality)
        if re.search(r"\bLondon\b", str(locality), re.I):
            physical = place
            break
    mode = str(item.get("eventAttendanceMode", "")).split("/")[-1]
    if mode == "OnlineEventAttendanceMode" and virtual:
        if not re.search(r"\bLondon\b", evidence, re.I):
            return None, "review", "online_london_link_unconfirmed"
        event_format = "online"
    elif mode == "MixedEventAttendanceMode" and physical:
        event_format = "hybrid"
    elif physical and mode in ("", "OfflineEventAttendanceMode"):
        event_format = "in_person"
    elif places and physical is None and len(confirmed_localities) == len(places):
        return None, "rejected", "outside_london"
    else:
        return None, "review", "unconfirmed_location_or_format"

    url = item.get("url") or page_url
    if isinstance(url, str):
        url = urljoin(page_url, url)
    if not isinstance(url, str) or not public_url(url):
        return None, "review", "invalid_event_url"
    organiser = item.get("organizer", {})
    organiser = organiser.get("name", "") if isinstance(organiser, dict) else organiser
    if not isinstance(organiser, str) or not organiser.strip():
        return None, "review", "missing_organiser"
    topics = discovered_topics(evidence)
    if is_career_event(name):
        topics += (CAREERS,)
    if is_career_fair(name):
        topics += (CAREER_FAIRS,)
    free = item.get("isAccessibleForFree")
    free = free if isinstance(free, bool) else None
    import hashlib
    identity = f"{canonical_url(url)}|{start.isoformat()}"
    event = Event(id="discovered-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                  title=name, start_at=start.isoformat(), end_at=end.isoformat() if end else None,
                  format=event_format, organiser=organiser.strip(), source="Web discovery",
                  source_url=url, venue_name=_text(physical.get("name")) if physical else None,
                  is_free=free, price_from_gbp=0.0 if free else None,
                  topics=topics, time_tbc=all_day)
    validate_event(event)
    return event, "accepted", "verified_structured_event"


def inspect_candidate(url: str, now: datetime | None = None) -> CandidateInspection:
    now = now or datetime.now(timezone.utc)
    if not public_url(url):
        return CandidateInspection(url, decision="rejected", reason="invalid_url")
    try:
        html = fetch_html(url, timeout=10, attempts=1, max_bytes=2_000_000)
    except Exception as exc:
        cause = exc.__cause__ or exc
        code = getattr(cause, "code", None)
        reason = f"http_{code}" if code else "fetch_failed"
        if isinstance(cause, TimeoutError):
            reason = "fetch_timeout"
        if "size limit" in str(exc):
            reason = "page_too_large"
        return CandidateInspection(url, decision="review", reason=reason)
    text = clean_html_text(html)
    structured = extract_schema_events(html)
    extraction = "json_ld" if structured else "microdata"
    if not structured:
        structured = extract_microdata_events(html)
    facts = dict(url=url, fetched=True, event_path=has_event_path(url),
                 links=detail_links(html, url), extraction=extraction if structured else "none",
                 topic_evidence=bool(TECHNICAL_TITLE.search(text)),
                 london_evidence=bool(re.search(r"\bLondon\b", text, re.I)),
                 date_evidence=any(item.get("startDate") for item in structured))
    if not structured:
        for page in EVENT_PAGES:
            if canonical_url(url) != canonical_url(page.url):
                continue
            try:
                event = page.parser(html, url)
                validate_event(event)
            except (EventParseError, ValueError):
                return CandidateInspection(**facts, decision="review", reason="known_parser_changed")
            start = datetime.fromisoformat(event.start_at)
            end = datetime.fromisoformat(event.end_at) if event.end_at else None
            if (end and end <= now) or (not end and start.astimezone(LONDON).date() < now.astimezone(LONDON).date()):
                return CandidateInspection(**facts, decision="rejected", reason="past_event")
            facts["extraction"] = "organiser_html"
            return CandidateInspection(**facts, decision="accepted", reason="verified_organiser_html", events=(event,))
        # An independent organiser without JSON-LD remains in review, not rejected.
        return CandidateInspection(**facts, decision="review", reason="no_structured_event")
    results = [verify_event(item, url, now) for item in structured[:MAX_EVENTS_PER_PAGE]]
    accepted = tuple(event for event, _, _ in results if event)
    if accepted:
        return CandidateInspection(**facts, decision="accepted", reason="verified_structured_event", events=accepted)
    review = next((result for result in results if result[1] == "review"), results[0])
    return CandidateInspection(**facts, decision=review[1], reason=review[2])


def select_candidates(urls: set[str], limit: int = MAX_PAGES) -> list[str]:
    """Deduplicate tracking URLs, then fairly spread a fixed budget across domains."""
    if limit <= 0:
        return []
    domains: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for url in sorted(urls):
        if not public_url(url):
            continue
        key = canonical_url(url)
        if key in seen:
            continue
        seen.add(key)
        domains[urlsplit(key).hostname].append(url)
    for group in domains.values():
        group.sort(key=lambda url: (-candidate_priority(url), url))
    selected = []
    while domains and len(selected) < limit:
        for domain in sorted(list(domains), key=lambda d: (-candidate_priority(domains[d][0]), d)):
            selected.append(domains[domain].pop(0))
            if not domains[domain]:
                del domains[domain]
            if len(selected) >= limit:
                break
    return selected


def candidate_priority(url: str) -> int:
    """Prefer detail pages over calendars, articles, courses and search pages."""
    path = urlsplit(url).path.lower()
    score = 4 if re.search(r"/(?:events?|e|talks?|conferences?|workshops?)/[^/]+", path) else 0
    score += 2 if re.search(r"data|analytics|statistic|experiment|career", path) else 0
    score -= 5 if re.search(r"/(?:blog|news|courses?|training|jobs|archive|past|search)(?:/|$)", path) else 0
    return score


def inspect_candidates(urls: set[str]) -> list[CandidateInspection]:
    # Reserve a quarter of the unchanged page budget for detail links. If there
    # are none, spend that budget on remaining search results instead.
    selected = select_candidates(urls, limit=36)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        first = list(pool.map(inspect_candidate, selected))
        seen = {canonical_url(url) for url in selected}
        links = {url for result in first if not result.events for url in result.links
                 if public_url(url) and canonical_url(url) not in seen}
        second_urls = select_candidates(links, limit=MAX_PAGES - len(first))
        seen.update(canonical_url(url) for url in second_urls)
        remaining = {url for url in urls if public_url(url) and canonical_url(url) not in seen}
        second_urls += select_candidates(remaining, limit=MAX_PAGES - len(first) - len(second_urls))
        return first + list(pool.map(inspect_candidate, second_urls))


def summarise_events(inspections: list[CandidateInspection], known: list[dict]) -> dict[str, int]:
    """Separate verified records from unique new events and already published events."""
    def keys(item):
        day = datetime.fromisoformat(item["start_at"]).astimezone(LONDON).date().isoformat()
        title = re.sub(r"[^\w]+", " ", item["title"].casefold()).strip()
        return ("url", canonical_url(item["source_url"]), day), ("name", title, day, item["organiser"].casefold())
    known_keys = {key for item in known for key in keys(item)}
    seen = set()
    counts = {"verified_records": 0, "duplicate_records": 0, "already_published": 0, "new_verified_events": 0}
    for inspection in inspections:
        for event in inspection.events:
            counts["verified_records"] += 1
            event_keys = keys(event.to_dict())
            if any(key in seen for key in event_keys):
                counts["duplicate_records"] += 1
            elif any(key in known_keys for key in event_keys):
                counts["already_published"] += 1
            else:
                counts["new_verified_events"] += 1
            seen.update(event_keys)
    return counts
