# London Data Radar

The public event finder lives at [tushakova.co.uk/events](https://tushakova.co.uk/events/). It uses only organisers' publicly published event information. It does not collect attendee or member details.

**Web-search prototype:** Brave Search now finds independent candidate sites and checks structured event facts in a separate manual workflow. It does not publish them yet. See [Web discovery and verification](docs/DISCOVERY.md) for the limits, decisions and next steps.

**New to the project?** Read [How London Data Radar works](docs/HOW_IT_WORKS.md) for a plain-English walkthrough of collection, filtering, refreshes, archives, failure handling and limitations.

## Data sources

- Royal Statistical Society London events
- Big Data LDN and MeasureCamp London event pages
- Public event listings for seven selected London Meetup groups: The Friendly Data Meetup, London Analytics Engineering Meetup, London Data Intelligence Network, London dbt Meetup, Data Science Festival London, Data Pub Social and CRAP Talks (conversion optimisation). Career-themed events receive a distinct Data Careers topic.
- Public London-wide Meetup search listings for data science, analytics and machine learning; these discover relevant events from other groups, subject to event-level topic, date and location checks.
- Data Science Festival organiser website: future London Career Day detail pages discovered from its website (past editions excluded)
- London Job Show organiser pages: a general two-day careers fair is included only while its own recruitment page explicitly lists data roles. It is labelled as a general fair, not a data-only fair.

The Meetup connector reads schema.org event data from group and London-wide search pages. It ignores cancelled or past events, irrelevant titles and events without confirmed in-person London venues or an explicit online/hybrid mode. For search-discovered groups, the event title itself must identify the data/analytics/statistics/experimentation topic. Hybrid events appear under both in-person and online filters. Missing end times and prices stay unknown; source event links have current booking details. A group with no relevant future event contributes no records. Search pages are a bounded sample of public listings, not an exhaustive search of Meetup or the whole web.

Search on the site filters the published event dataset; it does not search Google or all independent organiser sites. The Meetup discovery includes a bounded career-event query, and Career Day discovery checks the Data Science Festival website daily. Other standalone organisers must be added as new, validated sources; a visitor can submit a URL through the suggestion link on the page. Unknown event times are explicitly labelled Time TBC instead of inventing an hour. University-only career fairs are not included without checking who is eligible to attend.

Upcoming events are separated from the Past events tab. On each successful build, previously published events that have ended move into the archive even if the organiser no longer lists them. The first archive includes the previously verified Big Data LDN 2026 dataset record and the organiser's DSF Career Day 2026 page; earlier events not captured by the product cannot be reconstructed automatically. Past ticket prices and booking statuses are hidden because they become outdated. The expandable event change log records additions, updates, removals from a source and archiving, retaining the most recent 250 changes. Git history records the full evolution of the published JSON since tracking began.

## Refresh and deployment

`.github/workflows/refresh-events.yml` runs daily at 06:17 Europe/London (including summer/winter clock changes), on changes to ingestion code or this workflow on main, and can also be started manually from GitHub Actions. Scheduled runs may be delayed by GitHub; Codespaces does not need to be running. It validates events and commits `data/events.json` only when event facts change; it also commits `data/refresh-status.json` after every successful check. The dot is green when the last successful check was less than 36 hours ago, otherwise grey, with an explicit check time. The event-details timestamp changes only when event facts change. Missing Big Data LDN ticket prices remain unknown and do not block refreshes. If a source fails, it keeps the previously published dataset and marks the workflow failed so incomplete data are not silently published; the last successful check time then grows stale.

An isolated RSS event detail page can be temporarily unavailable even while the calendar works. In that case the refresh logs a warning, preserves that event's last verified details if already published, and continues with the other pages. If the entire RSS calendar or every detail page fails, the refresh still fails rather than silently clearing the source.

The public site deploys from the repository's `main` branch. A Codespace is only a temporary editor for making changes: **it does not need to run for the website or daily event refresh to work**. Stop Codespaces when finished; delete unused ones after checking for unpublished work.

For a local run:

```bash
python -m pip install -r requirements.txt
python -m src.events.build
```
