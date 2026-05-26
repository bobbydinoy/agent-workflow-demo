"""Main orchestrator for the multi-agent demo workflow.

Architecture overview:
- Planner creates an ordered, extensible task list.
- Agents execute in a chain using a shared context object.
- Tools handle data access, API calls, and safety checks.
- Retry service centralizes retries and failure handling.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from agent_framework import Executor
from agent_framework_orchestrations import SequentialBuilder

from agents.approval import HumanApprovalAgent
from agents.analyzer import AnalysisAgent
from agents.compliance import ComplianceAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewAgent
from config import configure_logging, load_config
from services.errors import ConfigValidationError
from services.observability import RunTelemetry
from services.retry_service import OperationExecutionError, RetryService
from tools.safe_tools import validate_prompt
from tools.secret_hygiene import run_secret_hygiene_checks

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    """Shared context for all workflow steps to avoid global state."""

    goal: str
    plan: list[str] = field(default_factory=list)
    research_output: dict[str, Any] | None = None
    analysis_output: dict[str, Any] | None = None
    reviewed_output: dict[str, Any] | None = None
    observability_report: dict[str, Any] | None = None


def execute_workflow(user_goal: str) -> WorkflowContext:
    """Run the full planning and execution chain for a user goal."""
    config = load_config()
    configure_logging(config.log_level)

    logger.info("Starting workflow for user goal")
    validate_prompt(user_goal)

    if config.approval_mode not in {"auto", "token"}:
        raise ConfigValidationError("APPROVAL_MODE must be 'auto' or 'token'")

    context = WorkflowContext(goal=user_goal)
    telemetry = RunTelemetry(goal=user_goal)

    if config.enable_secret_hygiene:
        telemetry.secret_hygiene = run_secret_hygiene_checks(
            project_root=config.project_root,
            strict=config.strict_secret_hygiene,
        )

    planner = PlannerAgent()
    researcher = ResearchAgent(
        notes_path=config.notes_path,
        api_endpoint=config.search_api_endpoint,
        api_timeout=config.search_api_timeout,
        use_llm=config.use_llm,
        llm_api_key=config.llm_api_key,
        llm_model=config.llm_model,
        llm_endpoint=config.llm_endpoint,
        llm_timeout=config.llm_timeout,
        llm_tool_routing=config.llm_tool_routing,
    )
    analyzer = AnalysisAgent(
        use_llm=config.use_llm,
        llm_api_key=config.llm_api_key,
        llm_model=config.llm_model,
        llm_endpoint=config.llm_endpoint,
        llm_timeout=config.llm_timeout,
        llm_web_search=config.llm_web_search,
        llm_search_context_size=config.llm_search_context_size,
    )
    reviewer = ReviewAgent()
    compliance = ComplianceAgent()
    approval = HumanApprovalAgent(mode=config.approval_mode, token=config.approval_token)

    retry_service = RetryService(
        max_retries=config.max_retries,
        min_wait=config.retry_min_wait,
        max_wait=config.retry_max_wait,
    )

    context.plan = planner.create_plan(user_goal)
    if config.enable_compliance_check and "compliance_check" not in context.plan:
        context.plan.append("compliance_check")
    if config.enable_human_approval and "human_approval" not in context.plan:
        context.plan.append("human_approval")
    logger.info("Execution plan created: %s", context.plan)

    step_to_participant: dict[str, Executor] = {
        "research": researcher,
        "analyze": analyzer,
        "review": reviewer,
        "compliance_check": compliance,
        "human_approval": approval,
    }
    participants: list[Executor] = []
    for step in context.plan:
        participant = step_to_participant.get(step)
        if participant is None:
            logger.warning("Unknown step '%s' skipped", step)
            continue
        participants.append(participant)

    if not participants:
        raise ValueError("No executable workflow steps found in plan")

    workflow = SequentialBuilder(
        participants=participants,
        output_from=[participants[-1]],
        intermediate_output_from="all_other",
    ).build()

    async def _run_sdk_workflow() -> WorkflowContext:
        logger.info("Executing SDK workflow chain via Microsoft Agent Framework")
        run_result = await retry_service.execute_async(
            operation=lambda: workflow.run(context.goal),
            operation_name="sdk_sequential_workflow",
        )

        for item in run_result.get_intermediate_outputs():
            if not isinstance(item, dict):
                continue
            stage_name = str(item.get("stage", "")).lower()
            payload = item.get("payload")
            if stage_name == "research" and isinstance(payload, dict):
                context.research_output = payload
            if stage_name == "analyze" and isinstance(payload, dict):
                context.analysis_output = payload
            if stage_name in {"research", "analyze", "review", "compliance_check", "human_approval"}:
                telemetry.add_stage(stage_name, payload if isinstance(payload, dict) else None)
                continue

            if "review_notes" in item:
                telemetry.add_stage("review", item)

        outputs = run_result.get_outputs()
        if not outputs:
            raise ValueError("Workflow did not produce final output")

        final_output = outputs[-1]
        if not isinstance(final_output, dict):
            raise ValueError("Final workflow output must be a dictionary")

        if "stage" in final_output and "payload" in final_output:
            final_stage = str(final_output.get("stage", "")).lower()
            payload = final_output.get("payload")
            if isinstance(payload, dict):
                final_output = payload
                if final_stage:
                    telemetry.add_stage(final_stage, payload)

        telemetry.retry_metrics = retry_service.get_attempt_metrics()
        context.observability_report = telemetry.finalize()
        final_output["observability"] = context.observability_report
        context.reviewed_output = final_output
        return context

    context = asyncio.run(_run_sdk_workflow())

    logger.info("Workflow execution finished")
    return context


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the demo app."""
    parser = argparse.ArgumentParser(description="Multi-agent framework demo")
    parser.add_argument(
        "--goal",
        type=str,
        default="Research AI agents for internal productivity tools",
        help="User goal that drives planning and execution",
    )
    return parser.parse_args()


def main() -> None:
    """Application entrypoint."""
    args = parse_args()

    try:
        result_context = execute_workflow(args.goal)
    except OperationExecutionError as exc:
        logger.exception("Workflow failed after retries: %s", exc)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workflow failed: %s", exc)
        raise

    print("\n=== FINAL REVIEWED OUTPUT ===")
    print(json.dumps(result_context.reviewed_output, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
