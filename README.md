# London Data Radar

The public event finder lives at [tushakova.co.uk/events](https://tushakova.co.uk/events/). It uses only organisers' publicly published event information. It does not collect attendee or member details.

## Data sources

- Royal Statistical Society London events
- Big Data LDN and MeasureCamp London event pages
- Public event listings for seven selected London Meetup groups: The Friendly Data Meetup, London Analytics Engineering Meetup, London Data Intelligence Network, London dbt Meetup, Data Science Festival London, Data Pub Social and CRAP Talks (conversion optimisation). Career-themed events receive a distinct Data Careers topic.
- Public London-wide Meetup search listings for data science, analytics and machine learning; these discover relevant events from other groups, subject to event-level topic, date and location checks.
- Data Science Festival organiser website: future London Career Day detail pages discovered from its website (past editions excluded)

The Meetup connector reads schema.org event data from group and London-wide search pages. It ignores cancelled or past events, irrelevant titles and events without confirmed in-person London venues or an explicit online/hybrid mode. For search-discovered groups, the event title itself must identify the data/analytics/statistics/experimentation topic. Hybrid events appear under both in-person and online filters. Missing end times and prices stay unknown; source event links have current booking details. A group with no relevant future event contributes no records. Search pages are a bounded sample of public listings, not an exhaustive search of Meetup or the whole web.

Search on the site filters the published event dataset; it does not search Google or all independent organiser sites. Career Day discovery checks the Data Science Festival website daily. Other standalone organisers must be added as new, validated sources; a visitor can submit a URL through the suggestion link on the page. Unknown event times are explicitly labelled Time TBC instead of inventing an hour. University-only career fairs are not included without checking who is eligible to attend.

## Refresh and deployment

`.github/workflows/refresh-events.yml` runs daily at 06:17 Europe/London (including summer/winter clock changes), on changes to ingestion code or this workflow on main, and can also be started manually from GitHub Actions. Scheduled runs may be delayed by GitHub; Codespaces does not need to be running. It validates events and commits `data/events.json` only when event facts change. Missing Big Data LDN ticket prices remain unknown and do not block refreshes. If a source fails, it keeps the previously published dataset and marks the workflow failed so incomplete data are not silently published.

An isolated RSS event detail page can be temporarily unavailable even while the calendar works. In that case the refresh logs a warning, preserves that event's last verified details if already published, and continues with the other pages. If the entire RSS calendar or every detail page fails, the refresh still fails rather than silently clearing the source.

The public site deploys from the repository's `main` branch. A Codespace is only a temporary editor for making changes: **it does not need to run for the website or daily event refresh to work**. Stop Codespaces when finished; delete unused ones after checking for unpublished work.

For a local run:

```bash
python -m pip install -r requirements.txt
python -m src.events.build
```
