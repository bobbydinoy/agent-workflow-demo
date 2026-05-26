"""Optional LLM helper tools for guide generation.

This module is intentionally isolated so the app can run in non-LLM mode
without requiring any model credentials.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

from agent_framework import Message
from agent_framework_openai import OpenAIChatClient, OpenAIChatCompletionClient

logger = logging.getLogger(__name__)


def _validate_guide_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Validate and normalize the expected LLM guide schema."""
    title = str(payload.get("title", "")).strip()
    target_audience = str(payload.get("target_audience", "Beginners")).strip() or "Beginners"
    limitations = str(payload.get("limitations", "")).strip()

    evidence_raw = payload.get("evidence", [])
    starter_plan_raw = payload.get("starter_plan", [])

    if not isinstance(evidence_raw, list) or not isinstance(starter_plan_raw, list):
        return None

    evidence = [str(item).strip() for item in evidence_raw if str(item).strip()][:8]
    starter_plan = [str(item).strip() for item in starter_plan_raw if str(item).strip()][:6]

    if not title or not evidence or len(starter_plan) < 3:
        return None

    return {
        "title": title,
        "target_audience": target_audience,
        "evidence": evidence,
        "starter_plan": starter_plan,
        "limitations": limitations
        or "Generated from provided evidence and references.",
    }


def _parse_json_content(content: str) -> dict[str, Any] | None:
    """Parse plain or fenced JSON content from model responses."""
    raw = content.strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            inner = "\n".join(lines[1:-1]).strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            try:
                parsed = json.loads(inner)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None

    return None


def _derive_openai_base_url(endpoint: str) -> str | None:
    """Convert a chat-completions endpoint into a base URL for SDK clients."""
    endpoint = endpoint.strip()
    if not endpoint:
        return None

    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None

    base = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            return base[: -len(suffix)]

    return base


async def generate_beginner_guide_with_llm(
    *,
    goal: str,
    evidence_points: list[str],
    references: list[str],
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int,
    enable_web_search: bool = True,
    search_context_size: str = "high",
) -> dict[str, Any] | None:
    """Generate a beginner guide with an LLM and return structured JSON output.

    Returns None if generation fails so callers can fall back to deterministic logic.
    """
    if not api_key.strip():
        logger.info("LLM disabled at runtime: missing API key")
        return None

    if not evidence_points:
        logger.info("LLM generation skipped: no evidence points available")
        return None

    system_prompt = (
        "You are a teaching assistant that creates beginner-friendly guides. "
        "Prioritize accurate, source-backed answers. "
        "If web search is available, use it to improve factual coverage. "
        "Return strict JSON with keys: title, target_audience, evidence, starter_plan, limitations."
    )

    evidence_block = "\n".join([f"- {item}" for item in evidence_points[:8]])
    references_block = "\n".join([f"- {item}" for item in references[:8]])

    user_prompt = (
        f"Goal: {goal}\n"
        "Audience: Beginners\n"
        "Create a practical guide with 4-6 starter steps.\n"
        "For evidence, prefer high-confidence facts and include source-oriented statements.\n"
        "Provided Evidence:\n"
        f"{evidence_block}\n"
        "Provided References:\n"
        f"{references_block}\n"
        "Do not output markdown. Return JSON only."
    )

    base_url = _derive_openai_base_url(endpoint)

    messages = [
        Message(role="system", contents=[system_prompt]),
        Message(role="user", contents=[user_prompt]),
    ]

    allowed_context_sizes = {"low", "medium", "high"}
    context_size = search_context_size.lower().strip()
    if context_size not in allowed_context_sizes:
        context_size = "high"

    base_options: dict[str, Any] = {
        "temperature": 0.2,
        "max_tokens": 900,
    }

    async def _request_with_completion_client() -> str | None:
        completion_client = OpenAIChatCompletionClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

        response = await completion_client.get_response(
            messages,
            options=base_options,
            client_kwargs={
                "timeout": timeout,
                "response_format": {"type": "json_object"},
            },
        )
        return response.text.strip()

    async def _request_with_web_search() -> str | None:
        chat_client = OpenAIChatClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        web_options = {
            **base_options,
            "tools": [
                OpenAIChatClient.get_web_search_tool(
                    search_context_size=context_size,
                )
            ],
        }

        response = await chat_client.get_response(
            messages,
            options=web_options,
            client_kwargs={"timeout": timeout},
        )
        return response.text.strip()

    try:
        content = None
        if enable_web_search:
            try:
                content = await _request_with_web_search()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "LLM web-search path failed; retrying without web search: %s",
                    exc,
                )

        if not content:
            content = await _request_with_completion_client()

        if not content:
            return None

        parsed = _parse_json_content(content)
        if parsed is None:
            return None

        return _validate_guide_payload(parsed)
    except (ValueError, json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
        logger.warning("LLM guide generation failed, using deterministic fallback: %s", exc)
        return None


async def choose_research_tools_with_llm(
    *,
    goal: str,
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int,
) -> list[str] | None:
    """Let the model select research tools for the current goal.

    Returns a subset of: local_notes, public_api.
    """
    if not api_key.strip():
        return None

    base_url = _derive_openai_base_url(endpoint)
    if not base_url:
        return None

    messages = [
        Message(
            role="system",
            contents=[
                "You are a tool-routing assistant. "
                "Return strict JSON only with key 'tools' as a list. "
                "Allowed values: local_notes, public_api."
            ],
        ),
        Message(
            role="user",
            contents=[
                f"Goal: {goal}\nChoose tools for best factual coverage."
            ],
        ),
    ]

    try:
        completion_client = OpenAIChatCompletionClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        response = await completion_client.get_response(
            messages,
            options={"temperature": 0.0, "max_tokens": 120},
            client_kwargs={
                "timeout": timeout,
                "response_format": {"type": "json_object"},
            },
        )
        parsed = _parse_json_content(response.text.strip())
        if not isinstance(parsed, dict):
            return None

        raw = parsed.get("tools", [])
        if not isinstance(raw, list):
            return None

        allowed = {"local_notes", "public_api"}
        selected = [str(item).strip() for item in raw if str(item).strip() in allowed]
        deduped: list[str] = []
        for item in selected:
            if item not in deduped:
                deduped.append(item)
        return deduped or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tool routing model call failed, using default tool set: %s", exc)
        return None
