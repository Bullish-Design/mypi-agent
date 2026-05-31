from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

from .base_model import MypiBaseModel
from .models import Paths
from .secrets import (
    _parse_devenv_local_yaml_provider,
    run_secrets_init,
    resolve_secrets_root,
    derive_slug,
)


class SecretspecSetupResult(MypiBaseModel):
    completed: bool
    binary_available: bool
    binary_version: str | None
    config_file_exists: bool
    config_created: bool
    config_upgraded: bool
    config_valid: bool
    config_has_profiles: bool
    config_profile_count: int
    config_has_secrets: bool
    secrets_dir_exists: bool
    dotenv_exists: bool
    local_yaml_exists: bool
    local_yaml_matches_dotenv: bool
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
    """Verify and initialise SecretSpec for this project on shell entry.

    This runs automatically on every shell entry and:
      - Creates the per-repo secrets directory, .env template, devenv.local.yaml,
        and secretspec.toml if they are missing
      - Validates the existing configuration
      - Runs secretspec check if possible
    """
    warnings: list[str] = []

    # --- Phase 1: Bootstrap secrets infrastructure if missing ---
    init_result = run_secrets_init(paths, if_missing=True)
    warnings.extend(init_result.warnings)

    # --- Phase 2: Verify secretspec binary ---
    binary_available = shutil.which("secretspec") is not None
    binary_version: str | None = None
    if binary_available:
        binary_version = _secretspec_binary_version()
    else:
        warnings.append(
            "SecretSpec is not available — secrets cannot be injected at runtime.\n"
            "  Add pkgs.secretspec to your devenv.nix packages."
        )

    # --- Phase 3: Check secretspec.toml ---
    config_path = paths.project_root / "secretspec.toml"
    config_file_exists = config_path.exists()
    config_created = False
    config_upgraded = False

    if config_file_exists:
        config_created = init_result.spec_toml_created
        config_upgraded = init_result.spec_toml_upgraded
    elif not config_file_exists and binary_available:
        # Fallback: try secretspec init as backup
        subprocess.run(
            ["secretspec", "init", "--file", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        config_file_exists = config_path.exists()
        if config_file_exists:
            config_created = True

    # --- Phase 4: Validate config structure ---
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

    if config_file_exists and not config_has_secrets:
        warnings.append(
            "SecretSpec config exists but has no secrets defined.\n"
            "  Consider upgrading via: mypi secrets init"
        )

    # --- Phase 5: Validate devenv.local.yaml matches dotenv path ---
    slug = derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    expected_dotenv = (secrets_root / slug / ".env").resolve()

    local_yaml_path = paths.devenv_local_yaml_path
    local_yaml_exists = local_yaml_path.exists()
    local_yaml_matches_dotenv = False

    if local_yaml_exists:
        provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if provider is not None:
            provider_path = Path(provider.removeprefix("dotenv:"))
            try:
                local_yaml_matches_dotenv = provider_path.resolve() == expected_dotenv
            except OSError:
                pass

    secrets_dir_exists = (secrets_root / slug).exists()
    dotenv_path = expected_dotenv
    dotenv_exists = dotenv_path.exists()

    if local_yaml_exists and not local_yaml_matches_dotenv:
        warnings.append(
            "devenv.local.yaml provider path does not match expected secrets location.\n"
            f"  Expected: dotenv:{expected_dotenv}\n"
            "  Run: mypi secrets init"
        )

    # --- Phase 6: Run secretspec check ---
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
                "  Run: mypi secrets check"
            )

    return SecretspecSetupResult(
        completed=True,
        binary_available=binary_available,
        binary_version=binary_version,
        config_file_exists=config_file_exists,
        config_created=config_created,
        config_upgraded=config_upgraded,
        config_valid=config_valid,
        config_has_profiles=config_has_profiles,
        config_profile_count=config_profile_count,
        config_has_secrets=config_has_secrets,
        secrets_dir_exists=secrets_dir_exists,
        dotenv_exists=dotenv_exists,
        local_yaml_exists=local_yaml_exists,
        local_yaml_matches_dotenv=local_yaml_matches_dotenv,
        check_ran=check_ran,
        check_passed=check_passed,
        warnings=warnings,
    )
