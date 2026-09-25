"""Guard date and location rules for independently refreshed event sources."""

import unittest
import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.events.http import FetchError
from src.events.models import Event
from src.events.sources.dsf import discover_career_urls, parse_career_day
from src.events.sources.meetup import GROUPS, parse_event
from src.events.sources import rss
from src.events.sources.rss import infer_topics, parse_event_page
from src.events.sources.standalone import parse_big_data_ldn, parse_measurecamp, EventParseError
from src.events.topics import CAREERS
from src.events.build import build_dataset
from src.events.sources.career_fairs import parse_london_job_show
from src.events.topics import CAREER_FAIRS, is_career_fair


class EventSourceTests(unittest.TestCase):
    def test_measurecamp_edition_tracks_organiser_and_fails_if_missing(self):
        html = """MeasureCamp London 20 is happening 18th September 2027.
        Saturday 18 Sep, 2027 Starting at 8.30am doors open
        Etc Venues Fenchurch Street 8 Fenchurch Pl, London EC3M 4PB"""
        event = parse_measurecamp(html, "https://london.measurecamp.org/registration/")
        self.assertEqual(event.id, "measurecamp-london-20-2027")
        self.assertEqual(event.title, "MeasureCamp London 20")
        with self.assertRaises(EventParseError):
            parse_measurecamp(html.replace("London 20 is happening", "London is happening"),
                              "https://london.measurecamp.org/registration/")

    def test_career_fair_requires_data_roles_and_real_dates(self):
        page = "16th & 17th October 2026 Westfield London, Ariel Way 11am – 5pm on both days Free entry Register free"
        fair = parse_london_job_show(page, "Hiring Data Management Professionals")
        self.assertEqual(fair.start_at, "2026-10-16T11:00:00+01:00")
        self.assertEqual(fair.end_at, "2026-10-17T17:00:00+01:00")
        self.assertIn(CAREER_FAIRS, fair.topics)
        with self.assertRaises(ValueError):
            parse_london_job_show(page, "Hiring shop assistants")
        self.assertTrue(is_career_fair("London Career Fair"))
        self.assertFalse(is_career_fair("Data Science Career Talk"))

    def test_past_events_survive_disappearance_from_source(self):
        event = Event(id="old-data-fair", title="Old fair",
                      start_at="2026-09-23T09:00:00+01:00",
                      end_at="2026-09-24T17:00:00+01:00",
                      format="in_person", organiser="Example", source="Example",
                      source_url="https://example.com/", topics=(CAREER_FAIRS,))
        first = build_dataset([event], now=datetime(2026, 9, 23, tzinfo=timezone.utc))
        second = build_dataset([], first, datetime(2026, 9, 25, tzinfo=timezone.utc))
        self.assertEqual(second["event_count"], 0)
        self.assertEqual(second["past_events"][0]["id"], "old-data-fair")
        self.assertEqual(second["changes"][-1]["action"], "archived")
        third = build_dataset([], second, datetime(2026, 9, 26, tzinfo=timezone.utc))
        self.assertEqual(third["past_events"], second["past_events"])

    def test_big_data_dates_follow_the_published_year(self):
        html = """
        22-23 September 2027 Olympia London
        BDL Visitor Pass £49
        Hammersmith Road London W14 8UX
        Opening hours Wednesday 09:00 - 18:00 Thursday 09:00 - 17:30
        """
        event = parse_big_data_ldn(html, "https://www.bigdataldn.com/")
        self.assertEqual(event.start_at, "2027-09-22T09:00:00+01:00")
        self.assertEqual(event.end_at, "2027-09-23T17:30:00+01:00")
        self.assertEqual(event.id, "big-data-ldn-2027")
        self.assertEqual(event.price_from_gbp, 49.0)
        self.assertFalse(event.is_free)

    def test_big_data_missing_price_is_unknown_not_a_source_failure(self):
        html = """
        23-24 September 2026 Olympia London
        Hammersmith Road London W14 8UX
        Opening hours Wednesday 09:00 - 18:00 Thursday 09:00 - 17:30
        """
        event = parse_big_data_ldn(html, "https://www.bigdataldn.com/")
        self.assertEqual(event.start_at, "2026-09-23T09:00:00+01:00")
        self.assertEqual(event.end_at, "2026-09-24T17:30:00+01:00")
        self.assertIsNone(event.price_from_gbp)
        self.assertIsNone(event.is_free)

    def test_meetup_only_accepts_future_scheduled_london_events(self):
        event_data = {
            "name": "The Friendly Data Meetup",
            "url": "https://www.meetup.com/the-friendly-data-meetup/events/316572897/",
            "startDate": "2026-09-28T18:00:00.000Z",
            "endDate": "2026-09-28T21:00:00.000Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": "The Ledger Building", "address": {
                "addressLocality": "London", "streetAddress": "4 Hertsmere Road, London"
            }},
        }
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        event = parse_event(event_data, GROUPS[0], now)
        self.assertEqual(event.start_at, "2026-09-28T19:00:00+01:00")
        self.assertIsNone(event.is_free)

        outside_london = {**event_data, "location": {"@type": "Place", "address": {"addressLocality": "Manchester"}}}
        self.assertIsNone(parse_event(outside_london, GROUPS[0], now))
        cancelled = {**event_data, "eventStatus": "https://schema.org/EventCancelled"}
        self.assertIsNone(parse_event(cancelled, GROUPS[0], now))

    def test_meetup_modes_and_unrelated_meetup_posts(self):
        base = {
            "name": "Data Science London: Bayesian Modelling",
            "url": "https://www.meetup.com/another-london-group/events/316572897/",
            "startDate": "2026-10-21T12:00:00Z",
            "endDate": "2026-10-21T13:00:00Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "organizer": {"name": "New London Analytics Group"},
        }
        from src.events.sources.meetup import MeetupGroup, discovered_topics
        group = MeetupGroup("another-london-group", "New London Analytics Group",
                            discovered_topics(base["name"]))
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        virtual = {"@type": "VirtualLocation", "url": base["url"]}
        physical = {"@type": "Place", "name": "London venue",
                    "address": {"addressLocality": "London"}}
        online = parse_event({**base, "eventAttendanceMode":
            "https://schema.org/OnlineEventAttendanceMode", "location": virtual,
            "endDate": ""},
            group, now, discovered=True)
        self.assertEqual(online.format, "online")
        self.assertIsNone(online.end_at)
        self.assertEqual(online.organiser, "New London Analytics Group")
        hybrid = parse_event({**base, "eventAttendanceMode":
            "https://schema.org/MixedEventAttendanceMode", "location": [virtual, physical]},
            group, now, discovered=True)
        self.assertEqual(hybrid.format, "hybrid")
        self.assertIsNone(parse_event({**base, "name": "AI & Society Run & Coffee Club",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": physical}, group, now, discovered=True))
        self.assertIsNone(parse_event({**base, "eventAttendanceMode":
            "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "address": {"addressLocality": "Paris"}}},
            group, now, discovered=True))

    def test_rss_online_only_if_topic_is_explicit(self):
        base = """<h1>Data science in practice</h1>
            Date: Thursday 29 October 2026, 1.00PM - 3.00PM
            Location: Online
            RSS Event
        """
        event = parse_event_page(base, "https://rss.org.uk/training-events/events/events-2026/rss-events/data-science/")
        self.assertEqual(event.format, "online")
        self.assertIsNone(parse_event_page(base.replace("Data science in practice", "Member welcome"),
            "https://rss.org.uk/training-events/events/events-2026/rss-events/member-welcome/"))

    def test_one_unavailable_rss_page_keeps_last_verified_event(self):
        previous = Event(id="rss-example", title="Statistical lecture",
                         start_at="2026-10-29T13:00:00+00:00", format="in_person",
                         organiser=rss.SOURCE_NAME, source=rss.SOURCE_NAME,
                         source_url="https://rss.org.uk/example/")

        def fetch(url):
            if url == previous.source_url:
                raise FetchError("temporary timeout")
            return "<html></html>"

        with patch.object(rss, "fetch_html", side_effect=fetch), \
                patch.object(rss, "discover_event_urls", return_value=[
                    previous.source_url, "https://rss.org.uk/other/"]), \
                patch.object(rss, "parse_event_page", return_value=None), \
                patch.object(rss.Path, "read_text", return_value=json.dumps({
                    "events": [previous.to_dict()]})):
            events, errors = rss.get_events()
        self.assertEqual(events, [previous])
        self.assertEqual(errors, [])

    def test_career_meetup_is_career_only_when_title_matches(self):
        item = {
            "name": "DSF Career Day 2027",
            "url": "https://www.meetup.com/data-science-festival-london/events/316572897/",
            "startDate": "2027-09-28T11:00:00Z",
            "endDate": "2027-09-28T18:00:00Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": "CodeNode", "address": {"addressLocality": "London"}},
        }
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        group = next(g for g in GROUPS if g.slug == "data-science-festival-london")
        self.assertIn(CAREERS, parse_event(item, group, now).topics)
        self.assertNotIn(CAREERS, parse_event({**item, "name": "Data Vibe Coding"}, group, now).topics)

    def test_dsf_career_day_requires_a_future_london_date(self):
        listing = '<a href="/event/career-day-2027/">Career Day</a>'
        self.assertEqual(discover_career_urls(listing), {
            "https://datasciencefestival.com/event/career-day-2027/"
        })
        past = '<h3>DSF Career Day 2026</h3><p>Thursday 17th September 2026 | CodeNode, London</p>'
        future = '<h3>DSF Career Day 2027</h3><p>Friday 17th September 2027 | CodeNode, London</p>'
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        self.assertIsNone(parse_career_day(past, "https://datasciencefestival.com/event/career-day-2026/", now))
        event = parse_career_day(future, "https://datasciencefestival.com/event/career-day-2027/", now)
        self.assertEqual(event.start_at, "2027-09-17T00:00:00+01:00")
        self.assertTrue(event.time_tbc)
        self.assertIn(CAREERS, event.topics)

    def test_rss_career_titles_are_tagged_without_tagging_generic_talks(self):
        self.assertIn(CAREERS, infer_topics("Data science career fair"))
        self.assertNotIn(CAREERS, infer_topics("Statistics research lecture"))


if __name__ == "__main__":
    unittest.main()
