"""Guardrail and safety tools for prompt/content validation."""

from __future__ import annotations

import logging
import re

from services.errors import GuardrailViolationError

logger = logging.getLogger(__name__)

POLICY_RULES: dict[str, list[str]] = {
    "unsafe_actions": [
        "delete database",
        "drop table",
        "shutdown server",
        "disable security",
    ],
    "secrets_and_exfiltration": [
        "api key",
        "private key",
        "password dump",
        "exfiltrate",
    ],
    "prompt_injection": [
        "ignore previous instructions",
        "reveal system prompt",
        "bypass safety",
    ],
}


def evaluate_policy_violations(text: str) -> list[dict[str, str]]:
    """Return all matched policy violations grouped by category."""
    normalized = text.lower()
    violations: list[dict[str, str]] = []
    for category, patterns in POLICY_RULES.items():
        for pattern in patterns:
            if re.search(re.escape(pattern), normalized):
                violations.append({"category": category, "pattern": pattern})
    return violations


def validate_prompt(prompt: str) -> None:
    """Validate prompt/content against policy rules and fail closed on violations."""
    violations = evaluate_policy_violations(prompt)
    if violations:
        first = violations[0]
        logger.error(
            "Policy violation detected category=%s pattern=%s",
            first["category"],
            first["pattern"],
        )
        raise GuardrailViolationError(
            f"Unsafe content detected ({first['category']}): {first['pattern']}"
        )

    logger.info("Prompt validation passed")
