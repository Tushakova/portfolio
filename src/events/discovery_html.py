"""Conservative HTML event extraction and one-hop detail-link discovery.

No dates are guessed from arbitrary page text. HTML microdata must explicitly
identify an Event scope; links are candidates only, never evidence of an event.
"""
from urllib.parse import urljoin, urlsplit
import re
from bs4 import BeautifulSoup
from src.events.source_policy import source_kind


def extract_microdata_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    def object_for(scope):
        result = {"@type": scope.get("itemtype", "").split("/")[-1]}
        for node in scope.select("[itemprop]"):
            # Each property belongs only to its nearest containing item scope.
            if node.find_parent(attrs={"itemscope": True}) is not scope:
                continue
            value = object_for(node) if node.has_attr("itemscope") else (
                node.get("content") or node.get("datetime") or node.get("href")
                or node.get("src") or node.get_text(" ", strip=True))
            for name in node.get("itemprop", "").split():
                if name in result:
                    result[name] = (result[name] if isinstance(result[name], list) else [result[name]]) + [value]
                else:
                    result[name] = value
        return result

    return [object_for(scope) for scope in soup.select("[itemscope][itemtype]")
            if re.fullmatch(r"https?://schema\.org/[A-Za-z]*Event", scope.get("itemtype", ""))]


def detail_links(html: str, page_url: str) -> tuple[str, ...]:
    """At most eight same-host event detail links, excluding navigation and archives."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["nav", "footer", "header"]):
        node.decompose()
    host = (urlsplit(page_url).hostname or "").removeprefix("www.")
    found = []
    for a in soup.select("a[href]"):
        url = urljoin(page_url, a["href"])
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or (parsed.hostname or "").removeprefix("www.") != host:
            continue
        if re.search(r"/(?:past|archive|category|tag|search|login|signup)(?:/|$)", parsed.path, re.I):
            continue
        is_detail = re.search(r"/(?:events?|e|talks?|conferences?|workshops?)/[^/]+", parsed.path, re.I)
        if is_detail and url not in found and url.rstrip("/") != page_url.rstrip("/"):
            found.append(url)
    # A catalogue may link explicitly to an organiser. Follow at most two
    # labelled links, never guess from ads or generic outbound navigation.
    official = []
    if source_kind(page_url) == "catalogue":
        for a in soup.select("a[href]"):
            label = a.get_text(" ", strip=True)
            if not re.fullmatch(r"(?:visit\s+)?(?:official|event|conference|organis[ez]er)\s+(?:web)?site(?:\s*(?:→|»))?", label, re.I):
                continue
            url = urljoin(page_url, a["href"])
            if urlsplit(url).scheme in ("http", "https") and urlsplit(url).hostname != urlsplit(page_url).hostname:
                official.append(url)
    return tuple(dict.fromkeys(official[:2] + found[:8]))
