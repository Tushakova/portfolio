"""Guard date and location rules for independently refreshed event sources."""

import unittest
from datetime import datetime, timezone

from src.events.sources.meetup import GROUPS, parse_event
from src.events.sources.standalone import parse_big_data_ldn


class EventSourceTests(unittest.TestCase):
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

    def test_meetup_only_accepts_future_scheduled_london_events(self):
        event_data = {
            "name": "The Friendly Data Meetup",
            "url": "https://www.meetup.com/the-friendly-data-meetup/events/316572897/",
            "startDate": "2026-09-28T18:00:00.000Z",
            "endDate": "2026-09-28T21:00:00.000Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"name": "The Ledger Building", "address": {
                "addressLocality": "London", "streetAddress": "4 Hertsmere Road, London"
            }},
        }
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        event = parse_event(event_data, GROUPS[0], now)
        self.assertEqual(event.start_at, "2026-09-28T19:00:00+01:00")
        self.assertIsNone(event.is_free)

        outside_london = {**event_data, "location": {"address": {"addressLocality": "Manchester"}}}
        self.assertIsNone(parse_event(outside_london, GROUPS[0], now))
        cancelled = {**event_data, "eventStatus": "https://schema.org/EventCancelled"}
        self.assertIsNone(parse_event(cancelled, GROUPS[0], now))


if __name__ == "__main__":
    unittest.main()
