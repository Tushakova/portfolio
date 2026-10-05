"""Refresh the finite list of human-reviewed web discoveries independently of Brave."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.events.models import Event
from src.events.validation import deduplicate_events, validate_events

APPROVED_PATH = Path("data/discovered-events.json")
MAX_APPROVED = 30


def read_events(path: Path) -> list[Event]:
    data = json.loads(path.read_text(encoding="utf-8"))
    events = []
    for item in data["events"]:
        item = dict(item)
        item["topics"] = tuple(item.get("topics", []))
        events.append(Event(**item))
    validate_events(events)
    return events


def refresh(events: list[Event]) -> tuple[list[Event], list[str]]:
    # Lazy import avoids the candidates -> sources import cycle.
    from src.events.candidates import inspect_candidate, public_url
    from src.events.build import is_past
    now = datetime.now(timezone.utc)
    fresh, errors = [], []
    for event in events:
        if is_past(event.to_dict(), now):
            continue  # build_dataset keeps the previously published archive.
        if not public_url(event.source_url):
            errors.append(f"Reviewed discovery {event.id}: invalid public URL")
            continue
        inspection = inspect_candidate(event.source_url)
        matches = [item for item in inspection.events
                   if item.id == event.id and inspection.decision == "accepted"]
        if len(matches) == 1:
            fresh.extend(matches)
        else:
            errors.append(f"Reviewed discovery {event.id}: {inspection.reason}; needs review")
    return fresh, errors


def get_events() -> tuple[list[Event], list[str]]:
    if not APPROVED_PATH.exists():
        return [], []
    events = read_events(APPROVED_PATH)
    if len(events) > MAX_APPROVED:
        return [], [f"Reviewed discoveries exceed the {MAX_APPROVED}-page refresh budget"]
    return refresh(events)


def approve(path: Path) -> None:
    """Import only the records a maintainer left in the reviewed candidate file."""
    from src.events.candidates import summarise_events, CandidateInspection, source_kind
    selected = read_events(path)
    if len(selected) > MAX_APPROVED:
        raise ValueError(f"Select at most {MAX_APPROVED} records per import")
    fresh, errors = refresh(selected)
    if errors or len(fresh) != len(selected):
        raise ValueError("Selected candidates failed re-verification: " + "; ".join(errors))
    current = read_events(APPROVED_PATH) if APPROVED_PATH.exists() else []
    published_path = Path("data/events.json")
    published = json.loads(published_path.read_text(encoding="utf-8"))
    known = current + [Event(**{**item, "topics": tuple(item.get("topics", []))})
                       for item in published.get("events", []) + published.get("past_events", [])]
    additions = []
    inspections = [CandidateInspection(url=e.source_url, decision="accepted",
                    provenance=source_kind(e.source_url), events=(e,)) for e in fresh]
    summarise_events(inspections, [e.to_dict() for e in known], additions)
    merged = deduplicate_events(current + additions)
    if len(merged) > MAX_APPROVED:
        raise ValueError(f"At most {MAX_APPROVED} approved events are supported; prune old entries first")
    APPROVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = APPROVED_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"events": [e.to_dict() for e in merged]},
                             indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(APPROVED_PATH)
    print(f"Approved {len(additions)} new events; {len(merged)} registered in total.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve human-reviewed discoveries after re-verification")
    parser.add_argument("--approve", type=Path, required=True)
    approve(parser.parse_args().approve)
