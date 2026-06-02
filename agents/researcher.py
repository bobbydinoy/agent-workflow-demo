"""Research agent that collects source-backed context from local and API data."""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter
from typing import Any

from agent_framework import Executor, Message, WorkflowContext, handler

from tools.api_tools import search_public_api
from tools.file_tools import read_file
from tools.llm_tools import choose_research_tools_with_llm

logger = logging.getLogger(__name__)


def _is_note_content_relevant_to_goal(note_content: str, goal: str) -> bool:
    """Check if local notes are topically relevant to the user goal.
    
    Uses keyword matching to determine relevance without requiring LLM calls.
    Returns True if there's reasonable overlap, False if notes appear unrelated.
    """
    if not note_content.strip() or not goal.strip():
        return False
    
    # Extract keywords from both goal and notes
    goal_lower = goal.lower()
    note_lower = note_content.lower()
    
    # Split into words and filter out common stopwords
    stopwords = {
        "i", "want", "to", "learn", "research", "tell", "me", "about", "the", "a", "an",
        "and", "or", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "for", "in", "on", "at", "by", "from", "with", "as", "of"
    }
    
    def extract_keywords(text: str) -> set[str]:
        words = text.split()
        return {w.strip('.,!?;:"\'').lower() for w in words 
                if len(w.strip('.,!?;:"\'')) > 2 and w.lower() not in stopwords}
    
    goal_keywords = extract_keywords(goal)
    note_keywords = extract_keywords(note_lower)
    
    # Calculate overlap
    if not goal_keywords or not note_keywords:
        return False
    
    overlap = goal_keywords & note_keywords
    overlap_ratio = len(overlap) / len(goal_keywords)
    
    logger.debug(
        "Relevance check: goal=%s, overlap_keywords=%s, ratio=%.2f",
        goal_keywords, overlap, overlap_ratio
    )
    
    # Require at least 25% keyword overlap to consider notes relevant
    return overlap_ratio >= 0.25


class ResearchAgent(Executor):
    """Gather evidence from approved sources without inventing facts."""

    def __init__(
        self,
        notes_path: Path,
        api_endpoint: str,
        api_timeout: int,
        *,
        use_llm: bool = False,
        llm_api_key: str = "",
        llm_model: str = "gpt-5.4-mini",
        llm_endpoint: str = "https://api.openai.com/v1/chat/completions",
        llm_timeout: int = 20,
        llm_tool_routing: bool = True,
        enable_public_api: bool = False,
    ) -> None:
        super().__init__(id="research")
        self._notes_path = notes_path
        self._api_endpoint = api_endpoint
        self._api_timeout = api_timeout
        self._use_llm = use_llm
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_endpoint = llm_endpoint
        self._llm_timeout = llm_timeout
        self._llm_tool_routing = llm_tool_routing
        self._enable_public_api = enable_public_api

    @handler
    async def run(
        self,
        messages: list[Message],
        ctx: WorkflowContext[dict[str, Any], dict[str, Any]],
    ) -> None:
        """Collect local notes and API evidence from the latest user conversation message."""
        started = perf_counter()
        if not messages:
            raise ValueError("ResearchAgent requires at least one user message")

        latest_message = messages[-1]
        query = latest_message.text.strip()
        if not query:
            raise ValueError("ResearchAgent could not extract a query from workflow input")

        logger.info("ResearchAgent started for query: %s", query)

        # Check if local notes are relevant to the goal
        notes_text_candidate = read_file(str(self._notes_path))
        notes_are_relevant = _is_note_content_relevant_to_goal(notes_text_candidate, query)
        
        if notes_are_relevant:
            logger.info("Local notes are relevant to goal; including in tool selection")
        else:
            logger.info("Local notes are NOT relevant to goal; skipping local_notes tool")

        selected_tools = []
        if notes_are_relevant:
            selected_tools.append("local_notes")
        
        if self._enable_public_api:
            selected_tools.append("public_api")

        if self._use_llm and self._llm_tool_routing:
            routed = await choose_research_tools_with_llm(
                goal=query,
                api_key=self._llm_api_key,
                model=self._llm_model,
                endpoint=self._llm_endpoint,
                timeout=self._llm_timeout,
            )
            if routed:
                # LLM routing can suggest tools; respect if public_api is enabled in config
                selected_tools = routed
                # Always ensure local_notes are included if they're relevant
                if notes_are_relevant and "local_notes" not in selected_tools:
                    selected_tools.insert(0, "local_notes")
                # If public_api was disabled in config, remove it from routed selection
                if not self._enable_public_api and "public_api" in selected_tools:
                    selected_tools.remove("public_api")
            else:
                logger.info("LLM tool routing returned no tools; using default selection")

        notes_text = ""
        if "local_notes" in selected_tools:
            notes_text = read_file(str(self._notes_path))

        api_result: dict[str, Any] = {
            "references": [],
            "source": "",
            "query": query,
            "heading": "",
            "abstract": "",
            "related_topics": [],
            "result_count": 0,
            "provider": "disabled",
            "error": "public_api tool not selected",
        }
        if "public_api" in selected_tools:
            api_result = search_public_api(
                query=query,
                endpoint=self._api_endpoint,
                timeout=self._api_timeout,
            )

        references: list[str] = []
        if "local_notes" in selected_tools:
            references.append(str(self._notes_path))
        for reference in api_result.get("references", []):
            if isinstance(reference, str) and reference.strip():
                references.append(reference)
        source_name = str(api_result.get("source", "")).strip()
        if source_name:
            references.append(source_name)

        # Preserve order while removing duplicates.
        deduped_references: list[str] = []
        for reference in references:
            if reference not in deduped_references:
                deduped_references.append(reference)

        result: dict[str, Any] = {
            "goal": query,
            "selected_tools": selected_tools,
            "notes": {
                "content": notes_text,
                "length": len(notes_text),
                "source": str(self._notes_path),
            },
            "api": api_result,
            "references": deduped_references,
            "_telemetry": {
                "duration_ms": (perf_counter() - started) * 1000,
                "tool_calls": len(selected_tools),
            },
        }

        logger.info("ResearchAgent finished with %d references", len(result["references"]))

        await ctx.yield_output({"stage": "research", "payload": result})
        await ctx.send_message(result)
