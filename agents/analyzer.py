"""Analysis agent for deriving metrics and concise summary from research output."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from agent_framework import Executor, WorkflowContext, handler
from tools.llm_tools import generate_beginner_guide_with_llm

logger = logging.getLogger(__name__)


class AnalysisAgent(Executor):
    """Analyze structured research output and produce summary metrics."""

    def __init__(
        self,
        *,
        use_llm: bool = False,
        llm_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
        llm_endpoint: str = "https://api.openai.com/v1/chat/completions",
        llm_timeout: int = 20,
        llm_web_search: bool = True,
        llm_search_context_size: str = "high",
    ) -> None:
        super().__init__(id="analyze")
        self._use_llm = use_llm
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_endpoint = llm_endpoint
        self._llm_timeout = llm_timeout
        self._llm_web_search = llm_web_search
        self._llm_search_context_size = llm_search_context_size

    @handler
    async def run(
        self,
        research_data: dict[str, Any],
        ctx: WorkflowContext[dict[str, Any], dict[str, Any]],
    ) -> None:
        """Compute metrics and build a practical guide grounded in source evidence."""
        started = perf_counter()
        logger.info("AnalysisAgent started")

        goal = str(research_data.get("goal", "")).strip()
        notes = research_data.get("notes", {})
        api = research_data.get("api", {})

        note_content = str(notes.get("content", ""))
        note_length = len(note_content)
        api_result_count = int(api.get("result_count", 0))
        api_heading = str(api.get("heading", "")).strip()
        api_abstract = str(api.get("abstract", "")).strip()

        raw_topics = api.get("related_topics", [])
        api_topics = [str(item) for item in raw_topics if isinstance(item, str) and item.strip()]
        top_topics = api_topics[:5]

        evidence_points: list[str] = []
        if api_abstract:
            evidence_points.append(api_abstract)
        evidence_points.extend(top_topics)

        deduped_evidence: list[str] = []
        for point in evidence_points:
            if point not in deduped_evidence:
                deduped_evidence.append(point)
        evidence_points = deduped_evidence

        if not evidence_points:
            evidence_points.append(
                "No specific public facts were returned by the API for this query."
            )

        references = [str(ref) for ref in research_data.get("references", []) if str(ref).strip()]
        citation_map: list[dict[str, str]] = []
        for index, evidence in enumerate(evidence_points):
            source = references[index % len(references)] if references else ""
            citation_map.append({"claim": evidence, "source": source})

        guide_title_target = api_heading or goal or "Research Topic"
        starter_plan = [
            "Start with a 20-minute fundamentals review using the primary reference link.",
            "Pick one concept from the evidence list and practice only that concept first.",
            "After each practice session, write one takeaway and one question to research next.",
            "Expand to the next evidence topic only after you can explain the previous one clearly.",
        ]

        if api_result_count == 0:
            starter_plan[0] = (
                "Refine the goal with clearer keywords (for example: 'python basics syntax and exercises')."
            )

        guide = {
            "title": f"Beginner Guide: {guide_title_target}",
            "goal": goal,
            "target_audience": "Beginners",
            "evidence": evidence_points,
            "starter_plan": starter_plan,
            "limitations": (
                "Guide only uses local notes and public API evidence; it does not invent facts."
            ),
        }

        if self._use_llm:
            llm_guide = await generate_beginner_guide_with_llm(
                goal=goal,
                evidence_points=evidence_points,
                references=[str(ref) for ref in research_data.get("references", [])],
                api_key=self._llm_api_key,
                model=self._llm_model,
                endpoint=self._llm_endpoint,
                timeout=self._llm_timeout,
                enable_web_search=self._llm_web_search,
                search_context_size=self._llm_search_context_size,
            )
            if llm_guide is not None:
                guide = {
                    "title": llm_guide["title"],
                    "goal": goal,
                    "target_audience": llm_guide["target_audience"],
                    "evidence": llm_guide["evidence"],
                    "starter_plan": llm_guide["starter_plan"],
                    "limitations": llm_guide["limitations"],
                }

        summary = (
            f"Generated a beginner guide for '{guide_title_target}' using source-backed evidence. "
            f"Local note length: {note_length} characters. "
            f"API related result count: {api_result_count}. "
            "Evidence and starter plan are included in the guide payload."
        )

        analyzed = {
            "metrics": {
                "note_length": note_length,
                "api_result_count": api_result_count,
            },
            "summary": summary,
            "guide": guide,
            "references": references,
            "citations": citation_map,
            "selected_tools": research_data.get("selected_tools", []),
            "_telemetry": {
                "duration_ms": (perf_counter() - started) * 1000,
                "tool_calls": 1 if self._use_llm else 0,
            },
        }

        logger.info("AnalysisAgent finished")

        await ctx.yield_output({"stage": "analyze", "payload": analyzed})
        await ctx.send_message(analyzed)
