from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import typer

from .doctor import run_doctor
from .models import Paths
from .sync import run_sync
from .sync import needs_sync
from .surfaces_runtime import build_settings_shim_actor, require_settings_shim_actor

app = typer.Typer(help="MYPI-AGENT CLI")

@app.command("sync")
def sync_command(
    trigger: str = typer.Option("manual", "--trigger"),
    repair_shim: bool = typer.Option(False, "--repair-shim"),
    diff_mode: bool = typer.Option(False, "--diff"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if trigger not in {"manual", "shell"}:
        raise typer.BadParameter("--trigger must be one of: manual, shell")
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("SyncCommandSurface", build_settings_shim_actor(paths))
    result = run_sync(
        paths,
        explicit=True,
        repair_shim=repair_shim,
        trigger=trigger,
        diff_requested=diff_mode,
        upgrade_target="all",
    )
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    if result.diff_requested:
        typer.echo(
            "diff: create=%d upgrade=%d preserved_modified=%d"
            % (
                result.would_create_count,
                result.would_upgrade_count,
                result.preserved_locally_modified_count,
            )
        )
    if result.advisory_shown and result.upgrade_requires_explicit_sync:
        typer.echo("advisory: upgrades require explicit sync")


@app.command("doctor")
def doctor_command(json_output: bool = typer.Option(False, "--json")) -> None:
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("DoctorCommandSurface", build_settings_shim_actor(paths))
    result = run_doctor(paths)
    if json_output:
        typer.echo(json.dumps(result.model_dump(), indent=2))
        raise typer.Exit(code=result.exit_code)
    for error in result.errors:
        typer.echo(f"error: {error}")
    raise typer.Exit(code=result.exit_code)


@app.command("agent")
def agent_command(args: list[str] = typer.Argument(None)) -> None:
    paths = Paths(project_root=Path.cwd())
    require_settings_shim_actor("AgentCommandSurface", build_settings_shim_actor(paths))
    pi_executable = paths.pi_executable_path
    if not pi_executable.exists() or not os.access(pi_executable, os.X_OK):
        typer.echo("error: Pi is not installed. Run: mypi sync")
        raise typer.Exit(code=1)
    result = subprocess.run(
        [str(pi_executable), *(args or [])],
        check=False,
    )
    raise typer.Exit(code=result.returncode)


@app.command("pi")
def pi_command(args: list[str] = typer.Argument(None)) -> None:
    agent_command(args=args)


@app.command("paths")
def paths_command(json_output: bool = typer.Option(False, "--json")) -> None:
    paths = Paths(project_root=Path.cwd())
    payload = paths.as_mapping()
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    for key, value in payload.items():
        typer.echo(f"{key}={value}")


@app.command("needs-sync")
def needs_sync_command(
    trigger: str = typer.Option("manual", "--trigger"),
) -> None:
    if trigger not in {"manual", "shell"}:
        raise typer.BadParameter("--trigger must be one of: manual, shell")
    paths = Paths(project_root=Path.cwd())
    if needs_sync(paths):
        raise typer.Exit(code=0)
    raise typer.Exit(code=1)


def main() -> None:
    app()
