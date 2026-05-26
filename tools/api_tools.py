"""External API tools for public search integration."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import requests

from services.errors import ExternalServiceError

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": "agent-framework-demo/1.0 (research-assistant)",
    "Accept": "application/json",
}


def _empty_result(query: str, source: str, provider: str, error: str = "") -> dict[str, Any]:
    """Return a consistent empty result payload when API data is unavailable."""
    return {
        "query": query,
        "heading": "",
        "abstract": "",
        "related_topics": [],
        "result_count": 0,
        "source": source,
        "provider": provider,
        "references": [],
        "error": error,
    }


def _extract_related_topics(payload: dict[str, Any]) -> list[str]:
    """Extract related topic text items from DuckDuckGo-style payloads."""
    topics: list[str] = []
    for item in payload.get("RelatedTopics", []):
        if isinstance(item, dict) and "Text" in item:
            topics.append(str(item["Text"]))
        # DuckDuckGo can nest topics in a "Topics" list.
        nested_topics = item.get("Topics") if isinstance(item, dict) else None
        if isinstance(nested_topics, list):
            for nested in nested_topics:
                if isinstance(nested, dict) and "Text" in nested:
                    topics.append(str(nested["Text"]))
    return topics


def _is_microsoft_agent_framework_query(query: str) -> bool:
    """Return True when query appears to target Microsoft Agent Framework."""
    normalized = query.lower()
    return (
        "agent framework" in normalized
        and any(keyword in normalized for keyword in {"microsoft", "learn", "guide", "python", "agent"})
    )


def _search_microsoft_agent_framework(query: str, timeout: int) -> dict[str, Any]:
    """Retrieve Microsoft Agent Framework context from official public sources."""
    readme_url = "https://raw.githubusercontent.com/microsoft/agent-framework/main/README.md"
    repo_url = "https://github.com/microsoft/agent-framework"
    python_samples_url = (
        "https://github.com/microsoft/agent-framework/tree/main/python/samples"
    )

    response = requests.get(readme_url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()
    readme_text = response.text

    lines = [line.strip() for line in readme_text.splitlines()]
    candidate_lines: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("![") or line.startswith("[!["):
            continue
        if line.lower().startswith("<img"):
            continue
        if line.startswith("<"):
            continue

        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        if "![" in line or "badge" in line.lower() or "discord" in line.lower():
            continue
        if any(token in cleaned.lower() for token in {"youtube", "watch the full", "<a href", "alt="}):
            continue
        cleaned = cleaned.replace("`", "").strip()
        if len(cleaned) < 40:
            continue
        if cleaned and cleaned not in candidate_lines:
            candidate_lines.append(cleaned)
        if len(candidate_lines) >= 6:
            break

    if not candidate_lines:
        return _empty_result(
            query=query,
            source=readme_url,
            provider="github-readme",
            error="No usable content extracted from Microsoft Agent Framework README.",
        )

    return {
        "query": query,
        "heading": "Microsoft Agent Framework",
        "abstract": candidate_lines[0],
        "related_topics": candidate_lines,
        "result_count": len(candidate_lines),
        "source": readme_url,
        "provider": "github-readme",
        "references": [
            repo_url,
            readme_url,
            python_samples_url,
            "https://learn.microsoft.com/agent-framework/",
        ],
    }


def _build_topic_candidates(query: str) -> list[str]:
    """Build likely topic candidates from a natural-language user query."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s_-]", " ", query).strip()
    tokens = [token for token in cleaned.split() if token]
    stopwords = {
        "i",
        "want",
        "to",
        "learn",
        "create",
        "build",
        "write",
        "make",
        "guide",
        "for",
        "a",
        "an",
        "the",
        "beginners",
        "beginner",
        "about",
        "please",
    }

    filtered_tokens = [token for token in tokens if token.lower() not in stopwords]
    candidates: list[str] = [query.strip()]
    if filtered_tokens:
        candidates.append(" ".join(filtered_tokens))

    normalized_topic = " ".join(filtered_tokens).lower()
    if "dota2" in normalized_topic or "dota 2" in normalized_topic:
        candidates.append("Dota_2")
    if "valorant" in normalized_topic:
        candidates.append("Valorant")
    if "python" in normalized_topic:
        candidates.append("Python_(programming_language)")
        candidates.append("Python (programming language)")
    if "php" in normalized_topic:
        candidates.append("PHP")
        candidates.append("PHP (programming language)")
    if "javascript" in normalized_topic or "js" in normalized_topic:
        candidates.append("JavaScript")

    # Help generic learning prompts map to stronger factual topics.
    if "learn" in normalized_topic and "coding" in normalized_topic:
        candidates.append("Computer programming")
    if "learn" in normalized_topic and "programming" in normalized_topic:
        candidates.append("Computer programming")
    if "programming" in normalized_topic and "language" in normalized_topic:
        candidates.append("Programming language")

    if normalized_topic:
        candidates.append(normalized_topic)

    # Keep order and uniqueness.
    unique: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _search_stackexchange(query: str, timeout: int) -> tuple[list[str], list[str]]:
    """Get related topics from StackExchange using domain-aware site selection."""

    normalized = query.lower()
    programming_tokens = {
        "python",
        "php",
        "javascript",
        "typescript",
        "java",
        "c#",
        "golang",
        "rust",
        "coding",
        "programming",
        "code",
        "software",
        "developer",
        "debug",
        "algorithm",
    }
    gaming_tokens = {
        "dota",
        "valorant",
        "game",
        "gaming",
        "moba",
        "fps",
    }

    sites: list[str] = []
    if any(token in normalized for token in programming_tokens):
        sites.append("stackoverflow")
    if any(token in normalized for token in gaming_tokens):
        sites.append("gaming")
    if not sites:
        sites.extend(["stackoverflow", "gaming"])

    topics: list[str] = []
    references: list[str] = []
    for site in sites:
        response = requests.get(
            "https://api.stackexchange.com/2.3/search/advanced",
            params={
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": site,
                "pagesize": 5,
            },
            headers=REQUEST_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            continue

        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            link = str(item.get("link", "")).strip()
            if title:
                topics.append(f"[{site}] {title}")
            if link:
                references.append(link)

        if topics:
            break

    return topics, references


def _search_wikipedia(query: str, timeout: int) -> dict[str, Any]:
    """Fallback to Wikipedia summary API using topic candidates from the query."""
    logger.info("Falling back to Wikipedia summary lookup for query: %s", query)

    last_error = ""
    for candidate in _build_topic_candidates(query):
        try:
            summary_response = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(candidate.replace(' ', '_'))}",
                headers=REQUEST_HEADERS,
                timeout=timeout,
            )
            if summary_response.status_code == 404:
                continue
            summary_response.raise_for_status()

            summary_payload = summary_response.json()
            if not isinstance(summary_payload, dict):
                continue

            heading = str(summary_payload.get("title", candidate)).strip()
            summary_text = str(summary_payload.get("extract", "")).strip()
            page_url = ""
            content_urls = summary_payload.get("content_urls", {})
            if isinstance(content_urls, dict):
                desktop = content_urls.get("desktop", {})
                if isinstance(desktop, dict):
                    page_url = str(desktop.get("page", "")).strip()

            stack_topics: list[str] = []
            stack_refs: list[str] = []
            try:
                stack_topics, stack_refs = _search_stackexchange(candidate, timeout)
            except requests.RequestException:
                logger.warning("StackExchange enrichment failed for candidate: %s", candidate)

            related_topics = [topic for topic in stack_topics if topic.strip()]
            if summary_text:
                related_topics.insert(0, f"Wikipedia summary: {summary_text}")

            references: list[str] = []
            if page_url:
                references.append(page_url)
            references.extend(stack_refs)

            return {
                "query": query,
                "heading": heading,
                "abstract": summary_text,
                "related_topics": related_topics[:10],
                "result_count": len(related_topics),
                "source": "https://en.wikipedia.org/api/rest_v1/page/summary",
                "provider": "wikipedia",
                "references": references[:6],
            }
        except requests.RequestException as exc:
            last_error = str(exc)
            continue

    return _empty_result(
        query=query,
        source="https://en.wikipedia.org/api/rest_v1/page/summary",
        provider="wikipedia",
        error=last_error,
    )


def search_public_api(query: str, endpoint: str, timeout: int = 8) -> dict[str, Any]:
    """Search a public API endpoint and return validated structured output."""
    if not query.strip():
        raise ExternalServiceError("Query cannot be empty")

    logger.info("Calling public API for query: %s", query)
    duckduckgo_result = _empty_result(query=query, source=endpoint, provider="duckduckgo")

    try:
        response = requests.get(
            endpoint,
            params={"q": query, "format": "json", "no_html": 1},
            headers=REQUEST_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ExternalServiceError("Unexpected API response format")

        related_texts = _extract_related_topics(payload)
        duckduckgo_result = {
            "query": query,
            "heading": str(payload.get("Heading", "")),
            "abstract": str(payload.get("AbstractText", "")),
            "related_topics": related_texts[:10],
            "result_count": len(related_texts),
            "source": endpoint,
            "provider": "duckduckgo",
            "references": [str(payload.get("AbstractURL", ""))],
        }

        if duckduckgo_result["result_count"] > 0 or duckduckgo_result["abstract"].strip():
            logger.info("API call complete with %d related topics", duckduckgo_result["result_count"])
            return duckduckgo_result
    except requests.RequestException as exc:
        logger.warning("Primary API call failed, switching to Wikipedia fallback: %s", exc)
        duckduckgo_result["error"] = str(exc)

    if _is_microsoft_agent_framework_query(query):
        try:
            maf_result = _search_microsoft_agent_framework(query=query, timeout=timeout)
            if maf_result["result_count"] > 0 or maf_result["abstract"].strip():
                logger.info(
                    "Microsoft Agent Framework fallback returned %d related topics",
                    maf_result["result_count"],
                )
                return maf_result
        except requests.RequestException as exc:
            logger.warning("Microsoft Agent Framework fallback failed: %s", exc)

    try:
        wikipedia_result = _search_wikipedia(query=query, timeout=timeout)
        if wikipedia_result["result_count"] > 0 or wikipedia_result["abstract"].strip():
            logger.info("Wikipedia fallback returned %d related topics", wikipedia_result["result_count"])
            return wikipedia_result
    except requests.RequestException as exc:
        logger.warning("Wikipedia fallback failed: %s", exc)

    logger.info("No API evidence found; returning empty structured API result")
    return duckduckgo_result
