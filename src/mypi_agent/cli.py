from __future__ import annotations

from pathlib import Path

import typer

from .doctor import run_doctor
from .models import Paths
from .sync import run_sync

app = typer.Typer(help="MYPI-AGENT CLI")

@app.command("sync")
def sync_command(repair_shim: bool = typer.Option(False, "--repair-shim")) -> None:
    paths = Paths(project_root=Path.cwd())
    result = run_sync(paths, explicit=True, repair_shim=repair_shim)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")


@app.command("doctor")
def doctor_command() -> None:
    paths = Paths(project_root=Path.cwd())
    result = run_doctor(paths)
    for error in result.errors:
        typer.echo(f"error: {error}")
    raise typer.Exit(code=result.exit_code)


def main() -> None:
    app()
