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
        llm_model: str = "gpt-4o-mini",
        llm_endpoint: str = "https://api.openai.com/v1/chat/completions",
        llm_timeout: int = 20,
        llm_tool_routing: bool = True,
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

        selected_tools = ["local_notes", "public_api"]
        if self._use_llm and self._llm_tool_routing:
            routed = await choose_research_tools_with_llm(
                goal=query,
                api_key=self._llm_api_key,
                model=self._llm_model,
                endpoint=self._llm_endpoint,
                timeout=self._llm_timeout,
            )
            if routed:
                selected_tools = routed

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
