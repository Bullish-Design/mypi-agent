from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from .base_model import MypiBaseModel
from .slug import derive_slug

RESOURCE_LITERALS = Literal["extensions", "skills", "prompts", "themes"]


class Manifest(MypiBaseModel):
    schema_version: Literal[1]
    resources: list[RESOURCE_LITERALS]
    pi_package: str
    pi_version: str | None = None
    node_version: str | None = None
    generated_by: str = "mypi-agent"


def _resolve_secrets_root_from_env(project_root: Path) -> Path:
    """Resolve secrets root using env var or default ~/.config path.

    Mirrors the logic in secrets.resolve_secrets_root but without
    importing the full secrets module (avoids circular deps).
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


class Paths(MypiBaseModel):
    project_root: Path

    @classmethod
    def discover(cls, allow_unmanaged: bool = False) -> "Paths":
        env_root = os.environ.get("MYPI_PROJECT_ROOT")
        if env_root:
            return cls(project_root=Path(env_root).resolve())

        cursor = Path.cwd().resolve()
        for candidate in [cursor, *cursor.parents]:
            if (candidate / "devenv.nix").exists() or (candidate / "devenv.yaml").exists():
                return cls(project_root=candidate)

        allow_env = os.environ.get("MYPI_ALLOW_UNMANAGED", "").strip().lower() in {"1", "true", "yes"}
        if allow_unmanaged or allow_env:
            return cls(project_root=cursor)
        raise RuntimeError("error: mypi must be run inside a devenv-managed project")

    @property
    def pi_dir(self) -> Path:
        return self.project_root / ".pi"

    @property
    def settings_path(self) -> Path:
        return self.pi_dir / "settings.json"

    @property
    def agent_root(self) -> Path:
        override = os.environ.get("MYPI_AGENT_ROOT")
        if override:
            root = (self.project_root / override).resolve()
            if root != self.project_root and self.project_root not in root.parents:
                raise RuntimeError("error: MYPI_AGENT_ROOT must stay within project root")
            return root
        return self.project_root / ".agents" / "pi"

    @property
    def manifest_path(self) -> Path:
        return self.agent_root / "manifest.json"

    @property
    def state_dir(self) -> Path:
        return self.agent_root / ".state"

    @property
    def bootstrap_state_path(self) -> Path:
        return self.state_dir / "bootstrap.json"

    @property
    def diagnostics_path(self) -> Path:
        return self.state_dir / "diagnostics.jsonl"

    @property
    def drift_report_path(self) -> Path:
        return self.state_dir / "drift-report.json"

    @property
    def installed_packages_state_path(self) -> Path:
        return self.state_dir / "installed-packages.json"

    @property
    def primitive_registry_state_path(self) -> Path:
        return self.state_dir / "primitive-registry.json"

    @property
    def pi_executable_path(self) -> Path:
        return self.agent_root / "node_modules" / ".bin" / "pi"

    @property
    def devenv_local_yaml_path(self) -> Path:
        return self.project_root / "devenv.local.yaml"

    @property
    def secrets_slug(self) -> str:
        """Derive a stable repo slug for secret storage paths."""
        return derive_slug(self.project_root)

    @property
    def secrets_root(self) -> Path:
        """Resolve the base directory for per-repo secret storage."""
        return _resolve_secrets_root_from_env(self.project_root)

    @property
    def secrets_dir_path(self) -> Path:
        """Per-repo secrets directory (e.g. ~/.config/mypi-agent/secrets/<slug>/)."""
        return self.secrets_root / self.secrets_slug

    @property
    def dotenv_path(self) -> Path:
        """Expected path to the .env file for this repo."""
        return self.secrets_dir_path / ".env"

    def as_mapping(self) -> dict[str, str]:
        return {
            "project_root": str(self.project_root),
            "shim_path": str(self.settings_path),
            "agent_root": str(self.agent_root),
            "manifest_path": str(self.manifest_path),
            "pi_executable_path": str(self.pi_executable_path),
            "secrets_slug": self.secrets_slug,
            "secrets_root": str(self.secrets_root),
            "secrets_dir": str(self.secrets_dir_path),
            "dotenv_path": str(self.dotenv_path),
            "devenv_local_yaml_path": str(self.devenv_local_yaml_path),
        }
