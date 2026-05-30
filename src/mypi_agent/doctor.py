from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from pydantic import ValidationError

from .base_model import MypiBaseModel
from .models import Manifest, Paths


class DoctorResult(MypiBaseModel):
    errors: list[str]
    warnings: list[str]
    requested: bool
    checks_completed: bool
    exit_code: int
    error_count: int
    warning_count: int
    computed_error_count: int
    diagnostics: list[dict[str, str]]


def _manifest_status(paths: Paths) -> str:
    if not paths.manifest_path.exists():
        return "invalid_manifest"
    try:
        payload = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_manifest"
    try:
        Manifest.model_validate(payload)
    except ValidationError:
        return "manifest_schema_invalid"
    return "ok"


def _secret_leak_likely(paths: Paths) -> bool:
    candidates = [paths.settings_path, paths.manifest_path]
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    for path in candidates:
        if path.exists() and any(marker in path.read_text(encoding="utf-8") for marker in markers):
            return True
    return False


def _settings_payload(paths: Paths) -> dict[str, object] | None:
    if not paths.settings_path.exists():
        return None
    try:
        payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def run_doctor(paths: Paths) -> DoctorResult:
    errors: list[str] = []
    warnings: list[str] = []
    diagnostics: list[dict[str, str]] = []

    if not paths.settings_path.exists():
        errors.append("missing_settings_shim")
        diagnostics.append({"code": "missing_settings_shim", "severity": "error"})
    if not paths.agent_root.exists():
        errors.append("missing_agent_root")
        diagnostics.append({"code": "missing_agent_root", "severity": "error"})
    manifest_status = _manifest_status(paths)
    if manifest_status == "invalid_manifest":
        errors.append("invalid_manifest")
        diagnostics.append({"code": "invalid_manifest", "severity": "error"})
    elif manifest_status == "manifest_schema_invalid":
        errors.append("manifest_schema_invalid")
        diagnostics.append({"code": "manifest_schema_invalid", "severity": "error"})
    if _secret_leak_likely(paths):
        errors.append("secret_leak_likely")
        diagnostics.append({"code": "secret_leak_likely", "severity": "error"})
    expected_prefix = paths.project_root / os.environ.get("MYPI_AGENT_ROOT", ".agents/pi") / "npm-global"
    npm_prefix = os.environ.get("NPM_CONFIG_PREFIX", "")
    if not npm_prefix:
        errors.append("npm_scope_not_project_local")
        diagnostics.append({"code": "npm_scope_not_project_local", "severity": "error"})
    else:
        try:
            npm_prefix_path = Path(npm_prefix).resolve()
            expected_prefix_path = expected_prefix.resolve()
            if expected_prefix_path not in npm_prefix_path.parents and npm_prefix_path != expected_prefix_path:
                errors.append("npm_scope_not_project_local")
                diagnostics.append({"code": "npm_scope_not_project_local", "severity": "error"})
        except OSError:
            errors.append("npm_scope_not_project_local")
            diagnostics.append({"code": "npm_scope_not_project_local", "severity": "error"})

    settings_payload = _settings_payload(paths)
    if settings_payload is not None:
        marker = settings_payload.get("x-mypi-agent")
        expected_root = f"../{os.environ.get('MYPI_AGENT_ROOT', '.agents/pi')}"
        if not isinstance(marker, dict) or marker.get("agentRoot") != expected_root:
            errors.append("settings_shim_not_pointing_to_configured_root")
            diagnostics.append({"code": "settings_shim_not_pointing_to_configured_root", "severity": "error"})
        if "npmCommand" not in settings_payload:
            warnings.append("missing_npm_command")
            diagnostics.append({"code": "missing_npm_command", "severity": "warning"})
    if shutil.which("node") is None:
        errors.append("missing_node")
        diagnostics.append({"code": "missing_node", "severity": "error"})
    if shutil.which("npm") is None:
        errors.append("missing_npm")
        diagnostics.append({"code": "missing_npm", "severity": "error"})
    if not paths.pi_executable_path.exists():
        errors.append("missing_pi_executable")
        diagnostics.append({"code": "missing_pi_executable", "severity": "error"})
    elif not os.access(paths.pi_executable_path, os.X_OK):
        errors.append("pi_executable_not_executable")
        diagnostics.append({"code": "pi_executable_not_executable", "severity": "error"})
    else:
        version_check = subprocess.run(
            [str(paths.pi_executable_path), "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if version_check.returncode != 0:
            errors.append("pi_version_check_failed")
            diagnostics.append({"code": "pi_version_check_failed", "severity": "error"})

    for resource_dir in ("extensions", "skills", "prompts", "themes"):
        if not (paths.agent_root / resource_dir).exists():
            warnings.append(f"missing_resource_dir_{resource_dir}")
            diagnostics.append({"code": f"missing_resource_dir_{resource_dir}", "severity": "warning"})

    if paths.bootstrap_state_path.exists():
        try:
            bootstrap = json.loads(paths.bootstrap_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warnings.append("invalid_bootstrap_state")
            diagnostics.append({"code": "invalid_bootstrap_state", "severity": "warning"})
        else:
            if not isinstance(bootstrap, dict) or bootstrap.get("status") != "completed":
                warnings.append("bootstrap_not_completed")
                diagnostics.append({"code": "bootstrap_not_completed", "severity": "warning"})

    computed_error_count = len(errors)
    exit_code = 1 if computed_error_count > 0 else 0
    return DoctorResult(
        errors=errors,
        warnings=warnings,
        requested=True,
        checks_completed=True,
        exit_code=exit_code,
        error_count=computed_error_count,
        warning_count=len(warnings),
        computed_error_count=computed_error_count,
        diagnostics=diagnostics,
    )
