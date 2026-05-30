# P0 Refactoring Guide

**Audience:** Developer implementing the P0 release-blocking changes for mypi-agent.
**Prerequisite reading:** `MYPI_SIMPLIFIED_SPEC_REVIEW.md` (same directory)
**Spec location:** `.scratch/specs/allium/`

This guide walks through every P0 change in implementation order. Each step includes the exact file, the current code, what to change, and how to verify. Complete them in order — later steps depend on earlier ones.

---

## Table of Contents

1. [P0.1 — Direct Pi Exposure](#p01--direct-pi-exposure)
2. [P0.2 — Pi Passthrough Flags](#p02--pi-passthrough-flags)
3. [P0.3 — Bootstrap Correctness](#p03--bootstrap-correctness)
4. [P0.4 — Pinned Version by Default](#p04--pinned-version-by-default)
5. [P0.5 — Settings Takeover Safety](#p05--settings-takeover-safety)
6. [P0.6 — Deepened needs-sync](#p06--deepened-needs-sync)
7. [P0.7 — Hermetic Test npm](#p07--hermetic-test-npm)
8. [Test Updates Summary](#test-updates-summary)

---

## P0.1 — Direct Pi Exposure

**Spec:** `core.allium:32-35`, `environment.allium:139-143`, `module.allium:75-78`
**Goal:** The upstream `pi` binary lives at `node_modules/.bin/pi` and is exposed on PATH. No `bin/pi-agent` wrapper is generated.

### Step 1.1: Fix `pi_executable_path` in `models.py`

**File:** `src/mypi_agent/models.py`, line 84-85

**Current:**
```python
@property
def pi_executable_path(self) -> Path:
    return self.agent_root / "bin" / "pi-agent"
```

**Change to:**
```python
@property
def pi_executable_path(self) -> Path:
    return self.agent_root / "node_modules" / ".bin" / "pi"
```

**Why:** The spec entity `PiExecutable` (core.allium:27-35) states the pi executable path points to upstream `node_modules/.bin/pi`, not a generated wrapper.

### Step 1.2: Delete launcher generation in `sync.py`

**File:** `src/mypi_agent/sync.py`, lines 349-357

**Current (inside `_apply_sync_plan`):**
```python
launcher = paths.agent_root / "bin" / "pi-agent"
launcher.parent.mkdir(parents=True, exist_ok=True)
if not launcher.exists():
    created.append(launcher)
launcher.write_text(
    "#!/usr/bin/env sh\nset -eu\nexec \"$(dirname \"$0\")/../node_modules/.bin/pi\" \"$@\"\n",
    encoding="utf-8",
)
launcher.chmod(0o755)
```

**Action:** Delete these 9 lines entirely. Do not replace them with anything.

**Why:** Spec rule `SyncInstallPi` (sync.allium:146-161) explicitly says "Do NOT generate a wrapper at bin/pi-agent." The upstream binary is used directly.

### Step 1.3: Add `node_modules/.bin` to PATH in `pi-agent.nix`

**File:** `modules/pi-agent.nix`, lines 105-112

**Current `config` block:**
```nix
config = lib.mkIf cfg.enable {
    packages = [ mypiBin cfg.nodePackage ] ++ lib.optional cfg.exposePiAgentShim piAgentBin;

    enterShell = lib.mkAfter ''
      ${npmEnvCmd}
      ${bootstrapCmd}
    '';
  };
```

**Change `enterShell` to add the node_modules/.bin directory to PATH:**
```nix
config = lib.mkIf cfg.enable {
    packages = [ mypiBin cfg.nodePackage ];

    enterShell = lib.mkAfter ''
      ${npmEnvCmd}
      export MYPI_AGENT_ROOT=${cfgRootEscaped}
      export PATH="''${DEVENV_ROOT:-$PWD}/$MYPI_AGENT_ROOT/node_modules/.bin:$PATH"
      ${bootstrapCmd}
    '';
  };
```

Note: `MYPI_AGENT_ROOT` is already set inside `npmEnvCmd` (line 22 of the `mypiBin` script), but it needs to also be set in the `enterShell` block so that the PATH addition works. The `npmEnvCmd` block already sets these env vars for the shell scope.

### Step 1.4: Remove `piAgentBin` and `exposePiAgentShim`

**File:** `modules/pi-agent.nix`

1. Delete lines 25-35 (the `piAgentBin` script definition):
```nix
  piAgentBin = pkgs.writeShellScriptBin "pi-agent" ''
    set -euo pipefail
    root_rel=${cfgRootEscaped}
    project_root="''${DEVENV_ROOT:-$PWD}"
    launcher="$project_root/$root_rel/bin/pi-agent"
    if [ ! -x "$launcher" ]; then
      echo "pi-agent is not installed yet; run: mypi sync" >&2
      exit 1
    fi
    exec "$launcher" "$@"
  '';
```

2. Delete lines 92-96 (the `exposePiAgentShim` option declaration):
```nix
    exposePiAgentShim = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Expose a compatibility pi-agent command.";
    };
```

3. In the `packages` list (line 106), remove the `piAgentBin` reference:
```nix
    # Before:
    packages = [ mypiBin cfg.nodePackage ] ++ lib.optional cfg.exposePiAgentShim piAgentBin;
    # After:
    packages = [ mypiBin cfg.nodePackage ];
```

### Step 1.5: Rename `pi_agent_installed` → `pi_installed` in `sync.py`

**File:** `src/mypi_agent/sync.py`

This is a field rename across two models and the build function. Change every occurrence:

- `SyncResult` (line 41): `pi_agent_installed: bool` → `pi_installed: bool`
- `SyncPlan` dataclass (line 64): `pi_agent_installed: bool` → `pi_installed: bool`
- `_build_sync_plan` (line 241): `pi_agent_installed = False` → `pi_installed = False`
- `_build_sync_plan` (line 260): `pi_agent_installed = True` → `pi_installed = True`
- `_build_sync_plan` return (line 332): `pi_agent_installed=pi_agent_installed` → `pi_installed=pi_installed`
- `run_sync` return (line 411): `pi_agent_installed=plan.pi_agent_installed` → `pi_installed=plan.pi_installed`

### Step 1.6: Update doctor error codes in `doctor.py`

**File:** `src/mypi_agent/doctor.py`

Rename three error codes (the spec uses `pi_*` not `pi_agent_*`):

| Current (line) | New |
|---|---|
| `"missing_pi_agent_executable"` (lines 109-110) | `"missing_pi_executable"` |
| `"pi_agent_executable_not_executable"` (lines 112-113) | `"pi_executable_not_executable"` |
| `"pi_agent_version_check_failed"` (lines 122-123) | `"pi_version_check_failed"` |

Change both the `errors.append(...)` and `diagnostics.append(...)` calls for each.

### Verification

After completing all P0.1 steps:

```bash
# Run existing tests — many will fail due to path changes (expected)
python -m pytest tests/ -x 2>&1 | head -30

# Check that pi_executable_path returns the new path
python -c "from mypi_agent.models import Paths; p = Paths(project_root=__import__('pathlib').Path('/tmp/test')); print(p.pi_executable_path)"
# Expected: /tmp/test/.agents/pi/node_modules/.bin/pi

# Check that sync.py no longer contains 'bin/pi-agent'
grep -n 'bin/pi-agent' src/mypi_agent/sync.py
# Expected: no output
```

---

## P0.2 — Pi Passthrough Flags

**Spec:** `surfaces.allium:62-74` (rule `PiLaunchesPi`)
**Goal:** `mypi pi` and `mypi agent` forward ALL upstream flags including `--version`, `-p`, `--mode`.

### Step 2.1: Rewrite `agent_command` in `cli.py`

**File:** `src/mypi_agent/cli.py`, lines 76-88

**Current:**
```python
@app.command("agent")
def agent_command(args: list[str] = typer.Argument(None)) -> None:
    paths = _resolve_paths()
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
```

**Change to:**
```python
@app.command(
    "agent",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def agent_command(ctx: typer.Context) -> None:
    paths = _resolve_paths()
    require_settings_shim_actor("AgentCommandSurface", build_settings_shim_actor(paths))
    pi_executable = paths.pi_executable_path
    if not pi_executable.exists() or not os.access(pi_executable, os.X_OK):
        typer.echo("error: Pi is not installed. Run: mypi sync")
        raise typer.Exit(code=1)
    result = subprocess.run(
        [str(pi_executable), *ctx.args],
        check=False,
    )
    raise typer.Exit(code=result.returncode)
```

### Step 2.2: Rewrite `pi_command` in `cli.py`

**File:** `src/mypi_agent/cli.py`, lines 91-93

**Current:**
```python
@app.command("pi")
def pi_command(args: list[str] = typer.Argument(None)) -> None:
    agent_command(args=args)
```

**Change to:**
```python
@app.command(
    "pi",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def pi_command(ctx: typer.Context) -> None:
    paths = _resolve_paths()
    require_settings_shim_actor("PiCommandSurface", build_settings_shim_actor(paths))
    pi_executable = paths.pi_executable_path
    if not pi_executable.exists() or not os.access(pi_executable, os.X_OK):
        typer.echo("error: Pi is not installed. Run: mypi sync")
        raise typer.Exit(code=1)
    result = subprocess.run(
        [str(pi_executable), *ctx.args],
        check=False,
    )
    raise typer.Exit(code=result.returncode)
```

**Why duplicate instead of delegating?** `pi_command` previously called `agent_command(args=args)`, but with `ctx: typer.Context` signatures, context objects are created per-command. Each needs its own handler. Alternatively, extract a shared `_run_pi(args: list[str], paths: Paths)` helper:

```python
def _run_pi(paths: Paths, args: list[str]) -> None:
    pi_executable = paths.pi_executable_path
    if not pi_executable.exists() or not os.access(pi_executable, os.X_OK):
        typer.echo("error: Pi is not installed. Run: mypi sync")
        raise typer.Exit(code=1)
    result = subprocess.run(
        [str(pi_executable), *args],
        check=False,
    )
    raise typer.Exit(code=result.returncode)


@app.command(
    "agent",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def agent_command(ctx: typer.Context) -> None:
    paths = _resolve_paths()
    require_settings_shim_actor("AgentCommandSurface", build_settings_shim_actor(paths))
    _run_pi(paths, ctx.args)


@app.command(
    "pi",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def pi_command(ctx: typer.Context) -> None:
    paths = _resolve_paths()
    require_settings_shim_actor("PiCommandSurface", build_settings_shim_actor(paths))
    _run_pi(paths, ctx.args)
```

### Verification

```bash
# After creating a fake pi binary:
mkdir -p /tmp/test-pi/.agents/pi/node_modules/.bin
echo '#!/bin/sh' > /tmp/test-pi/.agents/pi/node_modules/.bin/pi
echo 'echo "args: $@"' >> /tmp/test-pi/.agents/pi/node_modules/.bin/pi
chmod +x /tmp/test-pi/.agents/pi/node_modules/.bin/pi

# Test flag forwarding:
MYPI_PROJECT_ROOT=/tmp/test-pi MYPI_ALLOW_UNMANAGED=1 mypi pi --version
# Should print: args: --version

MYPI_PROJECT_ROOT=/tmp/test-pi MYPI_ALLOW_UNMANAGED=1 mypi pi -p "do something" --mode code
# Should print: args: -p do something --mode code
```

---

## P0.3 — Bootstrap Correctness

**Spec:** `core.allium:148-159` (invariant `BootstrapCompletedImpliesPiInstalled`), `sync.allium:165-184` (rule `SyncVerifyPiInstalled`)
**Goal:** Bootstrap status is only `completed` when the pi binary exists and is executable. Failed installs write `status: failed`.

### Step 3.1: Add `_pi_installed()` verifier in `sync.py`

**File:** `src/mypi_agent/sync.py`

Add this function after `_sha256_json` (around line 118):

```python
def _pi_installed(paths: Paths) -> bool:
    """Check that the upstream pi binary exists and is executable."""
    pi_path = paths.pi_executable_path
    return pi_path.exists() and os.access(pi_path, os.X_OK)
```

### Step 3.2: Change bootstrap state writes in `_build_sync_plan`

**File:** `src/mypi_agent/sync.py`, lines 304-311

**Current (inside `file_payloads` dict):**
```python
paths.bootstrap_state_path: {"status": "completed", "trigger": trigger, "config_hash": _config_hash(paths)},
```

This unconditionally writes `"status": "completed"`. **Do not change this line yet** — we will change it in step 3.3 where the actual verification happens.

### Step 3.3: Add post-install verification in `run_sync`

**File:** `src/mypi_agent/sync.py`, lines 382-420

**Current `run_sync`:**
```python
def run_sync(
    paths: Paths,
    explicit: bool,
    repair_shim: bool,
    trigger: str = "manual",
    diff_requested: bool = False,
    upgrade_target: str = "all",
) -> SyncResult:
    plan = _build_sync_plan(paths, repair_shim=repair_shim, trigger=trigger, diff_requested=diff_requested)
    created: list[Path] = []
    write_actions: list[WriteAction] = []
    if not diff_requested:
        created, write_actions = _apply_sync_plan(paths, plan)

    hash_inputs_changed = plan.bootstrap_performed or plan.shim_updated or plan.manifest_healed
    existing_files_overwritten = any(a.existed_before and a.content_changed for a in write_actions)
    return SyncResult(
        ...
        completed=True,
        ...
        pi_agent_installed=plan.pi_agent_installed,
        ...
    )
```

**Change to:**
```python
def run_sync(
    paths: Paths,
    explicit: bool,
    repair_shim: bool,
    trigger: str = "manual",
    diff_requested: bool = False,
    upgrade_target: str = "all",
) -> SyncResult:
    plan = _build_sync_plan(paths, repair_shim=repair_shim, trigger=trigger, diff_requested=diff_requested)
    created: list[Path] = []
    write_actions: list[WriteAction] = []
    if not diff_requested:
        created, write_actions = _apply_sync_plan(paths, plan)

        # P0.3: Verify pi binary after install, write correct bootstrap state
        pi_verified = _pi_installed(paths)
        bootstrap_state: dict[str, object] = {
            "schema_version": 1,
            "trigger": trigger,
            "config_hash": _config_hash(paths),
            "package_name": os.environ.get("MYPI_PI_PACKAGE_NAME", "@earendil-works/pi-coding-agent"),
        }
        if pi_verified:
            bootstrap_state["status"] = "completed"
            bootstrap_state["pi_installed"] = True
            bootstrap_state["pi_executable"] = str(
                paths.pi_executable_path.relative_to(paths.project_root)
            )
            bootstrap_state["last_error"] = None
        else:
            bootstrap_state["status"] = "failed"
            bootstrap_state["pi_installed"] = False
            bootstrap_state["last_error"] = "pi_install_failed"

        # Overwrite the bootstrap state file with the verified state
        atomic_write_json(paths.bootstrap_state_path, bootstrap_state)

    hash_inputs_changed = plan.bootstrap_performed or plan.shim_updated or plan.manifest_healed
    existing_files_overwritten = any(a.existed_before and a.content_changed for a in write_actions)
    pi_verified_final = _pi_installed(paths) if not diff_requested else False
    return SyncResult(
        created=created,
        warnings=plan.warnings,
        explicit=explicit,
        repair_shim=repair_shim,
        completed=True,
        existing_files_overwritten=existing_files_overwritten,
        advisory_shown=hash_inputs_changed,
        upgrade_requires_explicit_sync=True,
        bootstrap_performed=plan.bootstrap_performed,
        manifest_healed=plan.manifest_healed,
        shim_updated=plan.shim_updated,
        trigger=trigger,
        pi_installed=pi_verified_final,
        hash_inputs_changed=hash_inputs_changed,
        diff_requested=diff_requested,
        upgrade_target=upgrade_target,
        would_create_count=plan.would_create_count,
        would_upgrade_count=plan.would_upgrade_count,
        preserved_locally_modified_count=plan.preserved_locally_modified_count,
        primitive_file_classifications=plan.primitive_file_classifications,
        write_actions=write_actions,
    )
```

### Step 3.4: Remove premature bootstrap state from `_build_sync_plan`

**File:** `src/mypi_agent/sync.py`, line 307

Remove the bootstrap state entry from `file_payloads` since it's now written post-verification in `run_sync`:

```python
# Delete this line from file_payloads:
paths.bootstrap_state_path: {"status": "completed", "trigger": trigger, "config_hash": _config_hash(paths)},
```

The bootstrap state file is now written in `run_sync` after verification (step 3.3), so `_build_sync_plan` should not include it in `file_payloads`.

### Verification

```bash
# Test 1: Sync without npm should write status: failed
python -c "
import json, os
os.environ['MYPI_ALLOW_UNMANAGED'] = '1'
from pathlib import Path
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync
p = Paths(project_root=Path('/tmp/p0test'))
r = run_sync(p, explicit=True, repair_shim=False)
bs = json.loads(p.bootstrap_state_path.read_text())
print('pi_installed:', r.pi_installed)
print('bootstrap status:', bs['status'])
assert bs['status'] == 'failed'
assert r.pi_installed is False
print('PASS: failed install correctly recorded')
"

# Test 2: Sync with fake npm that creates pi binary should write status: completed
# (Use the existing fake npm test pattern from test_sync.py)
```

---

## P0.4 — Pinned Version by Default

**Spec:** `packages.allium:29-34`, `packages.allium:62-74`, `environment.allium:59`
**Goal:** When `piPackageVersion` is null and `allowFloatingPiVersion` is false (the default), sync errors out instead of silently installing latest.

### Step 4.1: Add `allowFloatingPiVersion` option to `pi-agent.nix`

**File:** `modules/pi-agent.nix`

Add this option inside `options.piAgent` (after the `npmInstallFlags` option, around line 91):

```nix
    allowFloatingPiVersion = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Allow floating (unpinned) Pi package version. Set to true to use latest from npm.";
    };
```

### Step 4.2: Export `MYPI_ALLOW_FLOATING_PI_VERSION` in `pi-agent.nix`

**File:** `modules/pi-agent.nix`

Add this line to the `npmEnvCmd` block (around line 48, after the `MYPI_NPM_INSTALL_FLAGS` export):

```nix
    export MYPI_ALLOW_FLOATING_PI_VERSION=${lib.boolToString cfg.allowFloatingPiVersion}
```

Also add the same export to the `mypiBin` script (add before the `exec` line around line 23):

```nix
    export MYPI_ALLOW_FLOATING_PI_VERSION=${lib.boolToString cfg.allowFloatingPiVersion}
```

### Step 4.3: Add version gate in `_build_sync_plan` in `sync.py`

**File:** `src/mypi_agent/sync.py`, inside `_build_sync_plan`

**Current (lines 243-252):**
```python
    if not diff_requested:
        npm = shutil.which("npm")
        pi_package_version = os.environ.get("MYPI_PI_PACKAGE_VERSION", "").strip() or None
        npm_install_flags = _load_npm_install_flags()
        if npm is None:
            warnings.append("pi_agent_install_skipped_no_npm")
        else:
            install_target = pi_package_name if pi_package_version is None else f"{pi_package_name}@{pi_package_version}"
            if pi_package_version is None:
                warnings.append("pi_package_version_unset_for_pinned_npm")
```

**Change to:**
```python
    if not diff_requested:
        npm = shutil.which("npm")
        pi_package_version = os.environ.get("MYPI_PI_PACKAGE_VERSION", "").strip() or None
        allow_floating = os.environ.get("MYPI_ALLOW_FLOATING_PI_VERSION", "false").lower() in {"true", "1", "yes"}
        npm_install_flags = _load_npm_install_flags()
        if npm is None:
            warnings.append("pi_install_skipped_no_npm")
        elif pi_package_version is None and not allow_floating:
            # P0.4: Error when version is null and floating not explicitly allowed
            raise RuntimeError(
                "error: piAgent.piPackageVersion must be set for reproducible installs.\n"
                "Set piAgent.allowFloatingPiVersion = true to use latest."
            )
        else:
            install_target = pi_package_name if pi_package_version is None else f"{pi_package_name}@{pi_package_version}"
            if pi_package_version is None:
                warnings.append("pi_package_version_floating")
```

### Step 4.4: Handle the error in `cli.py`

**File:** `src/mypi_agent/cli.py`, inside `sync_command`

The `RuntimeError` from step 4.3 will propagate up. Wrap the `run_sync` call:

**Current (lines 37-44):**
```python
    result = run_sync(
        paths,
        explicit=True,
        repair_shim=repair_shim,
        trigger=trigger,
        diff_requested=diff_mode,
        upgrade_target="all",
    )
```

**Change to:**
```python
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
```

### Step 4.5: Update warning code name

Also in `_build_sync_plan`, rename the existing npm-missing warning for consistency:

- `"pi_agent_install_skipped_no_npm"` → `"pi_install_skipped_no_npm"`
- `"pi_agent_install_failed"` → `"pi_install_failed"` (line 267)

### Verification

```bash
# Without version set and without floating opt-in, sync should error:
MYPI_ALLOW_UNMANAGED=1 mypi sync 2>&1
# Expected: error: piAgent.piPackageVersion must be set for reproducible installs.

# With floating opt-in, sync should proceed (with warning):
MYPI_ALLOW_FLOATING_PI_VERSION=true MYPI_ALLOW_UNMANAGED=1 mypi sync 2>&1
# Expected: proceeds (may warn about floating version)

# With version pinned, sync should proceed normally:
MYPI_PI_PACKAGE_VERSION=1.2.3 MYPI_ALLOW_UNMANAGED=1 mypi sync 2>&1
# Expected: proceeds without version warnings
```

**Important note for tests:** Most existing tests don't set `MYPI_PI_PACKAGE_VERSION` or `MYPI_ALLOW_FLOATING_PI_VERSION`. After this change, any test that calls `run_sync` without diff mode and with npm available will hit the version gate. Fix by either:
- Setting `MYPI_ALLOW_FLOATING_PI_VERSION=true` in `conftest.py` (easiest for existing tests)
- Or setting `MYPI_PI_PACKAGE_VERSION=0.0.0-test` in `conftest.py`

Recommended: add to `conftest.py`:
```python
@pytest.fixture(autouse=True)
def _allow_floating_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_FLOATING_PI_VERSION", "true")
```

---

## P0.5 — Settings Takeover Safety

**Spec:** `sync.allium:98-107` (rule `SyncRejectsUserOwnedSettings`), `sync.allium:258-266` (invariants)
**Goal:** When `.pi/settings.json` exists but is user-owned (no MYPI marker) or invalid JSON, sync refuses to proceed unless `--repair-shim` is passed.

### Step 5.1: Add settings classification check to `run_sync`

**File:** `src/mypi_agent/sync.py`, inside `run_sync`

Add this check **before** calling `_build_sync_plan`. Insert after the function signature and before the `plan = ...` line:

```python
def run_sync(
    paths: Paths,
    explicit: bool,
    repair_shim: bool,
    trigger: str = "manual",
    diff_requested: bool = False,
    upgrade_target: str = "all",
) -> SyncResult:
    # P0.5: Check settings classification before proceeding
    if not diff_requested and not repair_shim and paths.settings_path.exists():
        classification = _classify_file(
            paths.settings_path,
            _settings_payload(
                paths.agent_root.relative_to(paths.project_root).as_posix()
            ),
            MANAGED_SETTINGS_KEYS,
        )
        if classification in ("user_owned", "invalid_json"):
            raise RuntimeError(
                "error: .pi/settings.json already exists and is not MYPI-managed.\n"
                "Run `mypi sync --repair-shim` to adopt/repair the settings shim."
            )

    plan = _build_sync_plan(...)  # rest unchanged
```

**Why this location?** The spec rule `SyncRejectsUserOwnedSettings` fires when `repair_shim: false` and the settings classification is `user_owned` or `invalid_json`. It emits a `SyncError` — we implement that as a `RuntimeError` caught by the CLI.

### Step 5.2: Verify `--repair-shim` bypasses the gate

The `repair_shim` parameter is already checked in the guard (`not repair_shim`), so `--repair-shim` correctly bypasses it. No additional code needed.

### Step 5.3: Verify diff mode bypasses the gate

The guard also checks `not diff_requested`, so `--diff` correctly bypasses it. No additional code needed.

### Verification

```bash
# Create user-owned settings (no MYPI marker):
mkdir -p /tmp/p05test/.pi
echo '{"customKey": "value"}' > /tmp/p05test/.pi/settings.json

# Sync should fail:
MYPI_ALLOW_UNMANAGED=1 MYPI_PROJECT_ROOT=/tmp/p05test MYPI_ALLOW_FLOATING_PI_VERSION=true mypi sync
# Expected: error: .pi/settings.json already exists and is not MYPI-managed.

# Repair should succeed:
MYPI_ALLOW_UNMANAGED=1 MYPI_PROJECT_ROOT=/tmp/p05test MYPI_ALLOW_FLOATING_PI_VERSION=true mypi sync --repair-shim
# Expected: success

# Verify user key preserved after repair:
cat /tmp/p05test/.pi/settings.json | python -m json.tool
# Expected: contains "customKey": "value" AND "x-mypi-agent" marker

# Diff mode should succeed even with user-owned settings:
mkdir -p /tmp/p05test2/.pi
echo '{"customKey": "value"}' > /tmp/p05test2/.pi/settings.json
MYPI_ALLOW_UNMANAGED=1 MYPI_PROJECT_ROOT=/tmp/p05test2 MYPI_ALLOW_FLOATING_PI_VERSION=true mypi sync --diff
# Expected: success (read-only, no mutation)
```

---

## P0.6 — Deepened needs-sync

**Spec:** `surfaces.allium:129-152` (rule `NeedsSyncChecksRuntimeState`)
**Goal:** `needs_sync()` checks actual runtime state — pi binary exists, is executable, bootstrap completed — not just config hash.

### Step 6.1: Expand `needs_sync()` in `sync.py`

**File:** `src/mypi_agent/sync.py`, lines 213-219

**Current:**
```python
def needs_sync(paths: Paths) -> bool:
    if not paths.agent_root.exists() or not paths.settings_path.exists() or not paths.manifest_path.exists():
        return True
    bootstrap = _read_json_or_none(paths.bootstrap_state_path)
    if not isinstance(bootstrap, dict):
        return True
    return bootstrap.get("config_hash") != _config_hash(paths)
```

**Change to:**
```python
def needs_sync(paths: Paths) -> bool:
    # Structural checks
    if not paths.agent_root.exists():
        return True
    if not paths.settings_path.exists():
        return True
    if not paths.manifest_path.exists():
        return True

    # P0.6: Pi binary must exist and be executable
    if not _pi_installed(paths):
        return True

    # P0.6: Bootstrap must be completed
    bootstrap = _read_json_or_none(paths.bootstrap_state_path)
    if not isinstance(bootstrap, dict):
        return True
    if bootstrap.get("status") != "completed":
        return True

    # P0.6: Resource directories must exist
    for resource_dir in RESOURCE_DIRS:
        if not (paths.agent_root / resource_dir).exists():
            return True

    # Config hash drift
    return bootstrap.get("config_hash") != _config_hash(paths)
```

### Verification

```bash
# Scenario 1: Missing pi binary triggers needs-sync
python -c "
import os
os.environ['MYPI_ALLOW_UNMANAGED'] = '1'
os.environ['MYPI_ALLOW_FLOATING_PI_VERSION'] = 'true'
from pathlib import Path
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync, needs_sync
p = Paths(project_root=Path('/tmp/p06test'))
run_sync(p, explicit=True, repair_shim=False)
# Pi binary won't exist (no real npm), so needs_sync should be True
assert needs_sync(p) is True
print('PASS: missing pi binary triggers needs-sync')
"

# Scenario 2: After creating fake pi binary, needs-sync should be False
python -c "
import os
os.environ['MYPI_ALLOW_UNMANAGED'] = '1'
os.environ['MYPI_ALLOW_FLOATING_PI_VERSION'] = 'true'
from pathlib import Path
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync, needs_sync
p = Paths(project_root=Path('/tmp/p06test2'))
run_sync(p, explicit=True, repair_shim=False)
# Create fake pi binary
pi = p.pi_executable_path
pi.parent.mkdir(parents=True, exist_ok=True)
pi.write_text('#!/bin/sh\necho pi\n')
pi.chmod(0o755)
# Now manually fix bootstrap state to completed
import json
from mypi_agent.sync import atomic_write_json, _config_hash
atomic_write_json(p.bootstrap_state_path, {
    'status': 'completed', 'config_hash': _config_hash(p),
    'pi_installed': True, 'schema_version': 1
})
assert needs_sync(p) is False
print('PASS: all checks pass, needs-sync is False')
"
```

---

## P0.7 — Hermetic Test npm

**Spec:** General test safety — tests must not invoke real npm.
**Goal:** The test suite uses a fake npm by default. No test path calls real npm install.

### Step 7.1: Create a shared fake npm fixture in `conftest.py`

**File:** `tests/conftest.py`

**Current:**
```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _allow_unmanaged_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_UNMANAGED", "1")
    monkeypatch.delenv("MYPI_PROJECT_ROOT", raising=False)
```

**Change to:**
```python
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _allow_unmanaged_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_UNMANAGED", "1")
    monkeypatch.delenv("MYPI_PROJECT_ROOT", raising=False)


@pytest.fixture(autouse=True)
def _allow_floating_for_tests(monkeypatch):
    """P0.4: Allow floating version in tests to avoid version gate errors."""
    monkeypatch.setenv("MYPI_ALLOW_FLOATING_PI_VERSION", "true")


@pytest.fixture()
def fake_npm(tmp_path, monkeypatch):
    """Provide a fake npm that creates a pi binary under node_modules/.bin/pi.

    Usage:
        def test_something(tmp_path, fake_npm):
            paths = Paths(project_root=tmp_path)
            result = run_sync(paths, explicit=True, repair_shim=False)
            assert result.pi_installed is True
    """
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    npm_script = fake_bin / "npm"
    npm_script.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "prefix=\n"
        "pkg_name=\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --prefix) shift; prefix=\"$1\" ;;\n"
        "    @*) pkg_name=\"$1\" ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "if [ -z \"$prefix\" ]; then exit 1; fi\n"
        "# Extract package name (strip @version suffix)\n"
        "base_name=$(echo \"$pkg_name\" | sed 's/@[^@/]*$//')\n"
        "if [ -z \"$base_name\" ]; then base_name=\"@earendil-works/pi-coding-agent\"; fi\n"
        "mkdir -p \"$prefix/node_modules/.bin\"\n"
        "mkdir -p \"$prefix/node_modules/$base_name\"\n"
        "cat > \"$prefix/node_modules/.bin/pi\" <<'PIEOF'\n"
        "#!/usr/bin/env sh\n"
        "echo pi 0.0.1-fake\n"
        "PIEOF\n"
        "chmod +x \"$prefix/node_modules/.bin/pi\"\n"
        "cat > \"$prefix/node_modules/$base_name/package.json\" <<'PKGEOF'\n"
        "{\"name\": \"@earendil-works/pi-coding-agent\", \"version\": \"0.0.1-fake\"}\n"
        "PKGEOF\n",
        encoding="utf-8",
    )
    npm_script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ.get('PATH', '')}")
    return fake_bin


@pytest.fixture()
def fake_npm_failing(tmp_path, monkeypatch):
    """Provide a fake npm that always fails (exit 1)."""
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    npm_script = fake_bin / "npm"
    npm_script.write_text(
        "#!/usr/bin/env sh\nexit 1\n",
        encoding="utf-8",
    )
    npm_script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ.get('PATH', '')}")
    return fake_bin
```

### Step 7.2: Block real npm in all tests

Add an autouse fixture that prevents real npm from being called. This is the safest approach:

Add to `conftest.py`:

```python
@pytest.fixture(autouse=True)
def _block_real_npm(monkeypatch):
    """Prevent tests from accidentally calling real npm.

    Tests that need npm must use the fake_npm or fake_npm_failing fixture,
    which prepend a fake npm to PATH. This fixture removes npm from PATH
    so that shutil.which("npm") returns None unless a fake is provided.
    """
    original_which = __import__("shutil").which

    def _guarded_which(name: str, *args, **kwargs):
        if name == "npm":
            # Only allow npm if it's in a fake-bin directory (set up by fixtures)
            result = original_which(name, *args, **kwargs)
            if result and "fake-bin" in str(result):
                return result
            return None
        return original_which(name, *args, **kwargs)

    monkeypatch.setattr("shutil.which", _guarded_which)
```

### Step 7.3: Update `test_sync_installs_pi_agent_with_fake_npm` to use the shared fixture

**File:** `tests/integration/test_sync.py`, test at line 156

**Current test** creates its own fake npm inline. Refactor to use the shared `fake_npm` fixture:

```python
def test_sync_installs_pi_with_fake_npm(tmp_path, fake_npm):
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False)
    assert result.pi_installed is True
    assert paths.pi_executable_path.exists()
    registry = json.loads(paths.primitive_registry_state_path.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1
    assert "core" in registry["groups"]
    assert len(registry["installs"]) == 1
```

Note the rename: `test_sync_installs_pi_agent_with_fake_npm` → `test_sync_installs_pi_with_fake_npm` and `result.pi_agent_installed` → `result.pi_installed`.

### Verification

```bash
# Run all tests — none should call real npm
python -m pytest tests/ -v 2>&1 | grep -E "(PASS|FAIL|ERROR)"

# Verify the guard works: a test without fake_npm should see npm as missing
python -c "
import shutil
# Outside of test environment, this should still find npm normally
print('npm:', shutil.which('npm'))
"
```

---

## Test Updates Summary

After all P0 changes, the following existing tests need updates. This is a comprehensive list.

### Tests that reference `bin/pi-agent` path (P0.1)

| Test File | Test Name | Change |
|---|---|---|
| `test_sync.py` | `test_sync_installs_pi_agent_with_fake_npm` | Rename test, change `result.pi_agent_installed` → `result.pi_installed`, remove `launcher = paths.agent_root / "bin" / "pi-agent"` assertion, add `assert paths.pi_executable_path.exists()` |
| `test_cli.py` | `test_cli_doctor_success_after_sync` | Change pi executable path from `tmp_path / ".agents" / "pi" / "bin" / "pi-agent"` to `tmp_path / ".agents" / "pi" / "node_modules" / ".bin" / "pi"` |
| `test_cli.py` | `test_cli_doctor_json` | Same path change as above |
| `test_cli.py` | `test_cli_paths_outputs_required_fields` | Change assertion from `bin/pi-agent` to `node_modules/.bin/pi` |
| `test_cli.py` | `test_cli_paths_json_outputs_required_fields` | Same assertion change |
| `test_doctor.py` | `test_doctor_reports_missing_artifacts` | Change `"missing_pi_agent_executable"` → `"missing_pi_executable"` |
| `test_doctor.py` | `test_doctor_success_after_sync` | Change pi executable path to `node_modules/.bin/pi` |
| `test_doctor.py` | `test_doctor_reports_pi_agent_not_executable` | Change path + rename error code to `"pi_executable_not_executable"` |

### Tests affected by bootstrap correctness (P0.3)

| Test File | Test Name | Change |
|---|---|---|
| `test_sync.py` | `test_sync_sets_trigger_and_bootstrap_state` | Bootstrap state now includes `pi_installed`, `schema_version`, `last_error`. Assert `bootstrap["status"]` is `"failed"` (since no real npm → pi binary missing). Or use `fake_npm` fixture to get `"completed"`. |
| `test_sync.py` | `test_sync_contract_fields_exposed` | Change `result.pi_agent_installed` → `result.pi_installed` |

### Tests affected by version gate (P0.4)

Tests that call `run_sync` with npm available will hit the version gate. The autouse `_allow_floating_for_tests` fixture handles this.

| Test File | Test Name | Change |
|---|---|---|
| `test_sync.py` | `test_sync_pinned_package_uses_name_at_version` | Set `MYPI_ALLOW_FLOATING_PI_VERSION=false` explicitly in this test since it tests pinned behavior |

### Tests affected by settings safety (P0.5)

| Test File | Test Name | Change |
|---|---|---|
| `test_cli.py` | `test_cli_sync_repair_shim_rewrites_existing` | This test creates user-owned settings and runs sync with `--repair-shim`, so it should still pass. But verify it doesn't hit the gate. |
| `test_sync.py` | `test_repair_shim_rewrites_when_explicit` | Same — uses `repair_shim=True` so should pass the gate. |

### New tests to add

Add these new tests in `tests/integration/test_sync.py`:

```python
def test_sync_rejects_user_owned_settings_without_repair_shim(tmp_path):
    """P0.5: user-owned settings require --repair-shim."""
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text('{"customKey": "value"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="not MYPI-managed"):
        run_sync(paths, explicit=True, repair_shim=False)


def test_sync_rejects_invalid_json_settings_without_repair_shim(tmp_path):
    """P0.5: invalid JSON settings require --repair-shim."""
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text("{broken json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not MYPI-managed"):
        run_sync(paths, explicit=True, repair_shim=False)


def test_sync_accepts_user_owned_settings_with_repair_shim(tmp_path):
    """P0.5: --repair-shim allows adopting user-owned settings."""
    paths = Paths(project_root=tmp_path)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text('{"customKey": "value"}\n', encoding="utf-8")
    result = run_sync(paths, explicit=True, repair_shim=True)
    assert result.shim_updated is True
    settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    assert "x-mypi-agent" in settings
    assert settings["customKey"] == "value"  # user key preserved


def test_failed_npm_install_writes_bootstrap_failed(tmp_path, fake_npm_failing):
    """P0.3: failed npm install must not mark bootstrap as completed."""
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False)
    bootstrap = json.loads(paths.bootstrap_state_path.read_text(encoding="utf-8"))
    assert bootstrap["status"] == "failed"
    assert bootstrap["pi_installed"] is False
    assert result.pi_installed is False


def test_successful_npm_install_writes_bootstrap_completed(tmp_path, fake_npm):
    """P0.3: successful npm install marks bootstrap as completed."""
    paths = Paths(project_root=tmp_path)
    result = run_sync(paths, explicit=True, repair_shim=False)
    bootstrap = json.loads(paths.bootstrap_state_path.read_text(encoding="utf-8"))
    assert bootstrap["status"] == "completed"
    assert bootstrap["pi_installed"] is True
    assert result.pi_installed is True


def test_needs_sync_true_when_pi_binary_missing(tmp_path):
    """P0.6: needs_sync returns True when pi binary doesn't exist."""
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    assert needs_sync(paths) is True  # pi binary missing


def test_needs_sync_true_when_bootstrap_failed(tmp_path, fake_npm_failing):
    """P0.6: needs_sync returns True when bootstrap status is failed."""
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    assert needs_sync(paths) is True  # bootstrap failed


def test_needs_sync_false_when_fully_bootstrapped(tmp_path, fake_npm):
    """P0.6: needs_sync returns False when everything is in order."""
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    assert needs_sync(paths) is False


def test_pi_path_points_to_node_modules_bin_pi():
    """P0.1: pi_executable_path must point to node_modules/.bin/pi."""
    from pathlib import Path
    paths = Paths(project_root=Path("/tmp/test"))
    assert str(paths.pi_executable_path).endswith("node_modules/.bin/pi")
    assert "bin/pi-agent" not in str(paths.pi_executable_path)


def test_sync_does_not_generate_pi_agent_wrapper(tmp_path, fake_npm):
    """P0.1: sync must not create bin/pi-agent launcher."""
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)
    launcher = paths.agent_root / "bin" / "pi-agent"
    assert not launcher.exists()
```

Add required imports at the top of `test_sync.py`:
```python
import pytest
from mypi_agent.sync import needs_sync
```

### Order of implementation

1. Make all P0.1 changes first (path, sync, nix, doctor renames)
2. Make P0.2 changes (cli passthrough)
3. Make P0.3 changes (bootstrap correctness)
4. Make P0.4 changes (version gate)
5. Make P0.5 changes (settings safety)
6. Make P0.6 changes (needs-sync)
7. Make P0.7 changes (test fixtures)
8. Update all affected tests
9. Run full test suite: `python -m pytest tests/ -v`
10. Fix any remaining failures

### Final acceptance criteria

All of these must pass:

```bash
# Full test suite green
python -m pytest tests/ -v

# No references to bin/pi-agent in source (excluding test comments/docs)
grep -rn 'bin/pi-agent' src/

# Pi path is correct
python -c "from mypi_agent.models import Paths; from pathlib import Path; p = Paths(project_root=Path('/tmp/x')); assert 'node_modules/.bin/pi' in str(p.pi_executable_path)"

# No real npm in tests
grep -rn 'shutil.which.*npm' tests/ | grep -v conftest | grep -v fake
```
