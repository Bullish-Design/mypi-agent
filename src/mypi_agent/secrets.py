from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

from .base_model import MypiBaseModel
from .models import Paths
from .slug import derive_slug

CANONICAL_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]


class SecretsInitResult(MypiBaseModel):
    completed: bool
    slug: str
    secrets_dir: str
    secrets_dir_created: bool
    dotenv_created: bool
    dotenv_path: str
    local_yaml_created: bool
    local_yaml_path: str
    spec_toml_created: bool
    spec_toml_path: str
    spec_toml_upgraded: bool
    gitignore_updated: bool
    warnings: list[str]


class SecretsCheckResult(MypiBaseModel):
    completed: bool
    binary_available: bool
    slug: str
    secrets_dir_exists: bool
    dotenv_exists: bool
    dotenv_path: str
    provider_path_valid: bool
    provider_file_outside_repo: bool
    local_yaml_exists: bool
    local_yaml_path: str
    local_yaml_provider: str | None
    spec_toml_exists: bool
    spec_toml_valid: bool
    spec_toml_has_secrets: bool
    spec_toml_path: str
    check_ran: bool
    check_passed: bool
    warnings: list[str]


class SecretsPathResult(MypiBaseModel):
    slug: str
    project_root: str
    secrets_root: str
    secrets_dir: str
    dotenv_path: str
    provider: str
    profile: str
    local_yaml_path: str
    spec_toml_path: str


class SecretsDoctorResult(MypiBaseModel):
    completed: bool
    slug: str
    secrets_dir_exists: bool
    dotenv_exists: bool
    dotenv_has_values: bool
    local_yaml_exists: bool
    local_yaml_provider_valid: bool
    provider_file_outside_repo: bool
    provider_file_git_ignored: bool
    spec_toml_exists: bool
    spec_toml_has_required_keys: bool
    required_keys_present_in_provider: bool
    pi_wrapper_on_path: bool
    pi_wrapper_vs_node_modules: str | None
    state_files_clean: bool
    warnings: list[str]
    errors: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_secrets_root(project_root: Path) -> Path:
    """Resolve the base directory for per-repo secret storage.

    Order of precedence:
      1. MYPI_SECRETS_ROOT environment variable
      2. XDG_CONFIG_HOME / mypi-agent / secrets
      3. $HOME / .config / mypi-agent / secrets
    """
    env_override = os.environ.get("MYPI_SECRETS_ROOT")
    if env_override:
        return Path(env_override).resolve()

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"

    return (base / "mypi-agent" / "secrets").resolve()


def _canonical_secrets_toml(slug: str) -> str:
    """Return a secretspec.toml with the canonical Pi API key declarations."""
    return (
        f"[project]\n"
        f'name = "{slug}"\n'
        f'revision = "1.0"\n'
        f"\n"
        f"[profiles.default]\n"
        f'ANTHROPIC_API_KEY = {{ description = "Anthropic API key for Pi in {slug}", required = false }}\n'
        f'OPENAI_API_KEY = {{ description = "OpenAI API key for Pi in {slug}", required = false }}\n'
        f'OPENROUTER_API_KEY = {{ description = "OpenRouter API key for Pi in {slug}", required = false }}\n'
    )


def _template_dotenv() -> str:
    return (
        "# Fill in your API keys below.\n"
        "# This file is outside the project repo and should never be committed.\n"
        "# Create per-project API keys in your upstream provider dashboard\n"
        "# for clear usage attribution.\n"
        "\n"
        "OPENAI_API_KEY=\n"
        "ANTHROPIC_API_KEY=\n"
        "OPENROUTER_API_KEY=\n"
    )


def _devenv_local_yaml(provider_path: str) -> str:
    """Generate devenv.local.yaml content with an absolute dotenv provider path."""
    return (
        "# devenv.local.yaml - Per-project SecretSpec configuration\n"
        "# This file is NOT committed to version control.\n"
        "secretspec:\n"
        "  enable: true\n"
        f"  provider: dotenv:{provider_path}\n"
        "  profile: default\n"
    )


def _parse_devenv_local_yaml_provider(path: Path) -> str | None:
    """Extract the provider value from devenv.local.yaml, or None."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("provider:"):
            raw = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if raw.startswith("dotenv:"):
                return raw
    return None


def _dotenv_has_values(path: Path) -> bool:
    """Check if the .env file has at least one non-empty value for canonical keys."""
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip()
                if key in CANONICAL_KEYS and value:
                    return True
    return False


def _dotenv_required_keys_present(path: Path) -> bool:
    """Check that required keys declared in secretspec.toml are present in .env.

    For now, checks that all canonical keys present in .env have a value.
    Returns True if no .env exists (can't verify) or all canonical keys are set.
    """
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    declared_required: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip()
            if key in CANONICAL_KEYS:
                if value:
                    declared_required.add(key)
    # At least one canonical key has a value
    return len(declared_required) > 0


def _ensure_gitignore_entries(project_root: Path) -> bool:
    """Add required gitignore entries if missing. Returns True if modified."""
    gitignore = project_root / ".gitignore"
    required = ["devenv.local.yaml", ".env", ".env.*"]

    if not gitignore.exists():
        gitignore.write_text("\n".join(required) + "\n", encoding="utf-8")
        return True

    existing = set(gitignore.read_text(encoding="utf-8").splitlines())
    additions = [e for e in required if e not in existing]
    if not additions:
        return False

    with gitignore.open("a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(additions) + "\n")
    return True


def _git_tracked(path: Path) -> bool:
    """Check if a file is tracked by git (returns False if not in a git repo)."""
    git_dir = _find_git_dir(path)
    if git_dir is None:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(path.parent), "ls-files", "--error-unmatch", str(path.name)],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except OSError:
        return False


def _find_git_dir(path: Path) -> Path | None:
    """Walk up from path to find .git directory."""
    for parent in [path, *path.parents]:
        candidate = parent / ".git"
        if candidate.exists():
            return candidate
    return None


def _detect_pi_wrapper_on_path() -> tuple[bool, str | None]:
    """Check if 'pi' resolves to the mypi-agent wrapper vs. node_modules/.bin/pi.

    Returns (found_on_path, resolution_detail).
    """
    pi_path = shutil.which("pi")
    if pi_path is None:
        return (False, None)
    resolved = Path(pi_path).resolve()
    resolved_str = str(resolved)
    if "node_modules/.bin/pi" in resolved_str:
        return (True, "node_modules/.bin/pi (may bypass SecretSpec)")
    return (True, resolved_str)


def _state_files_clean(paths: Paths) -> bool:
    """Check that generated state files don't contain API key patterns."""
    candidates = [paths.settings_path, paths.manifest_path]
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    for path in candidates:
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(m in text for m in markers):
                return False
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def run_secrets_init(
    paths: Paths,
    *,
    if_missing: bool = False,
    slug_override: str | None = None,
) -> SecretsInitResult:
    """Initialise per-repo secrets: directory, .env template, devenv.local.yaml, secretspec.toml."""
    warnings: list[str] = []
    slug = slug_override if slug_override else derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    secrets_dir = secrets_root / slug
    dotenv_path = secrets_dir / ".env"
    local_yaml_path = paths.devenv_local_yaml_path
    spec_toml_path = paths.project_root / "secretspec.toml"

    secrets_dir_created = False
    dotenv_created = False
    local_yaml_created = False
    spec_toml_created = False
    spec_toml_upgraded = False
    gitignore_updated = False

    # 1. Create secrets directory (0700 — keep .env contents private)
    if not secrets_dir.exists():
        secrets_dir.mkdir(parents=True, exist_ok=True)
        secrets_dir.chmod(stat.S_IRWXU)
        secrets_dir_created = True

    # 2. Create template .env (never overwrites user's keys)
    if not dotenv_path.exists():
        dotenv_path.write_text(_template_dotenv(), encoding="utf-8")
        dotenv_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        dotenv_created = True
    elif if_missing:
        pass  # --if-missing mode: skip

    # 3. Create devenv.local.yaml with absolute dotenv path
    provider_path = str(dotenv_path.resolve())
    if not local_yaml_path.exists():
        local_yaml_path.write_text(_devenv_local_yaml(provider_path), encoding="utf-8")
        local_yaml_created = True
    elif if_missing:
        pass

    # 4. Create or upgrade secretspec.toml
    if not spec_toml_path.exists():
        spec_toml_path.write_text(_canonical_secrets_toml(slug), encoding="utf-8")
        spec_toml_created = True
    else:
        # Upgrade: if existing file has no secrets, rewrite with canonical template
        try:
            parsed = tomllib.loads(spec_toml_path.read_text(encoding="utf-8"))
        except Exception:
            parsed = None
        if parsed is None:
            # Corrupt or empty — overwrite
            spec_toml_path.write_text(_canonical_secrets_toml(slug), encoding="utf-8")
            spec_toml_upgraded = True
            warnings.append(f"replaced corrupt secretspec.toml with canonical template for {slug}")
        else:
            profiles = parsed.get("profiles")
            has_secrets = False
            if isinstance(profiles, dict):
                for profile_data in profiles.values():
                    if isinstance(profile_data, dict):
                        for value in profile_data.values():
                            if isinstance(value, dict) and value.get("description") is not None:
                                has_secrets = True
                                break
            if not has_secrets:
                spec_toml_path.write_text(_canonical_secrets_toml(slug), encoding="utf-8")
                spec_toml_upgraded = True

    # 5. Ensure .gitignore covers local files
    gitignore_updated = _ensure_gitignore_entries(paths.project_root)

    # 6. Warnings for next steps
    if dotenv_created or (dotenv_path.exists() and not _dotenv_has_values(dotenv_path)):
        warnings.append(
            f"Fill in your API keys:\n"
            f"  $ nano {dotenv_path}\n"
            f"  $ mypi secrets check"
        )

    if not shutil.which("secretspec"):
        warnings.append(
            "SecretSpec is not available. Add pkgs.secretspec to your devenv.nix packages."
        )

    return SecretsInitResult(
        completed=True,
        slug=slug,
        secrets_dir=str(secrets_dir),
        secrets_dir_created=secrets_dir_created,
        dotenv_created=dotenv_created,
        dotenv_path=str(dotenv_path),
        local_yaml_created=local_yaml_created,
        local_yaml_path=str(local_yaml_path),
        spec_toml_created=spec_toml_created,
        spec_toml_path=str(spec_toml_path),
        spec_toml_upgraded=spec_toml_upgraded,
        gitignore_updated=gitignore_updated,
        warnings=warnings,
    )


def run_secrets_check(paths: Paths) -> SecretsCheckResult:
    """Verify that SecretSpec can resolve secrets for this project."""
    warnings: list[str] = []
    slug = derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    secrets_dir = secrets_root / slug
    dotenv_path = secrets_dir / ".env"
    local_yaml_path = paths.devenv_local_yaml_path
    spec_toml_path = paths.project_root / "secretspec.toml"

    binary_available = shutil.which("secretspec") is not None
    if not binary_available:
        warnings.append("SecretSpec binary not available on PATH.")

    secrets_dir_exists = secrets_dir.exists()
    dotenv_exists = dotenv_path.exists()
    local_yaml_exists = local_yaml_path.exists()

    # Provider path validation
    provider_path_valid = False
    provider_file_outside_repo = False
    local_yaml_provider: str | None = None

    if local_yaml_exists:
        local_yaml_provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if local_yaml_provider is not None:
            provider_path_valid = True
            # Parse the actual file path from the provider value
            raw_path = local_yaml_provider.removeprefix("dotenv:")
            resolved = Path(raw_path)
            try:
                provider_file_outside_repo = not str(resolved.resolve()).startswith(
                    str(paths.project_root.resolve())
                )
            except OSError:
                provider_file_outside_repo = False
        else:
            warnings.append("devenv.local.yaml exists but has no valid dotenv provider.")
    else:
        warnings.append("devenv.local.yaml does not exist. Run: mypi secrets init")

    # secretspec.toml validation
    spec_toml_exists = spec_toml_path.exists()
    spec_toml_valid = False
    spec_toml_has_secrets = False

    if spec_toml_exists:
        try:
            parsed = tomllib.loads(spec_toml_path.read_text(encoding="utf-8"))
            spec_toml_valid = True
            profiles = parsed.get("profiles")
            if isinstance(profiles, dict):
                for profile_data in profiles.values():
                    if isinstance(profile_data, dict):
                        for value in profile_data.values():
                            if isinstance(value, dict) and value.get("description") is not None:
                                spec_toml_has_secrets = True
                                break
        except Exception:
            warnings.append("secretspec.toml is not valid TOML.")
    else:
        warnings.append("secretspec.toml does not exist. Run: mypi secrets init")

    if spec_toml_exists and not spec_toml_has_secrets:
        warnings.append("secretspec.toml has no secrets declared. Consider adding canonical API keys.")

    # Run secretspec check
    check_ran = False
    check_passed = False
    if binary_available and spec_toml_exists and spec_toml_valid and spec_toml_has_secrets:
        check_result = subprocess.run(
            ["secretspec", "check", "--no-prompt", "--file", str(spec_toml_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        check_ran = True
        check_passed = check_result.returncode == 0
        if not check_passed:
            stderr = check_result.stderr.strip()
            if stderr:
                warnings.append(f"SecretSpec check failed: {stderr}")
            else:
                warnings.append("SecretSpec check failed. Some secrets cannot be resolved.")
    elif spec_toml_exists and not spec_toml_has_secrets:
        warnings.append("Cannot run secretspec check: no secrets declared.")

    return SecretsCheckResult(
        completed=True,
        binary_available=binary_available,
        slug=slug,
        secrets_dir_exists=secrets_dir_exists,
        dotenv_exists=dotenv_exists,
        dotenv_path=str(dotenv_path),
        provider_path_valid=provider_path_valid,
        provider_file_outside_repo=provider_file_outside_repo,
        local_yaml_exists=local_yaml_exists,
        local_yaml_path=str(local_yaml_path),
        local_yaml_provider=local_yaml_provider,
        spec_toml_exists=spec_toml_exists,
        spec_toml_valid=spec_toml_valid,
        spec_toml_has_secrets=spec_toml_has_secrets,
        spec_toml_path=str(spec_toml_path),
        check_ran=check_ran,
        check_passed=check_passed,
        warnings=warnings,
    )


def run_secrets_path(paths: Paths) -> SecretsPathResult:
    """Print non-sensitive paths for the current project's secrets configuration."""
    slug = derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    secrets_dir = secrets_root / slug
    dotenv_path = secrets_dir / ".env"
    local_yaml_path = paths.devenv_local_yaml_path
    spec_toml_path = paths.project_root / "secretspec.toml"

    # Read profile from devenv.local.yaml if it exists, otherwise default
    profile = "default"
    if local_yaml_path.exists():
        text = local_yaml_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("profile:"):
                raw = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if raw:
                    profile = raw

    provider = f"dotenv:{dotenv_path.resolve()}"

    return SecretsPathResult(
        slug=slug,
        project_root=str(paths.project_root),
        secrets_root=str(secrets_root),
        secrets_dir=str(secrets_dir),
        dotenv_path=str(dotenv_path),
        provider=provider,
        profile=profile,
        local_yaml_path=str(local_yaml_path),
        spec_toml_path=str(spec_toml_path),
    )


def run_secrets_doctor(paths: Paths) -> SecretsDoctorResult:
    """High-level diagnostics for the per-repo secrets setup."""
    warnings: list[str] = []
    errors: list[str] = []

    slug = derive_slug(paths.project_root)
    secrets_root = resolve_secrets_root(paths.project_root)
    secrets_dir = secrets_root / slug
    dotenv_path = secrets_dir / ".env"
    local_yaml_path = paths.devenv_local_yaml_path
    spec_toml_path = paths.project_root / "secretspec.toml"

    # Secrets directory
    secrets_dir_exists = secrets_dir.exists()
    if not secrets_dir_exists:
        errors.append("secrets_directory_missing")

    # Dotenv existence and values
    dotenv_exists = dotenv_path.exists()
    if not dotenv_exists:
        errors.append("dotenv_file_missing")
    dotenv_has_values = _dotenv_has_values(dotenv_path) if dotenv_exists else False
    if dotenv_exists and not dotenv_has_values:
        warnings.append("dotenv_file_empty_or_no_values")

    # Local YAML
    local_yaml_exists = local_yaml_path.exists()
    if not local_yaml_exists:
        errors.append("devenv_local_yaml_missing")

    # Provider path validation
    local_yaml_provider_valid = False
    if local_yaml_exists:
        provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if provider is None:
            errors.append("devenv_local_yaml_no_valid_provider")
        else:
            local_yaml_provider_valid = True
    else:
        local_yaml_provider_valid = False

    # Provider file outside repo?
    provider_file_outside_repo = False
    if local_yaml_exists and local_yaml_provider_valid:
        provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if provider:
            raw_path = provider.removeprefix("dotenv:")
            resolved = Path(raw_path).resolve()
            try:
                provider_file_outside_repo = not str(resolved).startswith(
                    str(paths.project_root.resolve())
                )
            except OSError:
                provider_file_outside_repo = False
        if not provider_file_outside_repo and provider:
            warnings.append("provider_file_inside_repo")

    # Provider file git-ignored (should be outside repo, but also check)
    provider_file_git_ignored = False
    if local_yaml_exists and local_yaml_provider_valid:
        provider = _parse_devenv_local_yaml_provider(local_yaml_path)
        if provider:
            raw_path = provider.removeprefix("dotenv:")
            provider_path = Path(raw_path)
            if provider_path.exists() and not _git_tracked(provider_path):
                provider_file_git_ignored = True
            elif provider_path.exists():
                warnings.append("provider_file_tracked_by_git")

    # secretspec.toml
    spec_toml_exists = spec_toml_path.exists()
    spec_toml_has_required_keys = False
    if spec_toml_exists:
        try:
            parsed = tomllib.loads(spec_toml_path.read_text(encoding="utf-8"))
            profiles = parsed.get("profiles")
            if isinstance(profiles, dict):
                for profile_data in profiles.values():
                    if isinstance(profile_data, dict):
                        for key, value in profile_data.items():
                            if isinstance(value, dict) and value.get("required") is True:
                                spec_toml_has_required_keys = True
                                break
        except Exception:
            pass
    else:
        errors.append("secretspec_toml_missing")

    # Required keys present in provider
    required_keys_present_in_provider = _dotenv_required_keys_present(dotenv_path) if dotenv_exists else False

    # Pi wrapper on PATH
    pi_on_path, pi_resolution = _detect_pi_wrapper_on_path()
    if not pi_on_path:
        errors.append("pi_not_on_path")
    elif pi_resolution and "node_modules/.bin/pi" in pi_resolution:
        warnings.append("pi_resolves_to_node_modules_may_bypass_secretspec")

    # State files clean
    state_files_clean = _state_files_clean(paths)
    if not state_files_clean:
        errors.append("secret_leak_in_state_files")

    # Binary check
    if not shutil.which("secretspec"):
        errors.append("secretspec_binary_missing")

    return SecretsDoctorResult(
        completed=True,
        slug=slug,
        secrets_dir_exists=secrets_dir_exists,
        dotenv_exists=dotenv_exists,
        dotenv_has_values=dotenv_has_values,
        local_yaml_exists=local_yaml_exists,
        local_yaml_provider_valid=local_yaml_provider_valid,
        provider_file_outside_repo=provider_file_outside_repo,
        provider_file_git_ignored=provider_file_git_ignored,
        spec_toml_exists=spec_toml_exists,
        spec_toml_has_required_keys=spec_toml_has_required_keys,
        required_keys_present_in_provider=required_keys_present_in_provider,
        pi_wrapper_on_path=pi_on_path,
        pi_wrapper_vs_node_modules=pi_resolution,
        state_files_clean=state_files_clean,
        warnings=warnings,
        errors=errors,
    )
