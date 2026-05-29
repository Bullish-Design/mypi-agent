from __future__ import annotations

from pathlib import Path

import typer

from .doctor import run_doctor
from .models import Paths
from .runtime import evaluate_runtime_policy
from .sync import run_sync
from .surfaces_runtime import build_settings_shim_actor, require_settings_shim_actor

app = typer.Typer(help="MYPI-AGENT CLI")

@app.command("sync")
def sync_command(repair_shim: bool = typer.Option(False, "--repair-shim")) -> None:
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("SyncCommandSurface", build_settings_shim_actor(paths))
    result = run_sync(paths, explicit=True, repair_shim=repair_shim)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    if result.advisory_shown and result.upgrade_requires_explicit_sync:
        typer.echo("advisory: upgrades require explicit sync")


@app.command("doctor")
def doctor_command() -> None:
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("DoctorCommandSurface", build_settings_shim_actor(paths))
    result = run_doctor(paths)
    for error in result.errors:
        typer.echo(f"error: {error}")
    raise typer.Exit(code=result.exit_code)


@app.command("run")
def run_command() -> None:
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("MypiCommand", build_settings_shim_actor(paths))
    result = evaluate_runtime_policy()
    if result.missing_env_files_warning and result.warning_reason_missing_env_files_only:
        typer.echo("warning: missing_env_files")


def main() -> None:
    app()
