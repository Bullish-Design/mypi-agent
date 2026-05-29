from __future__ import annotations

import shutil

from mypi_agent.doctor import run_doctor
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync


def test_doctor_reports_missing_artifacts(tmp_path):
    result = run_doctor(Paths(project_root=tmp_path))
    assert "missing_settings_shim" in result.errors
    assert "missing_agent_root" in result.errors
    assert "invalid_manifest" in result.errors
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


def test_doctor_success_after_sync(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)

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
