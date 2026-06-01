from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from pydantic import ValidationError

from .base_model import MypiBaseModel
from .models import Manifest, Paths
from .secrets import (
    _detect_pi_wrapper_on_path,
    _parse_devenv_local_yaml_provider,
    _state_files_clean,
    derive_slug,
    resolve_secrets_root,
)


TELEGRAM_TOKEN_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_KEY",
    "TELEGRAM_TOKEN",
    "TELEGRAM_KEY",
)


def _telegram_token_available() -> bool:
    """Check if any accepted Telegram bot token env var is non-empty."""
    return any(
        os.environ.get(var, "").strip()
        for var in TELEGRAM_TOKEN_ENV_VARS
    )


def _telegram_enabled() -> bool:
    """Check if telegram integration is enabled via Nix module option."""
    return os.environ.get("MYPI_TELEGRAM_ENABLE", "").strip().lower() in {"1", "true", "yes"}


def _telegram_paired(paths) -> bool:
    """Check if the user has completed the Telegram pairing flow."""
    paired_file = paths.project_root / ".mypi" / "telegram.paired"
    return paired_file.exists()


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

    # -- Core infrastructure --
    if not paths.settings_path.exists():
        errors.append("missing_settings_shim")
        diagnostics.append({"code": "missing_settings_shim", "severity": "error"})
    if not paths.agent_root.exists():
        errors.append("missing_agent_root")
        diagnostics.append({"code": "missing_agent_root", "severity": "error"})

    if not os.environ.get("DEVENV_ROOT"):
        warnings.append("not_running_via_devenv_shell")
        diagnostics.append({"code": "not_running_via_devenv_shell", "severity": "warning"})

    # -- Manifest --
    manifest_status = _manifest_status(paths)
    if manifest_status == "invalid_manifest":
        errors.append("invalid_manifest")
        diagnostics.append({"code": "invalid_manifest", "severity": "error"})
    elif manifest_status == "manifest_schema_invalid":
        errors.append("manifest_schema_invalid")
        diagnostics.append({"code": "manifest_schema_invalid", "severity": "error"})

    # -- Secret leak check --
    if _secret_leak_likely(paths):
        errors.append("secret_leak_likely")
        diagnostics.append({"code": "secret_leak_likely", "severity": "error"})

    # -- NPM scope --
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

    # -- Settings shim --
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

    # -- Binaries --
    if shutil.which("node") is None:
        errors.append("missing_node")
        diagnostics.append({"code": "missing_node", "severity": "error"})
    if shutil.which("npm") is None:
        errors.append("missing_npm")
        diagnostics.append({"code": "missing_npm", "severity": "error"})
    if shutil.which("secretspec") is None:
        warnings.append("secretspec_not_available")
        diagnostics.append({"code": "secretspec_not_available", "severity": "warning"})

    # -- Pi executable --
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

    # -- Resource directories --
    for resource_dir in ("extensions", "skills", "prompts", "themes"):
        if not (paths.agent_root / resource_dir).exists():
            warnings.append(f"missing_resource_dir_{resource_dir}")
            diagnostics.append({"code": f"missing_resource_dir_{resource_dir}", "severity": "warning"})

    # -- Bootstrap state --
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

    # -- SecretSpec infrastructure checks --
    local_yaml_path = paths.devenv_local_yaml_path
    if not local_yaml_path.exists():
        warnings.append("missing_devenv_local_yaml")
        diagnostics.append({"code": "missing_devenv_local_yaml", "severity": "warning"})
    else:
        # Verify provider path exists and is outside repo
        provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if provider is None:
            warnings.append("devenv_local_yaml_invalid_provider")
            diagnostics.append({"code": "devenv_local_yaml_invalid_provider", "severity": "warning"})
        else:
            raw_path = provider.removeprefix("dotenv:")
            provider_path = Path(raw_path)
            if not provider_path.exists():
                warnings.append("secrets_provider_file_not_found")
                diagnostics.append({"code": "secrets_provider_file_not_found", "severity": "warning"})
            else:
                try:
                    provider_resolved = provider_path.resolve()
                    project_resolved = paths.project_root.resolve()
                    inside_repo = str(provider_resolved).startswith(str(project_resolved))
                    if inside_repo:
                        warnings.append("secrets_provider_inside_repo")
                        diagnostics.append({"code": "secrets_provider_inside_repo", "severity": "warning"})
                except OSError:
                    pass

    # -- secretspec.toml check --
    spec_toml_path = paths.project_root / "secretspec.toml"
    if not spec_toml_path.exists():
        warnings.append("missing_secretspec_toml")
        diagnostics.append({"code": "missing_secretspec_toml", "severity": "warning"})

    # -- Secrets directory check --
    slug = derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    secrets_dir = secrets_root / slug
    if not secrets_dir.exists():
        warnings.append("missing_secrets_directory")
        diagnostics.append({"code": "missing_secrets_directory", "severity": "warning"})

    dotenv_path = secrets_dir / ".env"
    if dotenv_path.exists():
        try:
            dotenv_text = dotenv_path.read_text(encoding="utf-8")
            if any(marker in dotenv_text for marker in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
                pass  # Keys present — expected
        except OSError:
            pass

    # -- State files clean check --
    if not _state_files_clean(paths):
        errors.append("secret_leak_in_state_files")
        diagnostics.append({"code": "secret_leak_in_state_files", "severity": "error"})

    # -- Pi wrapper PATH shadowing check --
    pi_on_path, pi_detail = _detect_pi_wrapper_on_path()
    if not pi_on_path:
        warnings.append("pi_not_on_path")
        diagnostics.append({"code": "pi_not_on_path", "severity": "warning"})
    elif pi_detail and "node_modules/.bin/pi" in pi_detail:
        warnings.append("pi_resolves_to_node_modules_may_bypass_secretspec")
        diagnostics.append({"code": "pi_resolves_to_node_modules_may_bypass_secretspec", "severity": "warning"})

    # -- Telegram readiness (spec: DoctorChecksTelegram) --
    if _telegram_enabled():
        # Check extension installed
        ext_path = paths.agent_root / "node_modules" / "@llblab" / "pi-telegram"
        if not ext_path.exists():
            warnings.append("telegram_extension_not_installed")
            diagnostics.append({"code": "telegram_extension_not_installed", "severity": "warning"})
        # Check token available
        if not _telegram_token_available():
            warnings.append("telegram_bot_token_not_configured")
            diagnostics.append({"code": "telegram_bot_token_not_configured", "severity": "warning"})
        # Check paired state
        if _telegram_token_available() and not _telegram_paired(paths):
            warnings.append("telegram_not_paired")
            diagnostics.append({"code": "telegram_not_paired", "severity": "info"})

        # Optional: check secretspec.toml declares TELEGRAM_BOT_TOKEN (spec: invariant TelegramTokenDeclaredInSecretspecConfig)
        if spec_toml_path.exists():
            try:
                spec_text = spec_toml_path.read_text(encoding="utf-8")
                if "TELEGRAM_BOT_TOKEN" not in spec_text and "TELEGRAM_BOT_KEY" not in spec_text:
                    warnings.append("telegram_token_not_declared_in_secretspec")
                    diagnostics.append({"code": "telegram_token_not_declared_in_secretspec", "severity": "warning"})
            except OSError:
                pass

    # -- Secrets doctor sub-check --
    # Check that the dotenv file actually has values
    if dotenv_path.exists():
        has_any_value = False
        try:
            for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    _, _, value = stripped.partition("=")
                    if value.strip():
                        has_any_value = True
                        break
        except OSError:
            pass
        if not has_any_value:
            warnings.append("secrets_dotenv_no_values")
            diagnostics.append({"code": "secrets_dotenv_no_values", "severity": "warning"})

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
