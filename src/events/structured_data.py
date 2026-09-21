"""Utilities for extracting schema.org Event data from web pages."""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


def _walk_json(value: Any):
    """Yield every dictionary contained in a JSON-like structure."""
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from _walk_json(child)

    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _is_event(value: dict) -> bool:
    """Return whether a JSON-LD object represents a schema.org Event."""
    event_type = value.get("@type")

    if isinstance(event_type, str):
        return event_type == "Event" or event_type.endswith("Event")

    if isinstance(event_type, list):
        return any(
            isinstance(item, str)
            and (item == "Event" or item.endswith("Event"))
            for item in event_type
        )

    return False


def extract_schema_events(html: str) -> list[dict]:
    """Extract schema.org Event objects from JSON-LD in an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        raw_json = script.string or script.get_text()

        if not raw_json.strip():
            continue

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            # One malformed JSON-LD block should not invalidate
            # otherwise usable structured data on the page.
            continue

        for item in _walk_json(payload):
            if _is_event(item):
                events.append(item)

    return events
