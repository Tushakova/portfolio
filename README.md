# London Data Radar

The public event finder lives at [tushakova.co.uk/events](https://tushakova.co.uk/events/). It uses only organisers' publicly published event information. It does not collect attendee or member details.

## Data sources

- Royal Statistical Society London events
- Big Data LDN and MeasureCamp London event pages
- Public event listings for four London Meetup groups: The Friendly Data Meetup, London Analytics Engineering Meetup, London Data Intelligence Network, and London dbt Meetup

The Meetup connector reads schema.org event data from group pages. Missing prices are shown as unknown; the source event link has current booking details. A group with no future London event contributes no records.

## Refresh and deployment

`.github/workflows/refresh-events.yml` runs once a day at 07:17 UTC and can also be started manually from GitHub Actions. It validates events and commits `data/events.json` only when event facts change. If a source fails, it keeps the previously published dataset and marks the workflow failed so incomplete data are not silently published.

The public site deploys from the repository's `main` branch. A Codespace is only a temporary editor for making changes: **it does not need to run for the website or daily event refresh to work**. Stop Codespaces when finished; delete unused ones after checking for unpublished work.

For a local run:

```bash
python -m pip install -r requirements.txt
python -m src.events.build
```
