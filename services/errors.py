"""Typed application exceptions for clearer failure handling and recovery guidance."""

from __future__ import annotations


class AppError(Exception):
    """Base application error."""


class ConfigValidationError(AppError):
    """Raised when required configuration is invalid."""


class GuardrailViolationError(AppError):
    """Raised when policy guardrails reject content."""


class ExternalServiceError(AppError):
    """Raised when an external dependency fails."""


class EvidenceValidationError(AppError):
    """Raised when evidence and claims cannot be verified."""


class ApprovalRequiredError(AppError):
    """Raised when human approval is required but missing."""


class SecretHygieneError(AppError):
    """Raised when secret-hygiene checks fail in strict mode."""
