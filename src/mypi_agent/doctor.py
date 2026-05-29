from __future__ import annotations

import json

from .base_model import AlliumBase
from .models import Paths


class DoctorResult(AlliumBase):
    errors: list[str]
    requested: bool
    checks_completed: bool
    exit_code: int
    error_count: int
    computed_error_count: int
    diagnostics: list[dict[str, str]]


def _manifest_valid(paths: Paths) -> bool:
    if not paths.manifest_path.exists():
        return False
    try:
        payload = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    required = ("schema_version", "resources", "pi_package", "pi_version", "node_version", "generated_by")
    if any(key not in payload for key in required):
        return False
    if payload.get("schema_version") != 1:
        return False
    if payload.get("generated_by") != "mypi-agent":
        return False
    resources = payload.get("resources")
    if not isinstance(resources, list):
        return False
    allowed_resources = {"extensions", "skills", "prompts", "themes"}
    return all(isinstance(item, str) and item in allowed_resources for item in resources)


def _secret_leak_likely(paths: Paths) -> bool:
    candidates = [paths.settings_path, paths.manifest_path]
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    for path in candidates:
        if path.exists() and any(marker in path.read_text(encoding="utf-8") for marker in markers):
            return True
    return False


def run_doctor(paths: Paths) -> DoctorResult:
    errors: list[str] = []
    diagnostics: list[dict[str, str]] = []

    if not paths.settings_path.exists():
        errors.append("missing_settings_shim")
        diagnostics.append({"code": "missing_settings_shim", "severity": "error"})
    if not paths.agent_root.exists():
        errors.append("missing_agent_root")
        diagnostics.append({"code": "missing_agent_root", "severity": "error"})
    if not _manifest_valid(paths):
        errors.append("invalid_manifest")
        diagnostics.append({"code": "invalid_manifest", "severity": "error"})
    if _secret_leak_likely(paths):
        errors.append("secret_leak_likely")
        diagnostics.append({"code": "secret_leak_likely", "severity": "error"})

    computed_error_count = len(errors)
    exit_code = 1 if computed_error_count > 0 else 0
    return DoctorResult(
        errors=errors,
        requested=True,
        checks_completed=True,
        exit_code=exit_code,
        error_count=computed_error_count,
        computed_error_count=computed_error_count,
        diagnostics=diagnostics,
    )
