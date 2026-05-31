from __future__ import annotations

import json
import subprocess

import typer

from .doctor import run_doctor
from .models import Paths
from .secrets import run_secrets_check, run_secrets_doctor, run_secrets_init, run_secrets_path
from .secretspec_setup import run_secretspec_setup
from .sync import run_sync
from .sync import needs_sync
from .surfaces_runtime import build_settings_shim_actor, require_settings_shim_actor

app = typer.Typer(help="MYPI-AGENT CLI")
secrets_app = typer.Typer(help="Manage per-repo SecretSpec secrets")


def _resolve_paths(allow_unmanaged: bool = False) -> Paths:
    try:
        return Paths.discover(allow_unmanaged=allow_unmanaged)
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------


@app.command("sync")
def sync_command(
    trigger: str = typer.Option("manual", "--trigger"),
    repair_shim: bool = typer.Option(False, "--repair-shim"),
    diff_mode: bool = typer.Option(False, "--diff"),
    json_output: bool = typer.Option(False, "--json"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    if trigger not in {"manual", "shell"}:
        raise typer.BadParameter("--trigger must be one of: manual, shell")
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    require_settings_shim_actor("SyncCommandSurface", build_settings_shim_actor(paths))
    try:
        result = run_sync(
            paths,
            explicit=True,
            repair_shim=repair_shim,
            trigger=trigger,
            diff_requested=diff_mode,
            upgrade_target="all",
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
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


@app.command("secretspec-setup")
def secretspec_setup_command(
    json_output: bool = typer.Option(False, "--json"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    result = run_secretspec_setup(paths)
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")


@app.command("doctor")
def doctor_command(json_output: bool = typer.Option(False, "--json")) -> None:
    paths = _resolve_paths()
    require_settings_shim_actor("DoctorCommandSurface", build_settings_shim_actor(paths))
    result = run_doctor(paths)
    if json_output:
        typer.echo(json.dumps(result.model_dump(), indent=2))
        raise typer.Exit(code=result.exit_code)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for error in result.errors:
        typer.echo(f"error: {error}")
    raise typer.Exit(code=result.exit_code)


@app.command("agent")
def agent_command() -> None:
    paths = _resolve_paths()
    pi_path = paths.pi_executable_path
    if not pi_path.exists():
        typer.echo("error: Pi is not installed. Run: mypi sync")
        raise typer.Exit(code=1)
    raise typer.Exit(
        code=subprocess.run([str(pi_path)], check=False).returncode,
    )


@app.command("paths")
def paths_command(json_output: bool = typer.Option(False, "--json")) -> None:
    paths = _resolve_paths()
    payload = paths.as_mapping()
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    for key, value in payload.items():
        typer.echo(f"{key}={value}")


@app.command("needs-sync")
def needs_sync_command(
    trigger: str = typer.Option("manual", "--trigger"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    if trigger not in {"manual", "shell"}:
        raise typer.BadParameter("--trigger must be one of: manual, shell")
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    if needs_sync(paths):
        raise typer.Exit(code=0)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# secrets subcommand group
# ---------------------------------------------------------------------------


@app.callback()
def _main_callback() -> None:
    pass


app.add_typer(secrets_app, name="secrets", help="Manage per-repo SecretSpec secrets")


@secrets_app.command("init")
def secrets_init_command(
    if_missing: bool = typer.Option(True, "--if-missing"),
    json_output: bool = typer.Option(False, "--json"),
    slug: str | None = typer.Option(None, "--slug"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    """Initialise per-repo secrets: directory, .env template, devenv.local.yaml, secretspec.toml."""
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    result = run_secrets_init(paths, if_missing=if_missing, slug_override=slug)
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return

    if result.secrets_dir_created:
        typer.echo(f"  → Created secrets directory: {result.secrets_dir}")
    if result.dotenv_created:
        typer.echo(f"  → Created template .env:     {result.dotenv_path}")
    if result.local_yaml_created:
        typer.echo(f"  → Created local config:       {result.local_yaml_path}")
    if result.spec_toml_created:
        typer.echo(f"  → Created secret declaration: {result.spec_toml_path}")
    if result.spec_toml_upgraded:
        typer.echo(f"  → Upgraded secretspec.toml:   {result.spec_toml_path}")
    if result.gitignore_updated:
        typer.echo("  → Updated .gitignore with local config patterns")

    for warning in result.warnings:
        typer.echo(f"warning: {warning}")

    if result.dotenv_created:
        typer.echo("")
        typer.echo("  Next steps:")
        typer.echo(f"    $ nano {result.dotenv_path}")
        typer.echo("    $ mypi secrets check")


@secrets_app.command("check")
def secrets_check_command(
    json_output: bool = typer.Option(False, "--json"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    """Verify that SecretSpec can resolve secrets for this project."""
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    result = run_secrets_check(paths)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        raise typer.Exit(code=1 if result.warnings else 0)

    status = "✓" if result.check_passed else "✗"
    typer.echo(f"  Slug:                {result.slug}")
    typer.echo(f"  SecretSpec binary:   {'✓' if result.binary_available else '✗'}")
    typer.echo(f"  Secrets directory:   {'✓' if result.secrets_dir_exists else '✗'}")
    typer.echo(f"  .env file:           {'✓' if result.dotenv_exists else '✗'}")
    typer.echo(f"  Provider path valid: {'✓' if result.provider_path_valid else '✗'}")
    typer.echo(f"  Provider outside repo: {'✓' if result.provider_file_outside_repo else '✗'}")
    typer.echo(f"  devenv.local.yaml:   {'✓' if result.local_yaml_exists else '✗'}")
    typer.echo(f"  secretspec.toml:     {'✓' if result.spec_toml_exists else '✗'}")
    typer.echo(f"  SecretSpec check:    {status}")

    for warning in result.warnings:
        typer.echo(f"warning: {warning}")

    raise typer.Exit(code=1 if not result.check_passed and result.check_ran else 0)


@secrets_app.command("path")
def secrets_path_command(
    json_output: bool = typer.Option(False, "--json"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    """Print non-sensitive paths for the current project's secrets configuration."""
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    result = run_secrets_path(paths)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return

    typer.echo(f"slug:            {result.slug}")
    typer.echo(f"project root:    {result.project_root}")
    typer.echo(f"secrets root:    {result.secrets_root}")
    typer.echo(f"secrets dir:     {result.secrets_dir}")
    typer.echo(f"dotenv file:     {result.dotenv_path}")
    typer.echo(f"provider:        {result.provider}")
    typer.echo(f"profile:         {result.profile}")
    typer.echo(f"local config:    {result.local_yaml_path}")
    typer.echo(f"spec file:       {result.spec_toml_path}")


@secrets_app.command("doctor")
def secrets_doctor_command(
    json_output: bool = typer.Option(False, "--json"),
    allow_unmanaged: bool = typer.Option(False, "--allow-unmanaged"),
) -> None:
    """Run high-level diagnostics on per-repo secrets setup."""
    paths = _resolve_paths(allow_unmanaged=allow_unmanaged)
    result = run_secrets_doctor(paths)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        raise typer.Exit(code=1 if result.errors else 0)

    typer.echo(f"Secrets doctor for: {result.slug}")
    typer.echo("")

    def _report(label: str, ok: bool) -> None:
        mark = "✓" if ok else "✗"
        typer.echo(f"  {mark} {label}")

    _report("Secrets directory exists", result.secrets_dir_exists)
    _report("Dotenv file exists", result.dotenv_exists)
    _report("Dotenv has key values", result.dotenv_has_values)
    _report("devenv.local.yaml exists", result.local_yaml_exists)
    _report("devenv.local.yaml provider valid", result.local_yaml_provider_valid)
    _report("Provider file outside repo", result.provider_file_outside_repo)
    _report("Provider file not git-tracked", result.provider_file_git_ignored)
    _report("secretspec.toml exists", result.spec_toml_exists)
    _report("secretspec.toml has required keys", result.spec_toml_has_required_keys)
    _report("Required keys present in provider", result.required_keys_present_in_provider)
    _report("pi on PATH", result.pi_wrapper_on_path)
    _report("State files clean", result.state_files_clean)

    if result.pi_wrapper_vs_node_modules and "node_modules" in result.pi_wrapper_vs_node_modules:
        typer.echo(f"  ⚠  pi resolves to: {result.pi_wrapper_vs_node_modules}")

    typer.echo("")
    for error in result.errors:
        typer.echo(f"  error: {error}")
    for warning in result.warnings:
        typer.echo(f"  warning: {warning}")

    raise typer.Exit(code=1 if result.errors else 0)


def main() -> None:
    app()
