"""Discovery configuration and evaluation for London Data Radar."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SEARCH_QUERIES = (
    "data analytics events London",
    "product analytics events London",
    "site:meetup.com London data analytics engineering events",
    "data science events London",
    "data engineering events London",
    "experimentation analytics events London",
    "site:eventbrite.co.uk London data science analytics events",
    "statistics events London",
    "data conference London",
    "site:luma.com London data science analytics events",
    "career fair data analytics London",
    "career fair data science London",
)

TARGETS_PATH = Path("data/discovery_targets.json")

DIAGNOSTIC_DOMAINS = (
    "meetup.com",
    "lu.ma",
    "luma.com",
    "eventbrite.co.uk",
    "eventbrite.com",
)


def normalise_url(url: str) -> str:
    """Normalise a URL for discovery evaluation."""
    parts = urlsplit(url.strip())

    hostname = (parts.hostname or "").casefold()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    path = parts.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parts.scheme.casefold() or "https",
            hostname,
            path,
            "",
            "",
        )
    )


def load_targets() -> list[dict]:
    """Load known events used only to evaluate discovery recall."""
    with TARGETS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    return payload["targets"]


def evaluate_targets(
    discovered_urls: set[str],
) -> list[tuple[str, bool]]:
    """Check whether known evaluation targets were discovered."""
    normalised_discovered = {
        normalise_url(url)
        for url in discovered_urls
    }

    results: list[tuple[str, bool]] = []

    for target in load_targets():
        target_url = normalise_url(
            target["url"]
        )

        results.append(
            (
                target["name"],
                target_url
                in normalised_discovered,
            )
        )

    return results


def hostname_for_url(url: str) -> str:
    """Return a normalised hostname for aggregate diagnostics."""
    hostname = (
        urlsplit(url).hostname
        or ""
    ).casefold()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def domain_diagnostics(
    discovered_urls: set[str],
) -> dict[str, int]:
    """
    Count selected event-platform domains.

    Only aggregate counts are returned. Search result URLs are not
    logged or persisted.
    """
    counts = {
        domain: 0
        for domain in DIAGNOSTIC_DOMAINS
    }

    counts["other"] = 0

    for url in discovered_urls:
        hostname = hostname_for_url(url)

        matched = False

        for domain in DIAGNOSTIC_DOMAINS:
            if (
                hostname == domain
                or hostname.endswith(
                    f".{domain}"
                )
            ):
                counts[domain] += 1
                matched = True
                break

        if not matched:
            counts["other"] += 1

    return counts
