"""Regression checks for precision, resource limits and duplicate handling."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src.events.candidates import (CandidateInspection, canonical_url, inspect_candidate,
                                  select_candidates, summarise_events, verify_event)

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
URL = "https://organiser.example/events/data-science"


def fixture(**overrides):
    base = {"@type": "Event", "name": "London Data Science Meetup",
            "description": "Discuss practical analytics with other professionals.",
            "startDate": "2026-10-21T18:00:00+01:00", "endDate": "2026-10-21T20:00:00+01:00",
            "url": URL, "organizer": {"name": "London Data Community"},
            "location": {"@type": "Place", "name": "Example Hall", "address": {"addressLocality": "London"}},
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode"}
    return dict(base, **overrides)


class DiscoveryTests(unittest.TestCase):
    def test_accepts_future_event_keeps_unknown_price(self):
        event, decision, _ = verify_event(fixture(), URL, NOW)
        self.assertEqual(decision, "accepted")
        self.assertIsNone(event.is_free)
        self.assertIsNone(event.price_from_gbp)

    def test_past_cancelled_foreign_and_restricted(self):
        cases = [
            (fixture(startDate="2025-10-21T18:00:00+01:00", endDate="2025-10-21T20:00:00+01:00"), "rejected", "past_event"),
            (fixture(eventStatus="https://schema.org/EventCancelled"), "rejected", "cancelled_or_postponed"),
            (fixture(location={"@type":"Place","address":{"addressLocality":"Paris"}}), "rejected", "outside_london"),
            (fixture(description="Data science event for students and recent graduates"), "review", "restricted_audience"),
            (fixture(startDate="2026-10-21T18:00:00"), "review", "missing_timezone"),
        ]
        for item, decision, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(verify_event(item, URL, NOW)[1:], (decision, reason))

    def test_topic_must_belong_to_event_not_footer(self):
        html = '<script type="application/ld+json">' + json.dumps(fixture(name="Investors Breakfast", description="Networking with founders")) + '</script><footer>London data science events October 2026</footer>'
        with patch("src.events.candidates.fetch_html", return_value=html):
            result = inspect_candidate(URL, NOW)
        self.assertEqual(result.reason, "off_topic_or_course")

    def test_unstructured_page_is_review_not_verified_by_month_word(self):
        with patch("src.events.candidates.fetch_html", return_value="<h1>London data science events</h1><p>September</p>"):
            result = inspect_candidate(URL, NOW)
        self.assertEqual(result.decision, "review")
        self.assertEqual(result.reason, "no_structured_event")
        self.assertFalse(result.plausible)

    def test_tracking_duplicates_budget_and_domain_diversity(self):
        urls = {f"https://large.example/events/{n}" for n in range(100)}
        urls |= {"https://independent.example/", "https://large.example/events/1?utm_source=mail", "http://127.0.0.1/private"}
        selected = select_candidates(urls, limit=6)
        self.assertEqual(len(selected), 6)
        self.assertIn("https://independent.example/", selected)
        self.assertEqual(len({canonical_url(url) for url in selected}), 6)
        self.assertNotIn("http://127.0.0.1/private", selected)
        self.assertNotEqual(canonical_url(URL+"?event=1"), canonical_url(URL+"?event=2"))

    def test_same_event_counts_once_and_known_record_not_new(self):
        event, _, _ = verify_event(fixture(), URL, NOW)
        inspections = [CandidateInspection(URL, decision="accepted", events=(event, event))]
        counts = summarise_events(inspections, [event.to_dict()])
        self.assertEqual(counts, dict(verified_records=2, duplicate_records=1, already_published=1, new_verified_events=0))

    def test_failed_page_does_not_abort_other_candidates(self):
        with patch("src.events.candidates.fetch_html", side_effect=TimeoutError):
            result = inspect_candidate(URL, NOW)
        self.assertEqual(result.reason, "fetch_timeout")

    def test_missing_city_is_review_not_outside_london(self):
        item = fixture(location={"@type": "Place", "address": {"streetAddress": "Example Street"}})
        self.assertEqual(verify_event(item, URL, NOW)[1:], ("review", "unconfirmed_location_or_format"))

    def test_online_requires_explicit_location_and_london_context(self):
        event, decision, _ = verify_event(fixture(eventAttendanceMode="https://schema.org/OnlineEventAttendanceMode",
              location={"@type":"VirtualLocation","url":URL}), URL, NOW)
        self.assertEqual(decision,"accepted")
        self.assertEqual(event.format,"online")
        _, decision, _ = verify_event(fixture(name="Data Science Meetup", eventAttendanceMode="https://schema.org/OnlineEventAttendanceMode",
              location={"@type":"VirtualLocation","url":URL}), URL, NOW)
        self.assertEqual(decision,"review")


class SearchBudgetTests(unittest.TestCase):
    def test_default_run_uses_twelve_queries_and_does_not_publish(self):
        import contextlib
        import io
        from pathlib import Path
        from src.events import search
        before = Path("data/events.json").read_bytes()
        with patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "test-only"}), \
             patch("sys.argv", ["search"]), \
             patch.object(search, "search_web", return_value=[]) as provider, \
             patch.object(search.time, "sleep"), \
             patch.object(search, "run_target_diagnostics") as diagnostics, \
             contextlib.redirect_stdout(io.StringIO()):
            search.main()
        self.assertEqual(provider.call_count, 12)
        diagnostics.assert_not_called()
        self.assertEqual(Path("data/events.json").read_bytes(), before)


class ExpandedExtractionTests(unittest.TestCase):
    def test_inclusive_date_end_stays_current_through_last_day(self):
        item = fixture(startDate="2026-09-24", endDate="2026-09-25")
        event, decision, _ = verify_event(item, URL, NOW)
        self.assertEqual(decision, "accepted")
        self.assertTrue(event.time_tbc)
        self.assertEqual(datetime.fromisoformat(event.end_at).date().isoformat(), "2026-09-25")
        self.assertEqual(verify_event(item, URL, datetime(2026, 9, 26, tzinfo=timezone.utc))[2], "past_event")

    def test_same_day_dates_and_reversed_dates(self):
        self.assertEqual(verify_event(fixture(startDate="2026-10-21", endDate="2026-10-21"), URL, NOW)[1], "accepted")
        self.assertEqual(verify_event(fixture(startDate="2026-10-21", endDate="2026-10-20"), URL, NOW)[2], "invalid_end_date")

    def test_microdata_scopes_preserve_event_and_organiser_names(self):
        html = '''<article itemscope itemtype="https://schema.org/Event">
          <h1 itemprop="name">London Data Science Meetup</h1>
          <time itemprop="startDate" datetime="2026-10-21"></time>
          <time itemprop="endDate" datetime="2026-10-22"></time>
          <div itemprop="organizer" itemscope itemtype="https://schema.org/Organization">
            <span itemprop="name">Example community</span></div>
          <div itemprop="location" itemscope itemtype="https://schema.org/Place">
            <span itemprop="name">Example venue</span>
            <div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
              <span itemprop="addressLocality">London</span></div></div>
          </article><footer>Other event Paris</footer>'''
        with patch("src.events.candidates.fetch_html", return_value=html):
            result = inspect_candidate(URL, NOW)
        self.assertEqual(result.extraction, "microdata")
        self.assertEqual(result.decision, "accepted")
        self.assertEqual(result.events[0].organiser, "Example community")
        self.assertEqual(result.events[0].title, "London Data Science Meetup")

    def test_link_extraction_does_not_follow_navigation_or_foreign_hosts(self):
        from src.events.discovery_html import detail_links
        html = '<nav><a href="/events/nav">Nav</a></nav><a href="/events/data-science">Data</a><a href="https://other.example/events/one">Other</a><a href="/archive/events/old">Old</a>'
        self.assertEqual(detail_links(html, URL), ())  # self link excluded
        self.assertEqual(detail_links(html, "https://organiser.example/events/"), (URL,))

    def test_one_hop_fetches_detail_without_crawling_further(self):
        from src.events.candidates import inspect_candidates
        root = "https://organiser.example/events/"
        child = "https://organiser.example/events/child"
        grandchild = "https://organiser.example/events/grandchild"
        def page(url, **kwargs):
            return f'<a href="{child if url == root else grandchild}">Event</a>'
        with patch("src.events.candidates.fetch_html", side_effect=page) as fetch:
            inspections = inspect_candidates({root})
        self.assertEqual({i.url for i in inspections}, {root, child})
        self.assertEqual(fetch.call_count, 2)

    def test_budget_is_unchanged_with_many_detail_links(self):
        from src.events.candidates import inspect_candidates
        roots = {f"https://site{i}.example/events/" for i in range(80)}
        with patch("src.events.candidates.fetch_html", return_value='<a href="/events/detail">Data</a>') as fetch:
            results = inspect_candidates(roots)
        self.assertEqual(len(results), 48)
        self.assertEqual(fetch.call_count, 48)
        self.assertTrue(any(i.url.endswith('/detail') for i in results))

    def test_detail_priority_over_article_and_zero_budget(self):
        self.assertEqual(select_candidates({"https://a.example/blog/data-science", URL}, limit=1), [URL])
        self.assertEqual(select_candidates({URL}, limit=0), [])
