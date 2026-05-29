from __future__ import annotations

import json

from mypi_agent.models import Paths
from mypi_agent.sync import run_sync


def test_sync_creates_missing_files_without_overwrite(tmp_path):
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text('{"agent_root":"custom"}\n', encoding="utf-8")

    run_sync(paths, explicit=True, repair_shim=False)

    assert paths.agent_root.exists()
    assert (paths.agent_root / "primitives").exists()
    assert (paths.agent_root / "packages").exists()
    assert json.loads(paths.settings_path.read_text(encoding="utf-8"))["agent_root"] == "custom"


def test_sync_self_heals_manifest_when_corrupt(tmp_path):
    paths = Paths(project_root=tmp_path)
    paths.agent_root.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text("{not json", encoding="utf-8")

    result = run_sync(paths, explicit=True, repair_shim=False)

    payload = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "manifest_recreated" in result.warnings


def test_repair_shim_rewrites_when_explicit(tmp_path):
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text('{"agent_root":"custom"}\n', encoding="utf-8")

    run_sync(paths, explicit=True, repair_shim=True)

    assert json.loads(paths.settings_path.read_text(encoding="utf-8"))["agent_root"] == "../.agents/pi"
