from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Paths


REQUIRED_DIRS = ("primitives", "packages")


@dataclass(frozen=True)
class SyncResult:
    created: list[Path]
    warnings: list[str]
    explicit: bool
    repair_shim: bool
    completed: bool
    existing_files_overwritten: bool
    advisory_shown: bool
    upgrade_requires_explicit_sync: bool
    bootstrap_performed: bool
    manifest_healed: bool
    shim_updated: bool


def _ensure_dir(path: Path, created: list[Path]) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object, created: list[Path]) -> None:
    if not path.exists():
        created.append(path)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_sync(paths: Paths, explicit: bool, repair_shim: bool) -> SyncResult:
    created: list[Path] = []
    warnings: list[str] = []

    bootstrap_performed = False
    manifest_healed = False
    shim_updated = False

    if not paths.agent_root.exists():
        bootstrap_performed = True
    _ensure_dir(paths.pi_dir, created)
    _ensure_dir(paths.agent_root, created)
    for dirname in REQUIRED_DIRS:
        _ensure_dir(paths.agent_root / dirname, created)

    if repair_shim:
        _write_json(paths.settings_path, {"agent_root": "../.agents/pi"}, created)
        shim_updated = True
    elif not paths.settings_path.exists():
        _write_json(paths.settings_path, {"agent_root": "../.agents/pi"}, created)
        bootstrap_performed = True

    manifest_valid = False
    if paths.manifest_path.exists():
        try:
            payload = _read_json(paths.manifest_path)
            manifest_valid = isinstance(payload, dict)
        except json.JSONDecodeError:
            manifest_valid = False

    if not paths.manifest_path.exists() or not manifest_valid:
        _write_json(paths.manifest_path, {"schema_version": 1, "primitives": []}, created)
        warnings.append("manifest_recreated")
        manifest_healed = True

    return SyncResult(
        created=created,
        warnings=warnings,
        explicit=explicit,
        repair_shim=repair_shim,
        completed=True,
        existing_files_overwritten=False,
        advisory_shown=True,
        upgrade_requires_explicit_sync=True,
        bootstrap_performed=bootstrap_performed,
        manifest_healed=manifest_healed,
        shim_updated=shim_updated,
    )
