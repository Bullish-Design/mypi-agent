from __future__ import annotations

import os
import shutil

from mypi_agent.doctor import run_doctor
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync


def test_doctor_reports_missing_artifacts(tmp_path):
    result = run_doctor(Paths(project_root=tmp_path))
    assert "missing_settings_shim" in result.errors
    assert "missing_agent_root" in result.errors
    assert "invalid_manifest" in result.errors
    assert "missing_pi_agent_executable" in result.errors
    assert result.requested is True
    assert result.checks_completed is True
    assert result.error_count == len(result.errors)
    assert result.computed_error_count == len(result.errors)
    assert result.exit_code == 1


def test_doctor_reports_missing_node_and_npm(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = run_doctor(Paths(project_root=tmp_path))
    assert "missing_node" in result.errors
    assert "missing_npm" in result.errors


def test_doctor_success_after_sync(tmp_path, monkeypatch):
    paths = Paths(project_root=tmp_path)
    monkeypatch.setenv("NPM_CONFIG_PREFIX", str(paths.agent_root / "npm-global"))
    run_sync(paths, explicit=True, repair_shim=False)
    paths.pi_executable_path.parent.mkdir(parents=True, exist_ok=True)
    paths.pi_executable_path.write_text("#!/bin/sh\necho 1.2.3\n", encoding="utf-8")
    os.chmod(paths.pi_executable_path, 0o755)

    result = run_doctor(paths)
    assert result.errors == []
    assert result.error_count == 0
    assert result.computed_error_count == 0
    assert result.exit_code == 0


def test_doctor_flags_likely_secret_leak(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    paths.settings_path.write_text('{"token":"SECRET_123"}\n', encoding="utf-8")

    result = run_doctor(paths)
    assert "secret_leak_likely" in result.errors
    assert result.exit_code == 1


def test_doctor_reports_npm_scope_not_project_local(tmp_path, monkeypatch):
    monkeypatch.setenv("NPM_CONFIG_PREFIX", "/tmp/not-project-local")
    result = run_doctor(Paths(project_root=tmp_path))
    assert "npm_scope_not_project_local" in result.errors


def test_doctor_reports_settings_root_mismatch(tmp_path, monkeypatch):
    paths = Paths(project_root=tmp_path)
    monkeypatch.setenv("NPM_CONFIG_PREFIX", str(paths.agent_root / "npm-global"))
    run_sync(paths, explicit=True, repair_shim=False)
    payload = paths.settings_path.read_text(encoding="utf-8").replace("../.agents/pi", "../wrong")
    paths.settings_path.write_text(payload, encoding="utf-8")
    result = run_doctor(paths)
    assert "settings_shim_not_pointing_to_configured_root" in result.errors


def test_doctor_reports_pi_agent_not_executable(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    paths.pi_executable_path.parent.mkdir(parents=True, exist_ok=True)
    paths.pi_executable_path.write_text("#!/bin/sh\necho pi-agent\n", encoding="utf-8")
    os.chmod(paths.pi_executable_path, 0o644)
    result = run_doctor(paths)
    assert "pi_agent_executable_not_executable" in result.errors
