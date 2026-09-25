# Web search: discovery and verification

There are three different kinds of search in London Data Radar:

| Feature | What it does | When it runs |
| --- | --- | --- |
| Website search box | Filters already published events | When a visitor types |
| Production collectors | Refresh configured organiser pages and public Meetup listings | Daily at 06:17 Europe/London |
| Brave web discovery | Finds candidate websites and checks event facts | Manually through **Test event discovery** in GitHub Actions |

Web discovery is an experimental verification stage. It does **not** yet add events to the website or replace the daily collectors.

## What happens in a discovery run

1. Python sends 12 London data, analytics, science, experimentation and careers queries, including three platform-targeted queries for Meetup, Eventbrite and Luma, to Brave Search API. Each requests up to 20 results. The key comes from the GitHub secret `BRAVE_SEARCH_API_KEY`; never put it in source code. Requests are paced, but the account's actual quota still applies.
2. Search URLs are deduplicated, ignoring tracking parameters but preserving meaningful query parameters. A URL is a candidate, not an event. Multiple results can describe the same event or a general calendar.
3. At most 48 pages are checked, spread across domains. Event-detail paths and topical URLs are prioritised over generic articles, courses and search pages. First, up to 36 search-result pages are fetched: capacity is reserved for 12 platform pages, 10 configured-organiser pages, 12 independent pages and at most two catalogue pages. Unused capacity is redistributed to non-catalogue sources. This is a starting allocation, not a guarantee of useful results. The remaining budget checks event-detail links found on those pages; unused slots check more search results. Links are followed one level deep: normally at most eight same-host detail links. Known catalogues can also supply up to two explicitly labelled official/event website links. Catalogue-to-catalogue links are not followed. DSF career-day navigation links are an explicit exception because the actual dates must be checked on their detail pages. Four workers fetch pages, with a 10-second request timeout, one attempt and a 2 MB HTML limit. The workflow has an overall 10-minute limit. The selected sample is deterministic, not exhaustive.
4. Beautiful Soup reads the fetched HTML. The verifier checks up to 20 schema.org Event records per page, using each event's own name, description, dates and location. It supports JSON-LD and explicitly scoped HTML microdata. If neither is available, the exact configured Big Data LDN and MeasureCamp URLs, plus DSF Career Day detail URLs, can use existing organiser-specific HTML parsers without downloading them again. Other unstructured pages remain in review. Keywords elsewhere on the page are insufficient.
5. Each page receives a decision. Verified records are deduplicated against each other and against published and archived events. Only aggregate counts, extraction methods and domain/reason counts are logged; raw Brave URLs, snippets and extracted candidate records remain in memory and are not saved.

## Decisions

- **accepted**: event facts pass the checks and were retrieved from a configured organiser domain or recognised event platform. `organiser_event` and `platform_listing` are distinct: a platform listing is not independently corroborated by an organiser website.
- **rejected**: the available event evidence shows an off-topic/course listing, a past or cancelled event, or a venue outside London.
- **review**: evidence is incomplete or unavailable, or provenance still needs checking. Even a fully populated Event record from a catalogue or unknown independent domain receives `source_confirmation_needed`, not automatic primary-source status. These pages can supply detail/official links for the second fetch stage. An unknown legitimate organiser is not rejected; its provenance still needs review.

Source lists are explicit in `src/events/source_policy.py`. They describe where facts were retrieved, not an endorsement of an organiser or an event. A catalogue calling a link “official” does not grant that destination automatic trust. The destination is fetched and assessed independently. Unsupported independent sites need a reviewed source registration or further corroboration before publication.

In-person events need a London address. Online events need explicit online attendance data and a London connection in their own description or name; hybrid events need an explicit mixed format and London venue. Unspecified prices remain unknown. Date-only starts or ends are marked Time TBC. A date-only end is treated as inclusive through the last London calendar day; the internal end-of-day boundary is not a claimed closing hour. Reversed dates are invalid. These records remain transient and are not sent to the website. Career events and career fairs receive separate topic labels when their titles support them.

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

Use real-run aggregate results to identify the biggest bottleneck. If most pages lack structured Event data, add tested extraction for useful organiser sites, rather than relaxing the date/location rules. The prototype does not render JavaScript or keep a persistent review queue. Its one-hop link extraction follows event-like same-host paths plus explicitly labelled organiser links on known catalogues; it does not crawl arbitrary external navigation. HTML without Event microdata still needs a tested organiser-specific parser. Its deterministic page budget can repeatedly leave the same URLs unchecked. Topic matching is rule based and still needs precision/coverage evaluation.

Before connecting this to daily publication, add an explicit search budget, a maintainable candidate-review process, stronger event identity tests and safe handling of discovery outages. Daily source refresh already works independently; scheduling the web-search prototype would introduce additional API usage and should be a separate deliberate change.
