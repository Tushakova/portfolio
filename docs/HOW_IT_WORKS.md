# London Data Radar — how it works

London Data Radar is a small, public event finder for people interested in data analytics, data science, statistics and experimentation in London. The live page is [tushakova.co.uk/events](https://tushakova.co.uk/events/). It offers a curated, automatically refreshed set of events; it is not a complete index of every event on the web.

## What a visitor sees

The page reads the published [`data/events.json`](../data/events.json) and shows upcoming events in date order. Visitors can search the **events already collected**, filter by subject (including data careers and career fairs), price when free entry has been verified, and attendance format (in person, online or hybrid). Each card links to the organiser's event page. An event spanning two days appears as one card with both dates.

The separate Past events view contains events the product has previously recorded. Historical prices and registration states are not shown because those details can become misleading. The expandable Event change log shows recently added, updated, archived and removed events. The dot next to the status turns green when a successful data check occurred within the previous 36 hours. The “Event details updated” timestamp records when the underlying event information last changed; it can be older than the most recent successful check.

## Where the events come from

| Source | How discovery works | Important boundary |
| --- | --- | --- |
| Royal Statistical Society | Read its public event index, then fetch and parse eligible event pages. | The calendar and event pages must remain accessible; unrelated RSS events are excluded. |
| Meetup | Read seven selected public London group pages **and** a bounded set of London-wide searches for data science, analytics, machine learning and data careers. Extract published schema.org event data. | New Meetup groups can appear via these searches, but search results are not exhaustive. No private member information is collected. |
| Big Data LDN and MeasureCamp London | Fetch each organiser's public event page and extract the published dates, venue and other available details. | They are individual configured websites, not general web search. A changed layout may need a parser update. |
| Data Science Festival | Discover Career Day pages from its public site and verify their dates and London venue. | Other events on its site are not automatically added by this connector. |
| London Job Show | Check the visitor page for dates, hours and free registration, and its IT recruitment page for an explicit reference to data roles. | This is a **general** careers fair. We do not imply that every exhibitor has a data job. |

A separate [Brave web-search prototype](DISCOVERY.md) now discovers independent sites and verifies structured event facts. It runs manually, logs aggregate diagnostics and does not publish events yet.

A new independent event site will not appear on the public radar just because Google indexes it. The “Search the wider web” link opens a separate Google search for the visitor; it does not import results into the radar. A new standalone organiser requires a specific source parser and validation. The site has an email link for suggesting one. University-only fairs are excluded unless eligibility for the wider public is confirmed.

## How an event becomes a card

1. [GitHub Actions](../.github/workflows/refresh-events.yml) starts the Python program `python -m src.events.build` after installing the dependency in [`requirements.txt`](../requirements.txt) and running the tests.
2. The five connectors in [`src/events/sources/`](../src/events/sources/) fetch public HTML with Python's standard-library `urllib.request`. They use **Beautiful Soup** to read HTML; Meetup event details are read from its public schema.org structured data. This project does not currently use the Meetup API or a Google search API.
3. Each connector turns supported events into one common [`Event`](../src/events/models.py) record: ID, title, local start/end, format, organiser, source link, venue, price/free status if known, registration status and topics. Unknown facts remain unknown. London times include a time-zone offset; an unconfirmed event hour is labelled “Time TBC”.
4. The pipeline [deduplicates and validates](../src/events/validation.py) IDs, URLs, dates, formats, topic labels and price consistency. Events that have ended move into the archive, including events a source no longer lists. It compares the new records with the previous publication to make the change log.
5. A successful run writes [`data/events.json`](../data/events.json) if event details changed and updates [`data/refresh-status.json`](../data/refresh-status.json) with the last successful check time. The workflow commits these files to `main`. The site's browser code in [`events/index.html`](../events/index.html) fetches them and renders the cards and status.

The first archive contained the previously published Big Data LDN 2026 event and the organiser's DSF Career Day 2026 page. Events from before the product began collecting data cannot be recovered from the archive automatically. The visible change log retains the latest 250 changes; Git preserves committed versions of the data files.

## When it updates, and what you need to do

The [refresh workflow](../.github/workflows/refresh-events.yml) is scheduled daily at **06:17 Europe/London**, adjusting for British Summer Time. It also runs after changes to the ingestion code or workflow are pushed to `main`. You can run it from the repository's **Actions → Refresh events → Run workflow** if you want an immediate check. A GitHub Codespace does **not** need to be running. GitHub can delay a scheduled run, so 06:17 is a target time rather than a guaranteed completion time.

A normal day needs no manual input. As a visitor, check the page's “Last successful check” status and open an event's organiser link before booking. As the maintainer, it is sensible to check the site and [Actions runs](https://github.com/Tushakova/portfolio/actions/workflows/refresh-events.yml) occasionally, especially after an organiser changes its website. For public repositories GitHub may disable scheduled workflows after an extended period without repository activity; the Actions page is the place to verify that scheduling remains enabled.

## What happens if something breaks

| Symptom | What it means | What to check |
| --- | --- | --- |
| Grey dot or “check overdue” | No successful refresh in the last 36 hours. | Open the latest **Refresh events** run under Actions and read the failing step. |
| A failed `Build events dataset` step | One or more source pages could not be fetched or parsed, or validation failed. | Read the individual `WARNING:` lines above the final error. A temporary outage may clear on a later run; a changed page format needs a source parser update. |
| The event-details date is older than the check time | A check succeeded without changing event facts. | This is normal; look at the last successful check time for freshness. |
| An expected event is missing | The organiser is outside configured sources, a public search did not return it, or validation filtered it out. | Check its organiser link, eligibility, location and whether a connector covers it. |
| An event link is old or an event has changed | The source removed or updated information after the last check. | Verify details with the organiser; if it keeps happening, amend the relevant parser. |

The pipeline deliberately fails a run instead of publishing an incomplete replacement when a configured source fails. The previously published data remains online, and the last successful check time gradually becomes stale. The output is *event discovery*, so the organiser's page remains the authority for tickets and last-minute changes.

## Running and changing it locally

From the repository root, with Python 3.12 available:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python -m src.events.build
```

The third command fetches live public pages and may change the JSON files. Review changes with `git diff` before committing. To add a source, write or adapt a connector under `src/events/sources/`, add it to the collectors in [`src/events/build.py`](../src/events/build.py), return validated `Event` objects, and test both valid and changed/missing fields. Include a working original organiser URL and enforce eligibility, topic, date and London venue where applicable. Avoid inventing prices or times.

## Current limits and next decisions

- Coverage is deliberately selective. Google-wide crawling, Eventbrite-wide search and guaranteed discovery of every standalone event are **not implemented**. The Brave prototype provides bounded web discovery and verification, but integration with daily publication and a review process remain future work.
- Parsers depend on organisers' public pages. Changed markup, blocked requests and temporary source outages can interrupt a scheduled refresh; the last verified dataset is retained.
- The on-page status is the **last successful check**, not a live indicator of an Actions job in progress or a guarantee that every event link still accepts bookings.
- Hosting/deployment account settings are outside this repository. The public domain currently serves the repository's event files, but a future hosting change must keep `/events/`, `/data/events.json` and `/data/refresh-status.json` accessible together.

These are maintenance and coverage limits, not prerequisites for using the current product. Add another source when it would materially improve the relevance of the listings rather than collecting every event on the web.
