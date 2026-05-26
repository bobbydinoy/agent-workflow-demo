"""Application configuration and logging setup."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    log_level: str
    data_dir: Path
    notes_file: str
    search_api_endpoint: str
    search_api_timeout: int
    use_llm: bool
    llm_api_key: str
    llm_model: str
    llm_endpoint: str
    llm_timeout: int
    llm_web_search: bool
    llm_search_context_size: str
    max_retries: int
    retry_min_wait: int
    retry_max_wait: int
    enable_compliance_check: bool
    enable_human_approval: bool
    approval_mode: str
    approval_token: str
    enable_secret_hygiene: bool
    strict_secret_hygiene: bool
    llm_tool_routing: bool

    @property
    def project_root(self) -> Path:
        """Return the project root inferred from the current working directory."""
        return Path(".").resolve()

    @property
    def notes_path(self) -> Path:
        """Return the absolute path to the notes file inside the data directory."""
        return self.data_dir / self.notes_file


def load_config() -> AppConfig:
    """Load app configuration from .env and process environment variables."""
    load_dotenv()

    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()

    use_llm = os.getenv("USE_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}
    llm_web_search = os.getenv("LLM_WEB_SEARCH", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enable_compliance_check = os.getenv("ENABLE_COMPLIANCE_CHECK", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enable_human_approval = os.getenv("ENABLE_HUMAN_APPROVAL", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enable_secret_hygiene = os.getenv("ENABLE_SECRET_HYGIENE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    strict_secret_hygiene = os.getenv("STRICT_SECRET_HYGIENE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    llm_tool_routing = os.getenv("LLM_TOOL_ROUTING", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return AppConfig(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_dir=data_dir,
        notes_file=os.getenv("NOTES_FILE", "company_notes.txt"),
        search_api_endpoint=os.getenv(
            "SEARCH_API_ENDPOINT", "https://api.duckduckgo.com/"
        ),
        search_api_timeout=int(os.getenv("SEARCH_API_TIMEOUT", "8")),
        use_llm=use_llm,
        llm_api_key=os.getenv("OPENAI_API_KEY", ""),
        llm_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        llm_endpoint=os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1/chat/completions"),
        llm_timeout=int(os.getenv("OPENAI_TIMEOUT", "20")),
        llm_web_search=llm_web_search,
        llm_search_context_size=os.getenv("LLM_SEARCH_CONTEXT_SIZE", "high"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_min_wait=int(os.getenv("RETRY_MIN_WAIT", "1")),
        retry_max_wait=int(os.getenv("RETRY_MAX_WAIT", "8")),
        enable_compliance_check=enable_compliance_check,
        enable_human_approval=enable_human_approval,
        approval_mode=os.getenv("APPROVAL_MODE", "auto").strip().lower(),
        approval_token=os.getenv("APPROVAL_TOKEN", "").strip(),
        enable_secret_hygiene=enable_secret_hygiene,
        strict_secret_hygiene=strict_secret_hygiene,
        llm_tool_routing=llm_tool_routing,
    )


def configure_logging(level: str) -> None:
    """Configure root logging for the full application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
