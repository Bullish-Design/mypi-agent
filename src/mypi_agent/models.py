from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    project_root: Path

    @property
    def pi_dir(self) -> Path:
        return self.project_root / ".pi"

    @property
    def settings_path(self) -> Path:
        return self.pi_dir / "settings.json"

    @property
    def agent_root(self) -> Path:
        return self.project_root / ".agents" / "pi"

    @property
    def manifest_path(self) -> Path:
        return self.agent_root / "installed.json"
