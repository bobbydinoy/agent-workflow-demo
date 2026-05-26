"""Secret hygiene checks used during startup for safer demos."""

from __future__ import annotations

from pathlib import Path

from services.errors import SecretHygieneError


def run_secret_hygiene_checks(*, project_root: Path, strict: bool = False) -> dict[str, object]:
    """Scan local project config files for likely hardcoded secrets."""
    findings: list[str] = []
    scanned_files: list[str] = []

    for relative in (".env", ".env.example"):
        candidate = project_root / relative
        if not candidate.exists() or not candidate.is_file():
            continue

        scanned_files.append(relative)
        content = candidate.read_text(encoding="utf-8")
        for line in content.splitlines():
            normalized = line.strip()
            if not normalized or normalized.startswith("#"):
                continue
            if "OPENAI_API_KEY=" in normalized:
                value = normalized.split("=", 1)[1].strip()
                if value and value.lower() not in {"your_api_key_here", "changeme"}:
                    findings.append(f"Potential API key in {relative}")

    has_gitignore = (project_root / ".gitignore").exists()
    if not has_gitignore:
        findings.append(".gitignore is missing; ensure .env is ignored before committing")

    report: dict[str, object] = {
        "enabled": True,
        "strict": strict,
        "scanned_files": scanned_files,
        "findings": findings,
        "status": "passed" if not findings else "warning",
    }

    if strict and findings:
        raise SecretHygieneError("Secret hygiene check failed in strict mode")

    return report
