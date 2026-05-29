from __future__ import annotations

import json
from dataclasses import dataclass

from .models import Paths


@dataclass(frozen=True)
class DoctorResult:
    errors: list[str]
    requested: bool
    checks_completed: bool
    exit_code: int
    error_count: int
    computed_error_count: int


def _manifest_valid(paths: Paths) -> bool:
    if not paths.manifest_path.exists():
        return False
    try:
        payload = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict)


def _secret_leak_likely(paths: Paths) -> bool:
    candidates = [paths.settings_path, paths.manifest_path]
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    for path in candidates:
        if path.exists() and any(marker in path.read_text(encoding="utf-8") for marker in markers):
            return True
    return False


def run_doctor(paths: Paths) -> DoctorResult:
    errors: list[str] = []

    if not paths.settings_path.exists():
        errors.append("missing_settings_shim")
    if not paths.agent_root.exists():
        errors.append("missing_agent_root")
    if not _manifest_valid(paths):
        errors.append("invalid_manifest")
    if _secret_leak_likely(paths):
        errors.append("secret_leak_likely")

    computed_error_count = len(errors)
    exit_code = 1 if computed_error_count > 0 else 0
    return DoctorResult(
        errors=errors,
        requested=True,
        checks_completed=True,
        exit_code=exit_code,
        error_count=computed_error_count,
        computed_error_count=computed_error_count,
    )
