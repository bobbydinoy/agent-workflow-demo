"""Lightweight observability helpers for demo telemetry reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass
class StageTelemetry:
    """Telemetry emitted by each workflow stage."""

    stage: str
    duration_ms: float
    tool_calls: int = 0


@dataclass
class RunTelemetry:
    """End-to-end telemetry for a workflow run."""

    goal: str
    started_at: float = field(default_factory=perf_counter)
    stage_data: list[StageTelemetry] = field(default_factory=list)
    retry_metrics: dict[str, int] = field(default_factory=dict)
    secret_hygiene: dict[str, Any] = field(default_factory=dict)

    def add_stage(self, stage: str, payload: dict[str, Any] | None) -> None:
        """Record per-stage telemetry from payload metadata."""
        telemetry_block = payload.get("_telemetry", {}) if isinstance(payload, dict) else {}
        duration_ms = float(telemetry_block.get("duration_ms", 0.0))
        tool_calls = int(telemetry_block.get("tool_calls", 0))
        self.stage_data.append(
            StageTelemetry(
                stage=stage,
                duration_ms=round(duration_ms, 2),
                tool_calls=tool_calls,
            )
        )

    def finalize(self) -> dict[str, Any]:
        """Return a JSON-serializable telemetry report."""
        total_ms = (perf_counter() - self.started_at) * 1000
        return {
            "total_duration_ms": round(total_ms, 2),
            "stage_durations_ms": {
                item.stage: item.duration_ms for item in self.stage_data
            },
            "tool_calls": {item.stage: item.tool_calls for item in self.stage_data},
            "retry_attempts": self.retry_metrics,
            "secret_hygiene": self.secret_hygiene,
        }
