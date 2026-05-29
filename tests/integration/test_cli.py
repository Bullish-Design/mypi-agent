from __future__ import annotations

from typer.testing import CliRunner

from mypi_agent.cli import app

runner = CliRunner()


def test_cli_sync_creates_required_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (tmp_path / ".pi" / "settings.json").exists()
    assert (tmp_path / ".agents" / "pi" / "primitives").exists()
    assert (tmp_path / ".agents" / "pi" / "packages").exists()


def test_cli_sync_repair_shim_rewrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / ".pi" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"agent_root":"custom"}\n', encoding="utf-8")

    result = runner.invoke(app, ["sync", "--repair-shim"], catch_exceptions=False)

    assert result.exit_code == 0
    assert '"../.agents/pi"' in settings.read_text(encoding="utf-8")


def test_cli_doctor_reports_errors_and_exit_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "error: missing_settings_shim" in result.stdout


def test_cli_doctor_success_after_sync(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sync_result = runner.invoke(app, ["sync"], catch_exceptions=False)
    assert sync_result.exit_code == 0

    doctor_result = runner.invoke(app, ["doctor"], catch_exceptions=False)
    assert doctor_result.exit_code == 0
