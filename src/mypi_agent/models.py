from __future__ import annotations

import os
from pathlib import Path

from .base_model import AlliumBase


class Paths(AlliumBase):
    project_root: Path

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
            return self.project_root / override
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
        return self.agent_root / "bin" / "pi-agent"

    def as_mapping(self) -> dict[str, str]:
        return {
            "project_root": str(self.project_root),
            "shim_path": str(self.settings_path),
            "agent_root": str(self.agent_root),
            "manifest_path": str(self.manifest_path),
            "pi_executable_path": str(self.pi_executable_path),
        }
