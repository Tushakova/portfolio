"""Web discovery for London Data Radar using Brave Search API."""

from src.events.candidates import (
    inspect_candidates,
)
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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

# Operational guardrail.
# The scheduled version will run at most once per day,
# so 10 queries/day is roughly 300-310 requests/month.
MAX_QUERIES_PER_RUN = 12

DIAGNOSTIC_QUERIES = (
    (
        "London Analytics Engineering Meetup #26",
        '"London Analytics Engineering Meetup" London',
    ),
    (
        "Big Data LDN 2026",
        '"Big Data LDN" 2026',
    ),
    (
        "MeasureCamp London 19",
        '"MeasureCamp London" 2026',
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

    Search results remain transient: they are used only during
    this process and are never written to disk.
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
    Run discovery without persisting Brave search results.

    Only aggregate counts and evaluation outcomes are logged.
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
    Test whether Brave can retrieve each known target when searched
    for directly.

    These queries evaluate the search provider only. They are not
    part of production discovery.
    """
    results: list[tuple[str, bool]] = []

    for target_name, query in DIAGNOSTIC_QUERIES:
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

    evaluation = evaluate_targets(
        discovered_urls
    )

    print("\nGeneric discovery targets")
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
        f"\nGeneric target recall: "
        f"{found_count}/{len(evaluation)}"
    )

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
