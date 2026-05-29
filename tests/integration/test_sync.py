from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path

from mypi_agent.models import Paths
from mypi_agent.sync import run_sync


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_sync_creates_missing_files_without_overwrite(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)

    assert paths.agent_root.exists()
    assert (paths.agent_root / "extensions").exists()
    assert (paths.agent_root / "skills").exists()
    assert (paths.agent_root / "prompts").exists()
    assert (paths.agent_root / "themes").exists()
    settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    assert settings["enableSkillCommands"] is True
    assert settings["extensions"] == ["../.agents/pi/extensions"]
    assert settings["skills"] == ["../.agents/pi/skills"]


def test_sync_self_heals_manifest_when_corrupt(tmp_path):
    paths = Paths(project_root=tmp_path)
    paths.agent_root.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text("{not json", encoding="utf-8")

    result = run_sync(paths, explicit=True, repair_shim=False)

    payload = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "manifest_recreated" in result.warnings
    assert result.manifest_healed is True


def test_repair_shim_rewrites_when_explicit(tmp_path):
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text('{"agent_root":"custom"}\n', encoding="utf-8")

    result = run_sync(paths, explicit=True, repair_shim=True)

    settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    assert settings["x-mypi-agent"]["agentRoot"] == "../.agents/pi"
    assert result.shim_updated is True


def test_sync_sets_trigger_and_bootstrap_state(tmp_path):
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False, trigger="shell")
    assert result.trigger == "shell"
    bootstrap = json.loads(paths.bootstrap_state_path.read_text(encoding="utf-8"))
    assert bootstrap["status"] == "completed"
    assert bootstrap["trigger"] == "shell"


def test_sync_persists_primitive_registry_with_core_group(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    payload = json.loads(paths.primitive_registry_state_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "core" in payload["groups"]


def test_sync_contract_fields_exposed(tmp_path):
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False)

    assert result.explicit is True
    assert result.repair_shim is False
    assert result.completed is True
    assert result.existing_files_overwritten is False
    assert result.advisory_shown is True
    assert result.upgrade_requires_explicit_sync is True
    assert result.diff_requested is False
    assert result.upgrade_target == "all"
    assert result.would_create_count >= 0
    assert result.would_upgrade_count >= 0
    assert result.preserved_locally_modified_count >= 0


def test_sync_diff_mode_reports_planned_change_counts(tmp_path):
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert result.diff_requested is True
    assert result.would_create_count >= 0
    assert result.would_upgrade_count >= 0
    assert result.preserved_locally_modified_count >= 0


def test_sync_diff_mode_is_strictly_read_only(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    before = _tree_hash(tmp_path)

    result = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    after = _tree_hash(tmp_path)

    assert result.diff_requested is True
    assert result.created == []
    assert result.write_actions == []
    assert before == after


def test_sync_classifies_settings_shim_states(tmp_path):
    paths = Paths(project_root=tmp_path)
    baseline = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert baseline.primitive_file_classifications["settings_shim"] == "missing"

    run_sync(paths, explicit=True, repair_shim=False)
    unchanged = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert unchanged.primitive_file_classifications["settings_shim"] == "managed_unchanged"

    settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    settings["skills"] = ["../.agents/pi/custom-skills"]
    paths.settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    changed = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert changed.primitive_file_classifications["settings_shim"] == "managed_changed"

    settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    settings["userKey"] = True
    paths.settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    user_modified = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert user_modified.primitive_file_classifications["settings_shim"] == "user_modified"

    paths.settings_path.write_text("{broken", encoding="utf-8")
    invalid = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
    assert invalid.primitive_file_classifications["settings_shim"] == "invalid_json"


def test_advisory_gated_on_hash_input_change(tmp_path):
    paths = Paths(project_root=tmp_path)
    first = run_sync(paths, explicit=True, repair_shim=False)
    second = run_sync(paths, explicit=True, repair_shim=False)
    assert first.hash_inputs_changed is True
    assert first.advisory_shown is True
    assert second.hash_inputs_changed is False
    assert second.advisory_shown is False


def test_sync_installs_pi_agent_with_fake_npm(tmp_path, monkeypatch):
    paths = Paths(project_root=tmp_path)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    npm = fake_bin / "npm"
    npm.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "prefix=\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = \"--prefix\" ]; then\n"
        "    shift\n"
        "    prefix=\"$1\"\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$prefix/node_modules/.bin\"\n"
        "cat > \"$prefix/node_modules/.bin/pi\" <<'EOF'\n"
        "#!/usr/bin/env sh\n"
        "echo pi\n"
        "EOF\n"
        "chmod +x \"$prefix/node_modules/.bin/pi\"\n",
        encoding="utf-8",
    )
    npm.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ.get('PATH', '')}")

    result = run_sync(paths, explicit=True, repair_shim=False)
    launcher = paths.agent_root / "bin" / "pi-agent"
    assert result.pi_agent_installed is True
    assert launcher.exists()
    registry = json.loads(paths.primitive_registry_state_path.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1
    assert "core" in registry["groups"]
    assert len(registry["installs"]) == 1
    assert registry["installs"][0]["source_hash"] != ""
    assert registry["installs"][0]["installed_at_rfc3339_utc"] != ""
