from __future__ import annotations

import json
import os
import shutil
import subprocess
from pydantic import ValidationError

from .base_model import AlliumBase
from .models import Manifest, Paths


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
    try:
        Manifest.model_validate(payload)
    except ValidationError:
        return False
    return True


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
    if shutil.which("node") is None:
        errors.append("missing_node")
        diagnostics.append({"code": "missing_node", "severity": "error"})
    if shutil.which("npm") is None:
        errors.append("missing_npm")
        diagnostics.append({"code": "missing_npm", "severity": "error"})
    if not paths.pi_executable_path.exists():
        errors.append("missing_pi_agent_executable")
        diagnostics.append({"code": "missing_pi_agent_executable", "severity": "error"})
    elif not os.access(paths.pi_executable_path, os.X_OK):
        errors.append("pi_agent_executable_not_executable")
        diagnostics.append({"code": "pi_agent_executable_not_executable", "severity": "error"})
    else:
        version_check = subprocess.run(
            [str(paths.pi_executable_path), "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if version_check.returncode != 0:
            errors.append("pi_agent_version_check_failed")
            diagnostics.append({"code": "pi_agent_version_check_failed", "severity": "error"})

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
