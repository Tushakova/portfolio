"""Web discovery for London Data Radar using Brave Search API."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.events.candidates import inspect_candidates, summarise_events, MAX_PAGES
from src.events.discovery import (
    SEARCH_QUERIES,
    domain_diagnostics,
    evaluate_targets,
)


API_URL = (
    "https://api.search.brave.com/"
    "res/v1/web/search"
)

RESULTS_PER_QUERY = 20
REQUEST_TIMEOUT_SECONDS = 20

# 12 generic discovery queries per run.
MAX_QUERIES_PER_RUN = 12


DIAGNOSTIC_QUERIES = (
    (
        "London Analytics Engineering Meetup #26",
        '"London Analytics Engineering Meetup" London',
    ),
    (
        "Big Data LDN",
        '"Big Data LDN" London',
    ),
    (
        "MeasureCamp London",
        '"MeasureCamp London"',
    ),
)


class SearchError(RuntimeError):
    """Raised when web discovery cannot complete safely."""


@dataclass(frozen=True)
class SearchSummary:
    query_count: int
    result_count: int
    unique_url_count: int


def get_api_key() -> str:
    """Read the Brave API key from the environment."""
    api_key = os.environ.get(
        "BRAVE_SEARCH_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise SearchError(
            "BRAVE_SEARCH_API_KEY is not configured"
        )

    return api_key


def search_web(
    query: str,
    api_key: str,
) -> list[dict]:
    """
    Run one Brave web search.

    Search results remain transient and are never written to disk.
    """
    parameters = urlencode(
        {
            "q": query,
            "country": "GB",
            "search_lang": "en",
            "ui_lang": "en-GB",
            "count": RESULTS_PER_QUERY,
            "safesearch": "moderate",
        }
    )

    request = Request(
        f"{API_URL}?{parameters}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": (
                "LondonDataRadar/0.1 "
                "(+https://tushakova.co.uk)"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = json.load(response)

    except HTTPError as exc:
        if exc.code in (402, 429):
            raise SearchError(
                "Brave Search quota or rate limit reached"
            ) from exc

        raise SearchError(
            f"Brave Search returned HTTP {exc.code}"
        ) from exc

    except (URLError, TimeoutError) as exc:
        raise SearchError(
            f"Brave Search request failed: {exc}"
        ) from exc

    results = (
        payload
        .get("web", {})
        .get("results", [])
    )

    if not isinstance(results, list):
        raise SearchError(
            "Unexpected Brave Search response format"
        )

    return results


def discover() -> tuple[
    set[str],
    SearchSummary,
]:
    """
    Run generic discovery queries.

    Brave result data remains in memory. Only aggregate
    diagnostics are logged.
    """
    api_key = get_api_key()

    queries = SEARCH_QUERIES[
        :MAX_QUERIES_PER_RUN
    ]

    discovered_urls: set[str] = set()
    total_results = 0

    for index, query in enumerate(
        queries,
        start=1,
    ):
        if index > 1:
            time.sleep(1.1)
        results = search_web(
            query,
            api_key,
        )

        total_results += len(results)

        for result in results:
            url = result.get("url")

            if isinstance(url, str) and url:
                discovered_urls.add(url)

        print(
            f"Query {index}/{len(queries)}: "
            f"{len(results)} result(s)"
        )

    summary = SearchSummary(
        query_count=len(queries),
        result_count=total_results,
        unique_url_count=len(discovered_urls),
    )

    return discovered_urls, summary


def run_target_diagnostics(
    api_key: str,
) -> list[tuple[str, bool]]:
    """
    Check whether Brave can retrieve known evaluation targets
    when they are searched for directly.

    These searches diagnose provider coverage only. They are not
    part of production event discovery.
    """
    results: list[tuple[str, bool]] = []

    for target_name, query in DIAGNOSTIC_QUERIES:
        time.sleep(1.1)
        search_results = search_web(
            query,
            api_key,
        )

        target_tokens = {
            token.casefold()
            for token in target_name.split()
            if len(token) > 2
        }

        found = False

        for result in search_results:
            searchable_text = " ".join(
                str(result.get(field, ""))
                for field in (
                    "title",
                    "url",
                    "description",
                )
            ).casefold()

            matched_tokens = sum(
                token in searchable_text
                for token in target_tokens
            )

            if (
                target_tokens
                and matched_tokens
                >= max(
                    2,
                    len(target_tokens) - 1,
                )
            ):
                found = True
                break

        results.append(
            (
                target_name,
                found,
            )
        )

    return results


def main() -> None:
    """Run discovery and print aggregate diagnostics."""
    parser = argparse.ArgumentParser(description="Bounded event discovery; no publication or saved search results.")
    parser.add_argument("--diagnostics", action="store_true", help="Use three extra API queries on known-target diagnostics")
    args = parser.parse_args()
    discovered_urls, summary = discover()

    print("\nDiscovery summary")
    print("-----------------")
    print(
        f"Queries:     {summary.query_count}"
    )
    print(
        f"Results:     {summary.result_count}"
    )
    print(
        f"Unique URLs: {summary.unique_url_count}"
    )

    print("\nDomain diagnostics")
    print("------------------")

    diagnostics = domain_diagnostics(
        discovered_urls
    )

    for domain, count in diagnostics.items():
        print(
            f"{domain:<18} {count}"
        )

    print("\nCandidate inspection")
    print("--------------------")

    inspections = inspect_candidates(
        discovered_urls
    )

    print(f"URL candidates:   {len(discovered_urls)}")
    print(f"Pages inspected:  {len(inspections)} (cap {MAX_PAGES})")
    print("Page decisions:")
    for (decision, reason), count in sorted(Counter((i.decision, i.reason) for i in inspections).items()):
        print(f"  {decision:<10} {reason:<38} {count}")
    previous = json.loads(Path("data/events.json").read_text(encoding="utf-8"))
    counts = summarise_events(inspections, previous.get("events", []) + previous.get("past_events", []))
    print("\nVerified event records (not published):")
    for label, count in counts.items():
        print(f"  {label:<28} {count}")
    print("Only pages within the budget were assessed. Review is not acceptance.")
    print("Search results and extracted candidates were not saved or added to the website.")

    evaluation = evaluate_targets(
        discovered_urls
    )

    print("\nKnown-page URL coverage (not event acceptance)")
    print("-------------------------")

    found_count = 0

    for name, found in evaluation:
        status = (
            "FOUND"
            if found
            else "NOT FOUND"
        )

        print(
            f"{status}: {name}"
        )

        if found:
            found_count += 1

    print(
        f"\nKnown-page URL matches: "
        f"{found_count}/{len(evaluation)}"
    )

    if not args.diagnostics:
        print("\nDirect diagnostics skipped (use --diagnostics for 3 extra API queries).")
        return

    print("\nDirect-search diagnostics")
    print("-------------------------")

    api_key = get_api_key()

    direct_results = run_target_diagnostics(
        api_key
    )

    direct_found = 0

    for name, found in direct_results:
        status = (
            "FOUND"
            if found
            else "NOT FOUND"
        )

        print(
            f"{status}: {name}"
        )

        if found:
            direct_found += 1

    print(
        f"\nDirect-search recall: "
        f"{direct_found}/{len(direct_results)}"
    )


if __name__ == "__main__":
    main()
