"""Review agent for output verification and safety checks."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

from agent_framework import Executor, Message, WorkflowContext, handler
from agent_framework_openai import OpenAIChatCompletionClient

from services.errors import EvidenceValidationError
from tools.safe_tools import validate_prompt

logger = logging.getLogger(__name__)


async def _generate_review_notes_with_llm(
    analysis_data: dict[str, Any],
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int,
) -> list[str] | None:
    """Generate contextual review notes using LLM based on analysis findings."""
    if not api_key.strip():
        logger.debug("LLM review generation skipped: missing API key")
        return None

    try:
        summary = str(analysis_data.get("summary", "")).strip()
        guide = analysis_data.get("guide", {})
        metrics = analysis_data.get("metrics", {})
        selected_tools = analysis_data.get("selected_tools", [])

        prompt = (
            f"Analyze this research analysis and generate 3-4 concise review notes (bullet points only).\n"
            f"Focus on: evidence quality, source traceability, gaps, and next steps.\n\n"
            f"Summary: {summary}\n"
            f"Tools used: {', '.join(selected_tools)}\n"
            f"Metrics: {json.dumps(metrics)}\n"
            f"Evidence count: {len(guide.get('evidence', []))}\n\n"
            f"Generate review notes as a JSON array of strings.\n"
            f"Example format: {{'notes': ['Note 1', 'Note 2', 'Note 3']}}"
        )

        messages = [
            Message(role="system", contents=[
                "You are a technical reviewer. Generate concise, actionable review notes."
            ]),
            Message(role="user", contents=[prompt]),
        ]

        client = OpenAIChatCompletionClient(
            model=model,
            api_key=api_key,
            base_url=endpoint.rsplit("/chat/completions", 1)[0] if "/chat/completions" in endpoint else endpoint,
        )

        response = await client.get_response(
            messages,
            options={
                "temperature": 0.3,
                "max_tokens": 300,
                "response_format": {"type": "json_object"},
            },
            client_kwargs={"timeout": timeout},
        )

        content = response.text.strip()
        parsed = json.loads(content)
        
        if isinstance(parsed, dict) and "notes" in parsed:
            notes = parsed.get("notes", [])
            if isinstance(notes, list) and all(isinstance(n, str) for n in notes):
                logger.info("Generated %d contextual review notes", len(notes))
                return notes

        return None
    except Exception as exc:
        logger.warning("LLM review note generation failed, using defaults: %s", exc)
        return None


class ReviewAgent(Executor):
    """Inspect analysis output and ensure safe, source-backed final output."""

    def __init__(
        self,
        *,
        use_llm: bool = False,
        llm_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
        llm_endpoint: str = "https://api.openai.com/v1/chat/completions",
        llm_timeout: int = 20,
    ) -> None:
        super().__init__(id="review")
        self._use_llm = use_llm
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_endpoint = llm_endpoint
        self._llm_timeout = llm_timeout

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

        # Generate review notes: LLM-based or default
        review_notes = None
        if self._use_llm:
            review_notes = await _generate_review_notes_with_llm(
                analysis_data=analysis_data,
                api_key=self._llm_api_key,
                model=self._llm_model,
                endpoint=self._llm_endpoint,
                timeout=self._llm_timeout,
            )

        # Fall back to default review notes if LLM generation failed or disabled
        if not review_notes:
            review_notes = [
                "Safety scan passed for blocked instruction patterns.",
                "Output includes explicit references to local and API sources.",
                f"Evidence extracted from {len(guide.get('evidence', []))} sources.",
                "Prepared for future compliance and human approval gates.",
            ]
            logger.info("Using default review notes")
        else:
            logger.info("Using LLM-generated review notes")

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
                "tool_calls": 1 if self._use_llm and review_notes else 0,
            },
        }

        logger.info("ReviewAgent finished with %d review notes", len(review_notes))
        await ctx.yield_output(reviewed)
        await ctx.send_message(reviewed)
