"""Candidate-page inspection for London Data Radar."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit

from src.events.http import fetch_text


EVENT_PATH_TERMS = (
    "event",
    "events",
    "meetup",
    "conference",
    "summit",
    "career",
    "fair",
    "workshop",
    "talk",
)

EVENT_TEXT_TERMS = (
    "data analytics",
    "product analytics",
    "analytics engineering",
    "data science",
    "data engineering",
    "machine learning",
    "artificial intelligence",
    "experimentation",
    "statistics",
    "career fair",
    "careers fair",
)

LONDON_TERMS = (
    "london",
    "greater london",
)

MONTH_PATTERN = re.compile(
    r"\b("
    r"january|february|march|april|may|june|"
    r"july|august|september|october|november|december"
    r")\b",
    re.IGNORECASE,
)

ISO_DATE_PATTERN = re.compile(
    r"\b20\d{2}-\d{2}-\d{2}\b"
)


@dataclass(frozen=True)
class CandidateInspection:
    url: str
    fetched: bool
    event_path: bool
    topic_evidence: bool
    london_evidence: bool
    date_evidence: bool

    @property
    def plausible(self) -> bool:
        """Return whether the page has enough event evidence."""
        return (
            self.fetched
            and self.topic_evidence
            and self.london_evidence
            and self.date_evidence
        )


def clean_html_text(html: str) -> str:
    """Convert HTML into rough searchable text."""
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = unescape(text)

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def has_event_path(url: str) -> bool:
    """Check whether the URL itself looks event-related."""
    path = urlsplit(url).path.casefold()

    return any(
        term in path
        for term in EVENT_PATH_TERMS
    )


def has_topic_evidence(text: str) -> bool:
    """Check for a relevant data/analytics topic."""
    lowered = text.casefold()

    return any(
        term in lowered
        for term in EVENT_TEXT_TERMS
    )


def has_london_evidence(text: str) -> bool:
    """Check for London location evidence."""
    lowered = text.casefold()

    return any(
        term in lowered
        for term in LONDON_TERMS
    )


def has_date_evidence(text: str) -> bool:
    """
    Check for basic date evidence.

    This deliberately does not yet attempt to parse the event date.
    """
    return bool(
        MONTH_PATTERN.search(text)
        or ISO_DATE_PATTERN.search(text)
    )


def inspect_candidate(
    url: str,
) -> CandidateInspection:
    """Fetch and inspect one discovered candidate page."""
    try:
        html = fetch_text(url)

    except Exception:
        return CandidateInspection(
            url=url,
            fetched=False,
            event_path=has_event_path(url),
            topic_evidence=False,
            london_evidence=False,
            date_evidence=False,
        )

    text = clean_html_text(html)

    return CandidateInspection(
        url=url,
        fetched=True,
        event_path=has_event_path(url),
        topic_evidence=has_topic_evidence(text),
        london_evidence=has_london_evidence(text),
        date_evidence=has_date_evidence(text),
    )


def inspect_candidates(
    urls: set[str],
) -> list[CandidateInspection]:
    """Inspect discovered URLs without persisting search results."""
    return [
        inspect_candidate(url)
        for url in urls
    ]
