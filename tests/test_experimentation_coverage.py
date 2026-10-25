"""Regression coverage for discovery, venue corroboration and topic precision."""
import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

from src.events.sources.meetup import (
    GROUPS, SEARCH_URLS, MAX_ORGANISER_PAGES, MeetupGroup,
    discovered_topics, organiser_links, parse_event, resolve_event,
)
from src.events.topics import EXPERIMENTATION, DATA_SCIENCE, DATA_ENGINEERING
from src.events.validation import deduplicate_events
from src.events.http import FetchError

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)
GROUP = MeetupGroup('example-experiments', 'Example Experimentation Community', (EXPERIMENTATION,))
URL = 'https://organiser.example/next-meetup'


def listing(**updates):
    data = dict(
        name='Experimentation Community Meetup #14',
        url='https://www.meetup.com/example-experiments/events/123456789/',
        description=f'Buy tickets on the [event website]({URL}).',
        startDate='2026-12-09T18:00:00Z', endDate='2026-12-09T20:00:00Z',
        eventStatus='https://schema.org/EventScheduled',
        eventAttendanceMode='https://schema.org/OfflineEventAttendanceMode',
        location={'@type':'Place','address':{'addressLocality':''}},
    )
    data.update(updates)
    return data


def detail(**updates):
    data = listing(location={'@type':'Place','name':'Community Hall','address':{
        'addressLocality':'London EC1M 4BS', 'streetAddress':'10 Example Lane'}},
        endDate='2026-12-09T20:30:00Z')
    data.update(updates)
    return '<script type="application/ld+json">'+json.dumps({'@type':'Event', **data})+'</script>'


class ExperimentationCoverageTests(unittest.TestCase):
    def test_search_covers_experimentation_without_one_event_id(self):
        self.assertTrue(any('keywords=experimentation' in url for url in SEARCH_URLS))
        self.assertTrue(any('A%2FB' in url for url in SEARCH_URLS))
        self.assertTrue(any('conversion%20rate' in url for url in SEARCH_URLS))
        self.assertTrue(any(g.slug == 'experimentation-london' for g in GROUPS))
        self.assertFalse(any('317046809' in url for url in SEARCH_URLS))

    def test_real_world_missing_venue_pattern_is_resolved_and_cached(self):
        cache = {}
        self.assertIsNone(parse_event(listing(), GROUP, NOW))
        with patch('src.events.sources.meetup.fetch_html', return_value=detail()) as fetch:
            event = resolve_event(listing(), GROUP, cache, NOW, discovered=True)
            again = resolve_event(listing(), GROUP, cache, NOW, discovered=True)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(event, again)
        self.assertEqual(event.id, 'meetup-123456789')
        self.assertEqual(event.source_url, URL)
        self.assertEqual(event.end_at, '2026-12-09T20:30:00+00:00')
        self.assertEqual(event.address, '10 Example Lane')
        self.assertIn(EXPERIMENTATION, event.topics)
        self.assertIsNone(event.is_free)

    def test_wrong_event_date_cancelled_and_foreign_are_not_corroboration(self):
        for html in (
            detail(name='A different experimentation meetup'),
            detail(startDate='2026-12-10T18:00:00Z'),
            detail(eventStatus='https://schema.org/EventCancelled'),
            detail(location={'@type':'Place','address':{'addressLocality':'Paris'}}),
            '<footer>London EC1M 4BS</footer>',
        ):
            with self.subTest(html=html), patch('src.events.sources.meetup.fetch_html', return_value=html):
                self.assertIsNone(resolve_event(listing(), GROUP, {}, NOW, discovered=True))

    def test_does_not_replace_explicit_foreign_venue_or_fetch_past_event(self):
        with patch('src.events.sources.meetup.fetch_html') as fetch:
            self.assertIsNone(resolve_event(listing(location={'@type':'Place','address':{'addressLocality':'Paris'}}), GROUP, {}, NOW))
            self.assertIsNone(resolve_event(listing(startDate='2025-12-09T18:00:00Z'), GROUP, {}, NOW))
            self.assertIsNone(resolve_event(listing(), GROUP, {str(i):[] for i in range(MAX_ORGANISER_PAGES)}, NOW))
            fetch.assert_not_called()

    def test_topic_precision_and_multiple_labels(self):
        for title in ('Modernize Databases Faster with AI-Assisted Migration and Optimization',
                      'Benchmarking optimization tasks, cost & quality with Bob'):
            self.assertNotIn(EXPERIMENTATION, discovered_topics(title))
        for title in ('Experimentation London #14', 'A/B Testing in practice',
                      'Conversion Rate Optimisation', 'Experiment design',
                      'Split-testing for products', 'Marketing incrementality'):
            self.assertIn(EXPERIMENTATION, discovered_topics(title))
        self.assertEqual(discovered_topics('Data Science and A/B testing'), (DATA_SCIENCE, EXPERIMENTATION))
        self.assertEqual(discovered_topics('Database Optimization'), (DATA_ENGINEERING,))

    def test_known_groups_also_receive_experimentation_tag(self):
        data = listing(location={'@type':'Place','address':{'addressLocality':'London'}})
        event = parse_event(data, replace(GROUP, topics=(DATA_SCIENCE,)), NOW)
        self.assertIn(EXPERIMENTATION, event.topics)

    def test_link_bounds_and_private_or_irrelevant_links(self):
        self.assertEqual(organiser_links('[sponsor](https://sponsor.example/) [website](http://localhost/) [tickets](https://127.0.0.1/)'), [])
        with patch('src.events.sources.meetup.fetch_html', return_value=detail()):
            event = resolve_event(listing(), GROUP, {}, NOW)
        copy = replace(event, source_url=listing()['url'])
        self.assertEqual(len(deduplicate_events([event, copy])), 1)

    def test_failed_optional_page_is_cached_and_does_not_repeat_requests(self):
        cache = {}
        with patch('src.events.sources.meetup.fetch_html', side_effect=FetchError('timeout')) as fetch:
            for _ in range(2):
                with self.assertRaises(FetchError):
                    resolve_event(listing(), GROUP, cache, NOW)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(len(cache), 1)


if __name__ == '__main__':
    unittest.main()
