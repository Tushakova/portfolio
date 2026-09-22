"""Build the canonical events dataset used by London Data Radar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.events.models import Event
from src.events.sources.standalone import get_events


OUTPUT_PATH = Path("data/events.json")
SCHEMA_VERSION = "1.0"


def build_dataset(events: list[Event]) -> dict:
    """Return the canonical dataset consumed by the frontend."""

    events = sorted(
        events,
        key=lambda event: event.start_at,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "events": [
            event.to_dict()
            for event in events
        ],
    }


def write_dataset(dataset: dict) -> None:
    """Write the canonical dataset atomically."""

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


def main() -> None:
    """Run the event ingestion pipeline."""

    events, errors = get_events()

    for error in errors:
        print(f"WARNING: {error}")

    if not events:
        raise RuntimeError(
            "No events were successfully ingested; "
            "refusing to overwrite the existing dataset."
        )

    dataset = build_dataset(events)
    write_dataset(dataset)

    print(
        f"Built {len(events)} event(s) "
        f"→ {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
