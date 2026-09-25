"""Discovery configuration and evaluation for London Data Radar."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SEARCH_QUERIES = (
    '"data analytics" events London',
    '"product analytics" meetup London',
    '"analytics engineering" meetup London',
    '"data science" meetup London',
    '"data engineering" meetup London',
    '"experimentation" product meetup London',
    '"machine learning" meetup London',
    '"statistics" events London',
    '"data conference" London',
    '"analytics conference" London',
)

TARGETS_PATH = Path("data/discovery_targets.json")


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
