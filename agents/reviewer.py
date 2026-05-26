"""Review agent for output verification and safety checks."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from services.errors import EvidenceValidationError
from tools.safe_tools import validate_prompt

logger = logging.getLogger(__name__)


class ReviewAgent(Executor):
    """Inspect analysis output and ensure safe, source-backed final output."""

    def __init__(self) -> None:
        super().__init__(id="review")

    @handler
    async def run(
        self,
        analysis_data: dict[str, Any],
        ctx: WorkflowContext[dict[str, Any], dict[str, Any]],
    ) -> None:
        """Review analysis content and emit the approved final payload."""
        started = perf_counter()
        logger.info("ReviewAgent started")

        summary = str(analysis_data.get("summary", ""))
        guide = analysis_data.get("guide", {})
        references = analysis_data.get("references", [])
        citations = analysis_data.get("citations", [])

        if not references:
            raise EvidenceValidationError("Review failed: missing references for source-backed output")

        if not isinstance(citations, list) or not citations:
            raise EvidenceValidationError("Review failed: missing citation map")

        for item in citations:
            if not isinstance(item, dict):
                raise EvidenceValidationError("Review failed: citation entry has invalid format")
            claim = str(item.get("claim", "")).strip()
            source = str(item.get("source", "")).strip()
            if not claim or not source:
                raise EvidenceValidationError(
                    "Review failed: each citation must include claim and source"
                )

        validate_prompt(summary)
        validate_prompt(json.dumps(guide, ensure_ascii=True))

        review_notes = [
            "Safety scan passed for blocked instruction patterns.",
            "Output includes explicit references to local and API sources.",
            "Prepared for future compliance and human approval gates.",
        ]

        reviewed = {
            "status": "approved",
            "final_summary": summary,
            "guide": guide,
            "metrics": analysis_data.get("metrics", {}),
            "references": references,
            "citations": citations,
            "selected_tools": analysis_data.get("selected_tools", []),
            "review_notes": review_notes,
            "future_controls": ["compliance_check", "human_approval"],
            "_telemetry": {
                "duration_ms": (perf_counter() - started) * 1000,
                "tool_calls": 0,
            },
        }

        logger.info("ReviewAgent finished")
        await ctx.yield_output(reviewed)
        await ctx.send_message(reviewed)
