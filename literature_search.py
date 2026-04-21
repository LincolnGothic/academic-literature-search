#!/usr/bin/env python3
"""Search academic literature sources from the command line.

This script currently supports:
- PubMed via the official NCBI E-utilities endpoints
- Google Scholar via lightweight HTML retrieval when available

Examples:
    python literature_search.py cancer immunotherapy
    python literature_search.py "graph neural networks" protein folding --source pubmed --source scholar --max-results 3
    python literature_search.py CRISPR --operator OR --format json --json-out results.json
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any


DEFAULT_USER_AGENT = "literature-search-cli/1.0 (+https://www.ncbi.nlm.nih.gov/)"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SCHOLAR_URL = "https://scholar.google.com/scholar"
MONTH_LOOKUP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


class SearchError(Exception):
    """Raised when a literature source cannot satisfy a query."""


@dataclass
class SearchResult:
    source: str
    title: str
    url: str
    authors: list[str] = field(default_factory=list)
    journal: str | None = None
    published: str | None = None
    snippet: str | None = None
    doi: str | None = None
    source_id: str | None = None


def collapse_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def join_keywords(keywords: list[str], operator: str) -> str:
    cleaned = [keyword.strip() for keyword in keywords if keyword.strip()]
    if len(cleaned) <= 1 or operator == "space":
        return " ".join(cleaned)
    glue = f" {operator.upper()} "
    return glue.join(cleaned)


def make_request(url: str, params: dict[str, Any], timeout: float, user_agent: str) -> bytes:
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise SearchError("Remote service rejected the request due to rate limiting.") from exc
        raise SearchError(f"HTTP {exc.code} while fetching {url}: {collapse_whitespace(body[:200])}") from exc
    except urllib.error.URLError as exc:
        raise SearchError(f"Network error while fetching {url}: {exc.reason}") from exc


def parse_json_response(payload: bytes) -> dict[str, Any]:
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SearchError("Received invalid JSON from remote service.") from exc


def itertext(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return collapse_whitespace("".join(element.itertext()))


def month_to_number(month: str | None) -> str | None:
    if not month:
        return None
    month = month.strip()
    if month.isdigit():
        return month.zfill(2)
    return MONTH_LOOKUP.get(month[:3].lower())


def build_iso_date(year: str | None, month: str | None = None, day: str | None = None) -> str | None:
    if not year:
        return None
    if not month:
        return year
    parts = [year, month.zfill(2)]
    if day and day.isdigit():
        parts.append(day.zfill(2))
    return "-".join(parts)


def extract_pubmed_date(article: ET.Element) -> str | None:
    article_date = article.find("./MedlineCitation/Article/ArticleDate")
    if article_date is not None:
        return build_iso_date(
            article_date.findtext("Year"),
            article_date.findtext("Month"),
            article_date.findtext("Day"),
        )

    pub_date = article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
    if pub_date is not None:
        year = pub_date.findtext("Year")
        month = month_to_number(pub_date.findtext("Month"))
        day = pub_date.findtext("Day")
        if year:
            return build_iso_date(year, month, day)
        medline_date = collapse_whitespace(pub_date.findtext("MedlineDate"))
        if medline_date:
            year_match = re.search(r"\b(19|20)\d{2}\b", medline_date)
            if year_match:
                return year_match.group(0)

    pubmed_date = article.find(".//PubMedPubDate[@PubStatus='pubmed']")
    if pubmed_date is not None:
        return build_iso_date(
            pubmed_date.findtext("Year"),
            pubmed_date.findtext("Month"),
            pubmed_date.findtext("Day"),
        )

    return None


def extract_pubmed_authors(article: ET.Element) -> list[str]:
    authors: list[str] = []
    for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
        collective = collapse_whitespace(author.findtext("CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        last_name = collapse_whitespace(author.findtext("LastName"))
        fore_name = collapse_whitespace(author.findtext("ForeName"))
        initials = collapse_whitespace(author.findtext("Initials"))
        name_parts = [part for part in [fore_name, last_name] if part]
        if name_parts:
            authors.append(" ".join(name_parts))
        elif last_name or initials:
            authors.append(" ".join(part for part in [initials, last_name] if part))
    return authors


def extract_pubmed_abstract(article: ET.Element) -> str:
    parts: list[str] = []
    for abstract_text in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
        label = collapse_whitespace(abstract_text.attrib.get("Label"))
        body = itertext(abstract_text)
        if not body:
            continue
        parts.append(f"{label}: {body}" if label else body)
    return " ".join(parts)


def search_pubmed(
    query: str,
    max_results: int,
    timeout: float,
    user_agent: str,
    email: str | None,
    api_key: str | None,
    sort: str,
) -> list[SearchResult]:
    esearch_params: dict[str, Any] = {
        "db": "pubmed",
        "retmode": "json",
        "retmax": max_results,
        "sort": "pub+date" if sort == "date" else "relevance",
        "term": query,
    }
    if email:
        esearch_params["email"] = email
    if api_key:
        esearch_params["api_key"] = api_key

    id_payload = make_request(PUBMED_ESEARCH_URL, esearch_params, timeout, user_agent)
    id_data = parse_json_response(id_payload)
    ids = id_data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    efetch_params: dict[str, Any] = {
        "db": "pubmed",
        "retmode": "xml",
        "id": ",".join(ids),
    }
    if email:
        efetch_params["email"] = email
    if api_key:
        efetch_params["api_key"] = api_key

    article_payload = make_request(PUBMED_EFETCH_URL, efetch_params, timeout, user_agent)
    try:
        root = ET.fromstring(article_payload)
    except ET.ParseError as exc:
        raise SearchError("Received invalid XML from PubMed.") from exc

    results: list[SearchResult] = []
    for article in root.findall("./PubmedArticle"):
        pmid = collapse_whitespace(article.findtext("./MedlineCitation/PMID"))
        title = itertext(article.find("./MedlineCitation/Article/ArticleTitle"))
        journal = itertext(article.find("./MedlineCitation/Article/Journal/Title")) or None
        doi = None
        for article_id in article.findall("./PubmedData/ArticleIdList/ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                doi = collapse_whitespace(article_id.text)
                break

        results.append(
            SearchResult(
                source="pubmed",
                source_id=pmid or None,
                title=title or "Untitled article",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "https://pubmed.ncbi.nlm.nih.gov/",
                authors=extract_pubmed_authors(article),
                journal=journal,
                published=extract_pubmed_date(article),
                snippet=extract_pubmed_abstract(article),
                doi=doi,
            )
        )
    return results


class ScholarHTMLParser(HTMLParser):
    """Parse a minimal subset of Google Scholar result HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._result_depth = 0
        self._capture_title = False
        self._capture_meta = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())

        if tag == "div" and "gs_ri" in classes:
            self._current = {"title": "", "url": "", "meta": "", "snippet": ""}
            self._result_depth = 1
            return

        if self._current is None:
            return

        if tag == "div":
            self._result_depth += 1
            if "gs_a" in classes:
                self._capture_meta = True
            elif "gs_rs" in classes:
                self._capture_snippet = True

        if tag == "h3" and "gs_rt" in classes:
            self._capture_title = True

        if self._capture_title and tag == "a" and not self._current.get("url"):
            self._current["url"] = attr_map.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return

        if tag == "h3":
            self._capture_title = False

        if tag == "div":
            if self._capture_meta:
                self._capture_meta = False
            elif self._capture_snippet:
                self._capture_snippet = False

            self._result_depth -= 1
            if self._result_depth <= 0:
                result = {
                    key: collapse_whitespace(html.unescape(value))
                    for key, value in self._current.items()
                }
                if result["title"]:
                    self.results.append(result)
                self._current = None

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return

        if self._capture_title:
            self._current["title"] += data
        elif self._capture_meta:
            self._current["meta"] += data
        elif self._capture_snippet:
            self._current["snippet"] += data


def parse_scholar_meta(meta: str) -> tuple[list[str], str | None, str | None]:
    published = None
    year_match = re.search(r"\b(19|20)\d{2}\b", meta)
    if year_match:
        published = year_match.group(0)

    parts = [part.strip() for part in meta.split(" - ") if part.strip()]
    authors_text = parts[0] if parts else ""
    authors = [
        collapse_whitespace(name)
        for name in re.split(r",|;|\.\.\.", authors_text)
        if collapse_whitespace(name)
    ]
    journal = parts[1] if len(parts) > 1 else None
    return authors, journal, published


def search_google_scholar(
    query: str,
    max_results: int,
    timeout: float,
    user_agent: str,
    language: str,
) -> list[SearchResult]:
    params = {
        "hl": language,
        "q": query,
        "num": min(max_results, 20),
    }
    search_url = f"{SCHOLAR_URL}?{urllib.parse.urlencode(params)}"
    try:
        payload = make_request(SCHOLAR_URL, params, timeout, user_agent)
    except SearchError as exc:
        raise SearchError(
            "Google Scholar blocked or rejected the automated request. "
            f"Try opening this query in a browser: {search_url}"
        ) from exc
    parser = ScholarHTMLParser()
    parser.feed(payload.decode("utf-8", errors="replace"))

    results: list[SearchResult] = []
    for item in parser.results[:max_results]:
        authors, journal, published = parse_scholar_meta(item.get("meta", ""))
        url = item.get("url") or search_url
        results.append(
            SearchResult(
                source="scholar",
                title=item.get("title") or "Untitled result",
                url=url,
                authors=authors,
                journal=journal,
                published=published,
                snippet=item.get("snippet") or None,
            )
        )

    if not results:
        raise SearchError(
            "Google Scholar returned no parsable results. "
            f"The request may have been blocked or the page structure may have changed. Try: {search_url}"
        )
    return results


def truncate(value: str | None, max_length: int) -> str | None:
    if not value:
        return None
    value = collapse_whitespace(value)
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def result_to_dict(result: SearchResult, snippet_length: int) -> dict[str, Any]:
    payload = asdict(result)
    payload["snippet"] = truncate(payload.get("snippet"), snippet_length)
    return payload


def run_search(
    *,
    keywords: list[str],
    operator: str = "and",
    sources: list[str] | None = None,
    max_results: int = 5,
    sort: str = "relevance",
    timeout: float = 20.0,
    email: str | None = None,
    api_key: str | None = None,
    scholar_lang: str = "en",
    snippet_length: int = 500,
    quiet_errors: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[str, dict[str, list[SearchResult]], dict[str, str], dict[str, Any]]:
    selected_sources = sources or ["pubmed"]
    query = join_keywords(keywords, operator)
    results_by_source: dict[str, list[SearchResult]] = {}
    errors: dict[str, str] = {}

    for source in selected_sources:
        try:
            if source == "pubmed":
                results = search_pubmed(
                    query=query,
                    max_results=max_results,
                    timeout=timeout,
                    user_agent=user_agent,
                    email=email,
                    api_key=api_key,
                    sort=sort,
                )
            elif source == "scholar":
                results = search_google_scholar(
                    query=query,
                    max_results=max_results,
                    timeout=timeout,
                    user_agent=user_agent,
                    language=scholar_lang,
                )
            else:
                raise SearchError(f"Unsupported source: {source}")
            results_by_source[source] = results
        except SearchError as exc:
            results_by_source[source] = []
            errors[source] = str(exc)
            if not quiet_errors:
                print(f"[{source}] {exc}", file=sys.stderr)

    payload = {
        "query": query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": selected_sources,
        "results": {
            source: [result_to_dict(item, snippet_length) for item in items]
            for source, items in results_by_source.items()
        },
        "errors": errors,
    }
    return query, results_by_source, errors, payload


def render_text(query: str, results_by_source: dict[str, list[SearchResult]], snippet_length: int) -> str:
    lines = [f"Query: {query}", ""]
    total = sum(len(items) for items in results_by_source.values())
    lines.append(f"Total results: {total}")
    lines.append("")

    for source, items in results_by_source.items():
        lines.append(f"{source.upper()} RESULTS ({len(items)})")
        lines.append("-" * len(lines[-1]))
        if not items:
            lines.append("No results found.")
            lines.append("")
            continue

        for index, item in enumerate(items, start=1):
            lines.append(f"[{index}] {item.title}")
            meta_parts = [f"Source: {item.source}"]
            if item.journal:
                meta_parts.append(f"Journal: {item.journal}")
            if item.published:
                meta_parts.append(f"Published: {item.published}")
            if item.authors:
                meta_parts.append("Authors: " + ", ".join(item.authors[:6]))
            lines.append(" | ".join(meta_parts))
            if item.doi:
                lines.append(f"DOI: {item.doi}")
            lines.append(f"URL: {item.url}")
            snippet = truncate(item.snippet, snippet_length)
            if snippet:
                lines.append("Summary:")
                lines.extend(textwrap.wrap(snippet, width=100))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search academic literature sources such as PubMed and Google Scholar.",
    )
    parser.add_argument(
        "keywords",
        nargs="+",
        help="One or more keywords or quoted phrases to search for.",
    )
    parser.add_argument(
        "--operator",
        choices=["and", "or", "space"],
        default="and",
        help="How to combine multiple keywords. Default: and.",
    )
    parser.add_argument(
        "--source",
        dest="sources",
        choices=["pubmed", "scholar"],
        action="append",
        help="Select one or more sources. Defaults to pubmed.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum results per source. Default: 5.",
    )
    parser.add_argument(
        "--sort",
        choices=["relevance", "date"],
        default="relevance",
        help="Result order for sources that support sorting. Default: relevance.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path to write the JSON payload.",
    )
    parser.add_argument(
        "--snippet-length",
        type=int,
        default=500,
        help="Maximum number of characters per abstract or snippet. Default: 500.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Network timeout in seconds. Default: 20.",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("NCBI_EMAIL"),
        help="Email for NCBI API etiquette. Defaults to NCBI_EMAIL if set.",
    )
    parser.add_argument(
        "--ncbi-api-key",
        default=os.environ.get("NCBI_API_KEY"),
        help="Optional NCBI API key. Defaults to NCBI_API_KEY if set.",
    )
    parser.add_argument(
        "--scholar-lang",
        default="en",
        help="Google Scholar interface language. Default: en.",
    )
    parser.add_argument(
        "--quiet-errors",
        action="store_true",
        help="Suppress per-source error messages in stderr.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.max_results < 1:
        print("--max-results must be at least 1.", file=sys.stderr)
        return 2

    query, results_by_source, errors, payload = run_search(
        keywords=args.keywords,
        operator=args.operator,
        sources=args.sources,
        max_results=args.max_results,
        sort=args.sort,
        timeout=args.timeout,
        email=args.email,
        api_key=args.ncbi_api_key,
        scholar_lang=args.scholar_lang,
        snippet_length=args.snippet_length,
        quiet_errors=args.quiet_errors,
    )

    if args.format == "json":
        output = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        output = render_text(query, results_by_source, args.snippet_length)
        if errors:
            output += "\nWarnings:\n"
            for source, message in errors.items():
                output += f"- {source}: {message}\n"

    print(output)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    return 0 if any(results_by_source.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
