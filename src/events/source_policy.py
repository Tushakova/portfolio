"""Explicit evidence tiers, not automatic trust based on well-formed markup.

These finite lists describe source provenance, not organiser endorsement.
Unknown domains remain candidates and are never silently promoted to primary.
"""
from urllib.parse import urlsplit

PLATFORMS = {'meetup.com', 'eventbrite.co.uk', 'eventbrite.com', 'lu.ma', 'luma.com', 'tickettailor.com'}
ORGANISERS = {'datasciencefestival.com', 'london.measurecamp.org', 'bigdataldn.com',
              'rss.org.uk', 'turing.ac.uk', 'mrs.org.uk'}
CATALOGUES = {'conferencealerts.co.in', 'conferenceindex.org', 'internationalconferencealerts.com',
              'allevents.in', 'industryevents.com', 'aiml.events', 'dev.events'}


def source_kind(url: str) -> str:
    host = (urlsplit(url).hostname or '').lower().removeprefix('www.')
    # Exact hostname matching: a lookalike subdomain does not inherit trust.
    for domains, kind in ((PLATFORMS, 'platform'), (ORGANISERS, 'organiser'), (CATALOGUES, 'catalogue')):
        if host in domains:
            return kind
    return 'independent_unconfirmed'
