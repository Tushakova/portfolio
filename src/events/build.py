"""Build the canonical events dataset used by the website."""

import json
from datetime import datetime, timezone
from pathlib import Path


OUTPUT_PATH = Path("data/events.json")


def build_dataset(events: list[dict]) -> dict:
    """Return the canonical dataset consumed by the frontend."""
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }


def write_dataset(dataset: dict) -> None:
    """Write the canonical dataset to disk."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(dataset, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main() -> None:
    events: list[dict] = []

    dataset = build_dataset(events)
    write_dataset(dataset)

    print(f"Built {len(events)} events → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
