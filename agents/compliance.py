"""Compliance gate agent for minimal policy checks before final approval."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from services.errors import GuardrailViolationError

logger = logging.getLogger(__name__)


class ComplianceAgent(Executor):
    """Run lightweight compliance checks on analyzed content."""

    def __init__(self) -> None:
        super().__init__(id="compliance_check")

    @handler
    async def run(
        self,
        analysis_data: dict[str, Any],
        ctx: WorkflowContext[dict[str, Any], dict[str, Any]],
    ) -> None:
        started = perf_counter()
        logger.info("ComplianceAgent started")

        references = analysis_data.get("references", [])
        guide = analysis_data.get("guide", {})

        if not isinstance(references, list) or not references:
            raise GuardrailViolationError("Compliance failed: references are required")

        evidence = guide.get("evidence", []) if isinstance(guide, dict) else []
        if not isinstance(evidence, list) or not evidence:
            raise GuardrailViolationError("Compliance failed: evidence list is required")

        compliance = {
            "status": "passed",
            "checks": [
                "references_present",
                "evidence_present",
                "structure_valid",
            ],
            "notes": [
                "Minimal compliance gate passed.",
                "Use policy tiers for production-grade compliance.",
            ],
        }

        result = dict(analysis_data)
        result["compliance"] = compliance
        result["_telemetry"] = {
            "duration_ms": (perf_counter() - started) * 1000,
            "tool_calls": 0,
        }

        logger.info("ComplianceAgent finished")
        await ctx.yield_output({"stage": "compliance_check", "payload": result})
        await ctx.send_message(result)
