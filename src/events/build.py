"""Build the canonical events dataset used by London Data Radar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.events.models import Event
from src.events.sources import dsf, meetup, rss, standalone
from src.events.validation import (
    deduplicate_events,
    validate_events,
)


OUTPUT_PATH = Path("data/events.json")
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


def build_dataset(events: list[Event]) -> dict:
    """Return the canonical dataset consumed by the frontend."""

    ordered_events = sorted(
        events,
        key=lambda event: event.start_at,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(ordered_events),
        "events": [
            event.to_dict()
            for event in ordered_events
        ],
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

    dataset = build_dataset(events)
    if events_unchanged(dataset):
        print("Event data unchanged; keeping the previous refresh timestamp.")
        return
    write_dataset(dataset)

    print(
        f"Built {len(events)} validated event(s) "
        f"→ {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
