"""Human approval gate agent for demo workflows."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from services.errors import ApprovalRequiredError

logger = logging.getLogger(__name__)


class HumanApprovalAgent(Executor):
    """Require explicit approval token or auto-approve for demo mode."""

    def __init__(self, *, mode: str = "auto", token: str = "") -> None:
        super().__init__(id="human_approval")
        self._mode = mode
        self._token = token

    @handler
    async def run(
        self,
        input_data: dict[str, Any],
        ctx: WorkflowContext[dict[str, Any], dict[str, Any]],
    ) -> None:
        started = perf_counter()
        logger.info("HumanApprovalAgent started in mode=%s", self._mode)

        if self._mode not in {"auto", "token"}:
            raise ApprovalRequiredError("Unsupported APPROVAL_MODE. Use 'auto' or 'token'.")

        if self._mode == "token" and not self._token.strip():
            raise ApprovalRequiredError(
                "Human approval required: set APPROVAL_TOKEN or switch APPROVAL_MODE=auto"
            )

        result = dict(input_data)
        result["approval"] = {
            "mode": self._mode,
            "approved": True,
            "reason": "Auto-approved for demo" if self._mode == "auto" else "Approved by token",
        }
        result["_telemetry"] = {
            "duration_ms": (perf_counter() - started) * 1000,
            "tool_calls": 0,
        }

        logger.info("HumanApprovalAgent finished")
        await ctx.yield_output({"stage": "human_approval", "payload": result})
        await ctx.send_message(result)
