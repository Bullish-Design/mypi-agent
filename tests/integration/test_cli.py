from __future__ import annotations

import json
import os

from typer.testing import CliRunner

from mypi_agent.cli import app

runner = CliRunner()
os.environ.setdefault("MYPI_PI_PACKAGE_VERSION", "1.2.3")


def test_cli_sync_creates_required_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (tmp_path / ".pi" / "settings.json").exists()
    assert (tmp_path / ".agents" / "pi" / "manifest.json").exists()
    assert (tmp_path / ".agents" / "pi" / "skills").exists()
    assert "advisory: upgrades require explicit sync" in result.stdout


def test_cli_sync_no_advisory_without_hash_input_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert first.exit_code == 0
    second = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert second.exit_code == 0
    assert "advisory: upgrades require explicit sync" not in second.stdout


def test_cli_sync_repair_shim_rewrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / ".pi" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"agent_root":"custom"}\n', encoding="utf-8")

    result = runner.invoke(app, ["sync", "--repair-shim"], catch_exceptions=False)

    assert result.exit_code == 0
    assert '"x-mypi-agent"' in settings.read_text(encoding="utf-8")


def test_cli_sync_rejects_user_owned_settings_without_repair(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / ".pi" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"customKey":"value"}\n', encoding="utf-8")
    result = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "not MYPI-managed" in result.stderr


def test_cli_doctor_reports_errors_and_exit_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "error: missing_settings_shim" in result.stdout


def test_cli_doctor_success_after_sync(tmp_path, monkeypatch, fake_npm):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NPM_CONFIG_PREFIX", str(tmp_path / ".agents" / "pi" / "npm-global"))
    sync_result = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert sync_result.exit_code == 0
    pi_executable = tmp_path / ".agents" / "pi" / "node_modules" / ".bin" / "pi"
    pi_executable.parent.mkdir(parents=True, exist_ok=True)
    pi_executable.write_text("#!/bin/sh\necho 1.2.3\n", encoding="utf-8")
    pi_executable.chmod(0o755)

    doctor_result = runner.invoke(app, ["doctor"], catch_exceptions=False)
    assert doctor_result.exit_code == 0


def test_cli_agent_errors_when_pi_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["agent"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "error: Pi is not installed. Run: mypi sync" in result.stdout


def test_cli_sync_json_and_trigger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync", "--trigger", "shell", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    assert '"trigger": "shell"' in result.stdout


def test_cli_sync_diff_prints_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync", "--diff"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "diff: create=" in result.stdout


def test_cli_doctor_json(tmp_path, monkeypatch, fake_npm):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NPM_CONFIG_PREFIX", str(tmp_path / ".agents" / "pi" / "npm-global"))
    sync_result = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert sync_result.exit_code == 0
    pi_executable = tmp_path / ".agents" / "pi" / "node_modules" / ".bin" / "pi"
    pi_executable.parent.mkdir(parents=True, exist_ok=True)
    pi_executable.write_text("#!/bin/sh\necho 1.2.3\n", encoding="utf-8")
    pi_executable.chmod(0o755)
    doctor_result = runner.invoke(app, ["doctor", "--json"], catch_exceptions=False)
    assert doctor_result.exit_code == 0
    assert '"error_count": 0' in doctor_result.stdout


def test_cli_paths_outputs_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["paths"], catch_exceptions=False)
    assert result.exit_code == 0
    assert f"project_root={tmp_path}" in result.stdout
    assert f"shim_path={tmp_path / '.pi' / 'settings.json'}" in result.stdout
    assert f"agent_root={tmp_path / '.agents' / 'pi'}" in result.stdout
    assert f"manifest_path={tmp_path / '.agents' / 'pi' / 'manifest.json'}" in result.stdout
    assert f"pi_executable_path={tmp_path / '.agents' / 'pi' / 'node_modules' / '.bin' / 'pi'}" in result.stdout


def test_cli_paths_json_outputs_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["paths", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["project_root"] == str(tmp_path)
    assert payload["shim_path"] == str(tmp_path / ".pi" / "settings.json")
    assert payload["agent_root"] == str(tmp_path / ".agents" / "pi")
    assert payload["manifest_path"] == str(tmp_path / ".agents" / "pi" / "manifest.json")
    assert payload["pi_executable_path"] == str(tmp_path / ".agents" / "pi" / "node_modules" / ".bin" / "pi")


def test_cli_rejects_unmanaged_directory_without_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MYPI_ALLOW_UNMANAGED", raising=False)
    result = runner.invoke(app, ["paths"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "error: mypi must be run inside a devenv-managed project" in result.stdout


def test_cli_sync_allow_unmanaged_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MYPI_ALLOW_UNMANAGED", raising=False)
    result = runner.invoke(app, ["sync", "--allow-unmanaged"], catch_exceptions=False)
    assert result.exit_code == 0


def test_cli_discovers_project_root_from_subdirectory(tmp_path, monkeypatch):
    project_root = tmp_path / "proj"
    project_root.mkdir(parents=True)
    (project_root / "devenv.yaml").write_text("inputs: {}\nimports: []\n", encoding="utf-8")
    nested = project_root / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("MYPI_ALLOW_UNMANAGED", raising=False)
    result = runner.invoke(app, ["paths", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["project_root"] == str(project_root)


def test_cli_sync_from_subdirectory_writes_to_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "proj"
    project_root.mkdir(parents=True)
    (project_root / "devenv.yaml").write_text("inputs: {}\nimports: []\n", encoding="utf-8")
    nested = project_root / "packages" / "example" / "src"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("MYPI_ALLOW_UNMANAGED", raising=False)

    result = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert result.exit_code == 0
    assert (project_root / ".pi" / "settings.json").exists()
    assert (project_root / ".agents" / "pi" / "manifest.json").exists()
    assert not (nested / ".pi" / "settings.json").exists()
    assert not (nested / ".agents" / "pi" / "manifest.json").exists()
