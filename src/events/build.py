"""Build the canonical events dataset used by London Data Radar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.events.models import Event
from src.events.sources import career_fairs, dsf, meetup, rss, standalone
from src.events.validation import (
    deduplicate_events,
    validate_events,
)


OUTPUT_PATH = Path("data/events.json")
CHECK_PATH = Path("data/refresh-status.json")
SCHEMA_VERSION = "1.0"


def collect_events() -> tuple[list[Event], list[str]]:
    """Collect events from all active sources."""

    events: list[Event] = []
    errors: list[str] = []

    collectors = (
        ("Standalone", standalone.get_events),
        ("RSS", rss.get_events),
        ("Meetup", meetup.get_events),
        ("Data Science Festival", dsf.get_events),
        ("Career fairs", career_fairs.get_events),
    )

    for source_name, collector in collectors:
        try:
            source_events, source_errors = collector()
            events.extend(source_events)
            errors.extend(source_errors)

            print(
                f"{source_name}: "
                f"{len(source_events)} event(s), "
                f"{len(source_errors)} warning(s)"
            )

        except Exception as exc:
            # Source isolation:
            # an unexpected failure in one connector must not erase
            # successfully collected events from other connectors.
            errors.append(
                f"{source_name}: unexpected failure: {exc}"
            )

    return events, errors


def previous_dataset() -> dict:
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def is_past(item: dict, now: datetime) -> bool:
    """Keep an event through its final local calendar day if end time is unknown."""
    if item.get("end_at"):
        return datetime.fromisoformat(item["end_at"]) < now
    from zoneinfo import ZoneInfo
    london = ZoneInfo("Europe/London")
    return datetime.fromisoformat(item["start_at"]).astimezone(london).date() < now.astimezone(london).date()


def build_dataset(events: list[Event], previous: dict | None = None,
                  now: datetime | None = None) -> dict:
    """Return the canonical dataset consumed by the frontend."""

    previous = previous or {}
    now = now or datetime.now(timezone.utc)
    current = {event.id: event.to_dict() for event in events}
    archived = {item["id"]: item for item in previous.get("past_events", [])}
    # Previous snapshots become an archive when sources stop listing past events.
    for item in previous.get("events", []):
        if is_past(item, now):
            archived[item["id"]] = item
    for item in current.values():
        if is_past(item, now):
            archived[item["id"]] = item
    for event_id in current:
        if not is_past(current[event_id], now):
            archived.pop(event_id, None)
    upcoming = sorted((item for item in current.values() if not is_past(item, now)),
                      key=lambda item: item["start_at"])
    past = sorted(archived.values(), key=lambda item: item["start_at"], reverse=True)
    changes = list(previous.get("changes", []))
    old = {item["id"]: item for item in previous.get("events", [])}
    for event_id, item in current.items():
        if event_id not in old:
            changes.append({"at": now.isoformat(), "event_id": event_id,
                            "title": item["title"], "action": "added"})
        elif old[event_id] != item:
            changes.append({"at": now.isoformat(), "event_id": event_id,
                            "title": item["title"], "action": "updated"})
    for event_id, item in old.items():
        if event_id not in current:
            changes.append({"at": now.isoformat(), "event_id": event_id,
                            "title": item["title"],
                            "action": "archived" if is_past(item, now) else "removed from source"})

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "event_count": len(upcoming),
        "events": upcoming,
        "past_events": past,
        "changes": changes[-250:],
    }


def write_dataset(dataset: dict) -> None:
    """Write the dataset atomically."""

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = OUTPUT_PATH.with_suffix(".json.tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            dataset,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    temporary_path.replace(OUTPUT_PATH)


def events_unchanged(dataset: dict) -> bool:
    """Avoid publishing a new timestamp when event facts have not changed."""
    try:
        previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False

    return (
        previous.get("schema_version") == dataset["schema_version"]
        and previous.get("events") == dataset["events"]
        and previous.get("event_count") == dataset["event_count"]
        and previous.get("past_events", []) == dataset["past_events"]
        and previous.get("changes", []) == dataset["changes"]
    )


def main() -> None:
    """Run the complete ingestion pipeline."""

    events, errors = collect_events()

    for error in errors:
        print(f"WARNING: {error}")

    if errors:
        raise RuntimeError(
            "One or more sources failed; keeping the last published dataset "
            "rather than silently dropping events."
        )

    events = deduplicate_events(events)

    if not events:
        raise RuntimeError(
            "No events were successfully ingested; "
            "refusing to overwrite the existing dataset."
        )

    validate_events(events)

    now = datetime.now(timezone.utc)
    dataset = build_dataset(events, previous_dataset(), now)
    CHECK_PATH.write_text(json.dumps({"last_successful_check": now.isoformat()}, indent=2) + "\n", encoding="utf-8")
    if events_unchanged(dataset):
        print("Event data unchanged; keeping the previous refresh timestamp.")
        return
    write_dataset(dataset)

    print(
        f"Built {dataset['event_count']} upcoming and {len(dataset['past_events'])} archived event(s) "
        f"→ {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
