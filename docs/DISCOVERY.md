# Web search: discovery and verification

There are three different kinds of search in London Data Radar:

| Feature | What it does | When it runs |
| --- | --- | --- |
| Website search box | Filters already published events | When a visitor types |
| Production collectors | Refresh configured organiser pages and public Meetup listings | Daily at 06:17 Europe/London |
| Brave web discovery | Finds candidate websites and checks event facts | Manually through **Test event discovery** in GitHub Actions |

Web discovery is an experimental verification stage. It does not automatically publish search results. Verified candidates can now be reviewed, imported and then checked by the daily collectors.

## What happens in a discovery run

1. Python sends 12 London data, analytics, science, experimentation and careers queries, including three platform-targeted queries for Meetup, Eventbrite and Luma, to Brave Search API. Each requests up to 20 results. The key comes from the GitHub secret `BRAVE_SEARCH_API_KEY`; never put it in source code. Requests are paced, but the account's actual quota still applies.
2. Search URLs are deduplicated, ignoring tracking parameters but preserving meaningful query parameters. A URL is a candidate, not an event. Multiple results can describe the same event or a general calendar.
3. At most 48 pages are checked, spread across domains. Event-detail paths and topical URLs are prioritised over generic articles, courses and search pages. First, up to 24 search-result pages are fetched: capacity is reserved for 8 platform pages, 7 configured-organiser pages, 8 independent pages and at most one catalogue page. Unused capacity is redistributed to non-catalogue sources. This is a starting allocation, not a guarantee of useful results. The remaining budget checks event-detail links found on those pages; unused slots check more search results. Links are followed one level deep: normally at most eight same-host detail links. Known catalogues can also supply up to two explicitly labelled official/event website links. Catalogue-to-catalogue links are not followed. DSF career-day navigation links are an explicit exception because the actual dates must be checked on their detail pages. Four workers fetch pages, with a 10-second request timeout, one attempt and a 2 MB HTML limit. The workflow has an overall 10-minute limit. The selected sample is deterministic, not exhaustive.
4. Beautiful Soup reads the fetched HTML. The verifier checks up to 20 schema.org Event records per page, using each event's own name, description, dates and location. It supports JSON-LD and explicitly scoped HTML microdata. If neither is available, the exact configured Big Data LDN and MeasureCamp URLs, plus DSF Career Day detail URLs, can use existing organiser-specific HTML parsers without downloading them again. Other unstructured pages remain in review. Keywords elsewhere on the page are insufficient.
5. Each page receives a decision. Verified records are deduplicated against each other and against published and archived events. By default only aggregate counts are logged. `--show-events` additionally logs the title, dates, format, organiser and source URL of unique new source-supported events, extracted from fetched event pages, for human review. The GitHub workflow enables this flag. Public workflow logs therefore contain these public event facts. Raw Brave response bodies and snippets are never saved; the published event dataset is unchanged by search. The workflow exports independently fetched new event facts to `discovery-candidates.json`; no raw search responses or snippets are stored.

## Decisions

- **accepted**: event facts pass the checks and were retrieved from a configured organiser domain or recognised event platform. `organiser_event` and `platform_listing` are distinct: a platform listing is not independently corroborated by an organiser website.
- **rejected**: the available event evidence shows an off-topic/course listing, a past or cancelled event, or a venue outside London.
- **review**: evidence is incomplete or unavailable, or provenance still needs checking. Even a fully populated Event record from a catalogue or unknown independent domain receives `source_confirmation_needed`, not automatic primary-source status. These pages can supply detail/official links for the second fetch stage. An unknown legitimate organiser is not rejected; its provenance still needs review.

Source lists are explicit in `src/events/source_policy.py`. They describe where facts were retrieved, not an endorsement of an organiser or an event. A catalogue calling a link “official” does not grant that destination automatic trust. The destination is fetched and assessed independently. Unsupported independent sites need a reviewed source registration or further corroboration before publication.

In-person events need a London address. Online events need explicit online attendance data and a London connection in their own description or name; hybrid events need an explicit mixed format and London venue. Unspecified prices remain unknown. Date-only starts or ends are marked Time TBC. A date-only end is treated as inclusive through the last London calendar day; the internal end-of-day boundary is not a claimed closing hour. Reversed dates are invalid. Accepted new records can be exported for human review; unconfirmed records are not exported for publication. Career events and career fairs receive separate topic labels when their titles support them.

The page-level reason is representative: if a calendar has mixed outcomes, accepted takes precedence, then review. Event counts are separate from page counts. `fact_checked_records` counts records passing factual rules before source confirmation. `organiser_records`, `platform_records` and `unconfirmed_source_records` report provenance separately; these are record counts before deduplication. `new_source_supported_events` excludes known events, duplicates and unconfirmed sources. None of these records is published by this workflow. Finding a familiar organiser URL in the coverage checks does not prove that a current event was verified.

## Running it

In GitHub, open **Actions → Test event discovery → Run workflow** on `main`. Leave the additional diagnostics box unchecked for the normal 12-query run. Selecting it adds three direct searches for known targets, bringing the total to 15. These extra searches measure provider coverage, not new-event discovery. Codespaces does not need to run.

Locally, install `requirements.txt`, set the API key securely in the environment, then run:

```bash
python -m unittest discover -s tests
python -m src.events.search
```

Inspect `Pages inspected`, the decision/reason counts, and `new_source_supported_events`. A run finding 180 URLs has not found 180 usable events. A successful run with zero accepted events is possible and does not change the website. API or account errors fail the run; individual inaccessible candidate pages go to review.

## Next development step

Use real-run aggregate results to identify the biggest bottleneck. If most pages lack structured Event data, add tested extraction for useful organiser sites, rather than relaxing the date/location rules. The prototype does not render JavaScript; candidate files are retained as Actions artifacts for 14 days. Its one-hop link extraction follows event-like same-host paths plus explicitly labelled organiser links on known catalogues; it does not crawl arbitrary external navigation. HTML without Event microdata still needs a tested organiser-specific parser. Its deterministic page budget can repeatedly leave the same URLs unchecked. Topic matching is rule based and still needs precision/coverage evaluation.

Before connecting this to daily publication, add an explicit search budget, a maintainable candidate-review process, stronger event identity tests and safe handling of discovery outages. Daily source refresh already works independently; scheduling the web-search prototype would introduce additional API usage and should be a separate deliberate change.

## September 2026 improvement and handoff

Known Meetup/Eventbrite event IDs are excluded before fetching, including archive entries. Reusable homepages and calendars are deliberately rechecked so next year's conference is not lost. Record-level matching still compares date plus URL or title/organiser. Detail links are followed even from accepted calendars: finding one valid record does not imply all linked events were checked.

The unchanged budget is 12 API queries and at most 48 page fetches. Half the page budget is reserved for detail links; unused capacity returns to search results. Unknown organisers remain review candidates, not automatically trusted sources.

Read the `New source-supported events for review` section of the workflow log. A known Big Data LDN record must not appear there. `already_published` counts website/archive matches; `duplicate_records` counts repeated copies within this run. Known-page URL coverage is a search benchmark, not the new-event list. If no new events pass, the report explicitly says so.

This patch was tested with mocked HTTP and search fixtures, not a paid live Brave run. The next validation is one GitHub workflow run with diagnostics off. Inspect its new-event section before enabling any publication. This change does not schedule Brave searches or auto-publish candidates. Keep the API key in GitHub Secrets.


## October 2026: review-to-publication handoff

1. Run **Test event discovery** with diagnostics off. Open the completed run and download the **discovery-candidates** artifact. Search still uses 12 API calls and at most 48 page checks.
2. Extract `discovery-candidates.json`. Review dates, London connection, subject relevance, public eligibility and organiser links. Remove unwanted records from its `events` array. Do not manually invent fields or promote records marked review.
3. Upload the reviewed JSON to the repository root in Codespaces and run:

```bash
python -m src.events.sources.reviewed --approve discovery-candidates.json
python -m src.events.build
```

The import re-fetches every selected page and requires a currently accepted record with the same ID. Changed dates, cancelled events, blocked pages and changed parsers stop import for review. Import also excludes events already published or archived and duplicate imports. Only page facts are persisted in `data/discovered-events.json`.

4. Inspect `git diff -- data/discovered-events.json data/events.json data/refresh-status.json`, then commit and push those files. A change to `data/discovered-events.json` triggers the ordinary refresh workflow.
5. Approved sources are checked daily without calling Brave. At most 30 approved event pages are supported. Past approved records remain in the archive and are no longer fetched. Prune their registry entries when approaching the cap; the archive is unaffected. A source that can no longer confirm an approved upcoming event fails the refresh and preserves the last publication rather than silently deleting it. Investigate the warning and remove cancelled records from the registry after review.

This establishes a working human-reviewed publication route. Brave discovery itself remains manual; daily API searches and automatic publication are not enabled. Use a few real runs to measure relevant-event yield before deciding whether a weekly discovery schedule is worthwhile. No new paid API queries are introduced into the daily refresh.

## Change-log identity

Upcoming and archived records are both considered known. A past event still listed by an organiser is not newly added on every check. The transition from Upcoming to Past is logged once. Repeated historical `added` entries from the earlier bug are removed while retaining the earliest entry and actual updates. Exact online cross-posts with the same long title, start instant and end time are displayed once even when Meetup group links differ; different dates remain distinct.
