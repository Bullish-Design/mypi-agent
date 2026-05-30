from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

from .base_model import MypiBaseModel
from .models import Paths


class SecretspecSetupResult(MypiBaseModel):
    completed: bool
    binary_available: bool
    binary_version: str | None
    config_file_exists: bool
    config_created: bool
    config_valid: bool
    config_has_profiles: bool
    config_profile_count: int
    config_has_secrets: bool
    check_ran: bool
    check_passed: bool
    warnings: list[str]


def _secretspec_binary_version() -> str | None:
    result = subprocess.run(
        ["secretspec", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip().split("\n")[0]
    return None


def _parse_secretspec_toml(path: Path) -> dict[str, object] | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _config_has_profiles(parsed: dict[str, object]) -> bool:
    profiles = parsed.get("profiles")
    if not isinstance(profiles, dict):
        return False
    return len(profiles) > 0


def _config_profile_count(parsed: dict[str, object]) -> int:
    profiles = parsed.get("profiles")
    if not isinstance(profiles, dict):
        return 0
    return len(profiles)


def _config_has_secrets(parsed: dict[str, object]) -> bool:
    """Check that at least one profile has at least one secret key."""
    profiles = parsed.get("profiles")
    if not isinstance(profiles, dict):
        return False
    for _profile_name, profile_data in profiles.items():
        if isinstance(profile_data, dict):
            for _key, value in profile_data.items():
                if isinstance(value, dict) and value.get("description") is not None:
                    return True
    return False


def run_secretspec_setup(paths: Paths) -> SecretspecSetupResult:
    warnings: list[str] = []

    # Rule 1: Verify secretspec binary is available
    binary_available = shutil.which("secretspec") is not None
    binary_version: str | None = None
    if binary_available:
        binary_version = _secretspec_binary_version()
    else:
        warnings.append(
            "SecretSpec is not available — secrets cannot be injected at runtime.\n"
            "  Add pkgs.secretspec to your devenv.nix packages."
        )

    # Rule 2/3: Check config file, create if missing
    config_path = paths.project_root / "secretspec.toml"
    config_file_exists = config_path.exists()
    config_created = False

    if not config_file_exists and binary_available:
        init_result = subprocess.run(
            ["secretspec", "init", "--file", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        config_file_exists = config_path.exists()
        if config_file_exists:
            config_created = True

    # Rule 4: Validate config structure
    config_valid = False
    config_has_profiles = False
    config_profile_count = 0
    config_has_secrets = False

    if config_file_exists:
        parsed = _parse_secretspec_toml(config_path)
        if parsed is not None:
            config_valid = True
            config_has_profiles = _config_has_profiles(parsed)
            config_profile_count = _config_profile_count(parsed)
            config_has_secrets = _config_has_secrets(parsed)

    # Rule 6: If config exists but has no secrets, guide the user
    if config_valid and not config_has_secrets:
        warnings.append(
            "SecretSpec config exists but has no secrets defined.\n"
            "  Add API keys to secretspec.toml under [profiles.default]:\n"
            '    ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi", required = false }\n'
            '    OPENAI_API_KEY = { description = "OpenAI API key for Pi", required = false }\n'
            "  Then run: secretspec check"
        )

    # Rule 5: Run secretspec check to verify secrets are in provider
    check_ran = False
    check_passed = False
    if binary_available and config_valid and config_has_profiles:
        check_result = subprocess.run(
            ["secretspec", "check", "--no-prompt", "--file", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        check_ran = True
        check_passed = check_result.returncode == 0
        if not check_passed:
            warnings.append(
                "SecretSpec: some secrets are not yet configured.\n"
                "  Run: secretspec check"
            )

    return SecretspecSetupResult(
        completed=True,
        binary_available=binary_available,
        binary_version=binary_version,
        config_file_exists=config_file_exists,
        config_created=config_created,
        config_valid=config_valid,
        config_has_profiles=config_has_profiles,
        config_profile_count=config_profile_count,
        config_has_secrets=config_has_secrets,
        check_ran=check_ran,
        check_passed=check_passed,
        warnings=warnings,
    )
