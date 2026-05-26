"""File access tools with strict path safety checks."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _ensure_safe_data_path(filepath: str, data_dir: Path | None = None) -> Path:
    """Resolve and validate that filepath is strictly inside the data directory."""
    root_data_dir = (data_dir or Path("./data")).resolve()
    candidate_path = Path(filepath).resolve()

    try:
        candidate_path.relative_to(root_data_dir)
    except ValueError as exc:
        logger.error("Blocked unsafe file access attempt: %s", filepath)
        raise PermissionError(f"Unsafe path access blocked: {filepath}") from exc

    return candidate_path


def read_file(filepath: str) -> str:
    """Read a UTF-8 text file only if it is inside ./data."""
    logger.info("Reading file from path: %s", filepath)
    safe_path = _ensure_safe_data_path(filepath)

    if not safe_path.exists() or not safe_path.is_file():
        raise FileNotFoundError(f"File not found: {safe_path}")

    content = safe_path.read_text(encoding="utf-8")
    logger.info("Read %d characters from %s", len(content), safe_path)
    return content
