"""Regression checks for archive identity, repeated runs and reviewed discovery."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from unittest.mock import patch

from src.events.models import Event
from src.events.build import build_dataset
from src.events.validation import deduplicate_events
from src.events.candidates import CandidateInspection
from src.events.sources import reviewed


def example(**kwargs):
    fields = dict(id="measurecamp-19", title="MeasureCamp London 19",
                  start_at="2026-09-26T09:00:00+01:00", end_at="2026-09-26T17:00:00+01:00",
                  format="in_person", organiser="MeasureCamp", source="Standalone",
                  source_url="https://london.measurecamp.org/registration/")
    fields.update(kwargs)
    return Event(**fields)


class LifecycleTests(unittest.TestCase):
    def test_past_source_record_is_not_added_every_day(self):
        e = example()
        previous = build_dataset([e], now=datetime(2026, 9, 25, tzinfo=timezone.utc))
        first = build_dataset([e], previous, datetime(2026, 9, 27, tzinfo=timezone.utc))
        self.assertEqual([c["action"] for c in first["changes"]], ["added", "archived"])
        for day in range(28, 31):
            result = build_dataset([e], first, datetime(2026, 9, day, tzinfo=timezone.utc))
            self.assertEqual(result["changes"], first["changes"])
            self.assertEqual(result["past_events"], first["past_events"])

    def test_historical_duplicate_additions_are_repaired(self):
        e = example()
        previous = build_dataset([e], now=datetime(2026, 9, 27, tzinfo=timezone.utc))
        previous["changes"].append({**previous["changes"][0], "at": "2026-09-28T00:00:00+00:00"})
        result = build_dataset([e], previous, datetime(2026, 9, 29, tzinfo=timezone.utc))
        self.assertEqual(len(result["changes"]), 1)

    def test_real_archive_update_and_next_edition_are_logged(self):
        e = example()
        previous = build_dataset([e], now=datetime(2026, 9, 27, tzinfo=timezone.utc))
        changed = replace(e, venue_name="Corrected venue")
        next_edition = example(id="measurecamp-20", title="MeasureCamp London 20",
                               start_at="2027-09-18T09:00:00+01:00", end_at="2027-09-18T17:00:00+01:00")
        result = build_dataset([changed, next_edition], previous, datetime(2026, 9, 28, tzinfo=timezone.utc))
        self.assertEqual([c["action"] for c in result["changes"]], ["added", "updated", "added"])
        self.assertEqual(len(deduplicate_events([changed, next_edition])), 2)

    def test_cross_posted_online_event_is_one_card(self):
        e = example(format="online", title="GPU, CUDA, and PyTorch Performance Optimizations")
        other = replace(e, id="other", source_url="https://meetup.com/other/events/123/", organiser="Other group")
        self.assertEqual(deduplicate_events([e, other]), [e])
        different_day = replace(other, start_at="2026-09-27T09:00:00+01:00")
        self.assertEqual(len(deduplicate_events([e, different_day])), 2)

    def test_reviewed_import_rechecks_and_deduplicates(self):
        e = example(id="future", start_at="2099-09-26T09:00:00+01:00", end_at="2099-09-26T17:00:00+01:00")
        inspection = CandidateInspection(url=e.source_url, decision="accepted", provenance="organiser", events=(e,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = root / "candidates.json"
            candidates.write_text(json.dumps({"events": [e.to_dict()]}))
            approved = root / "approved.json"
            with patch.object(reviewed, "APPROVED_PATH", approved), \
                    patch("src.events.candidates.inspect_candidate", return_value=inspection), \
                    patch.object(reviewed.Path, "read_text", autospec=True) as read:
                def read_local(p, **kw):
                    if str(p) == "data/events.json":
                        return json.dumps({"events": []})
                    with p.open() as handle:
                        return handle.read()
                read.side_effect = read_local
                reviewed.approve(candidates)
                reviewed.approve(candidates)
                self.assertEqual(len(reviewed.read_events(approved)), 1)

    def test_reviewed_failure_returns_error_not_empty_success(self):
        e = example(start_at="2099-09-26T09:00:00+01:00", end_at="2099-09-26T17:00:00+01:00")
        with patch("src.events.candidates.inspect_candidate", return_value=CandidateInspection(url=e.source_url, reason="http_403")):
            events, errors = reviewed.refresh([e])
        self.assertEqual(events, [])
        self.assertTrue(errors)
