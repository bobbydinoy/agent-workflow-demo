"""Retry and failure handling service built on tenacity."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import AsyncRetrying, RetryCallState, Retrying, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
T = TypeVar("T")


class OperationExecutionError(Exception):
    """Raised when an operation fails after all retry attempts."""


class RetryService:
    """Execute operations with retries, backoff, and centralized logging."""

    def __init__(self, max_retries: int = 3, min_wait: int = 1, max_wait: int = 8) -> None:
        self._max_retries = max_retries
        self._min_wait = min_wait
        self._max_wait = max_wait
        self._attempt_counters: dict[str, int] = {}

    def get_attempt_metrics(self) -> dict[str, int]:
        """Return operation->attempt_count metrics for completed executions."""
        return dict(self._attempt_counters)

    @staticmethod
    def _log_retry(retry_state: RetryCallState) -> None:
        """Log retry attempt details before the next retry sleep."""
        logger.warning(
            "Retry attempt %s after error: %s",
            retry_state.attempt_number,
            retry_state.outcome.exception() if retry_state.outcome else "unknown",
        )

    def execute(self, operation: Callable[[], T], operation_name: str = "operation") -> T:
        """Execute an operation with exponential backoff and capped retries."""
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._min_wait,
                    max=self._max_wait,
                ),
                reraise=True,
                before_sleep=self._log_retry,
            ):
                with attempt:
                    self._attempt_counters[operation_name] = attempt.retry_state.attempt_number
                    logger.info("Executing operation: %s", operation_name)
                    return operation()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Operation failed after max retries: %s", operation_name)
            raise OperationExecutionError(
                f"Operation '{operation_name}' failed after {self._max_retries} retries"
            ) from exc

        raise OperationExecutionError(
            f"Operation '{operation_name}' exited without producing a result"
        )

    async def execute_async(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "operation",
    ) -> T:
        """Execute an async operation with exponential backoff and capped retries."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._min_wait,
                    max=self._max_wait,
                ),
                reraise=True,
                before_sleep=self._log_retry,
            ):
                with attempt:
                    self._attempt_counters[operation_name] = attempt.retry_state.attempt_number
                    logger.info("Executing operation: %s", operation_name)
                    return await operation()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Operation failed after max retries: %s", operation_name)
            raise OperationExecutionError(
                f"Operation '{operation_name}' failed after {self._max_retries} retries"
            ) from exc

        raise OperationExecutionError(
            f"Operation '{operation_name}' exited without producing a result"
        )
