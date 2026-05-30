# MYPI-AGENT Code Review

**Repository reviewed:** `mypi-agent_v003`  
**Review date:** 2026-05-29  
**Scope adjustment:** `dev/` is intentionally ignored in this review because it is development-only and, per project clarification, is gitignored in the real repository. Findings below focus on the public import surface, Nix/devenv module, Python CLI/runtime, tests, and repo-level contract files outside `dev/`.

---

## 1. Executive Summary

`mypi-agent_v003` has the right high-level shape for a reusable devenv bootstrap foundation. The public import surface is small, `allium-env` is not part of the public root import path, and the module exposes a `piAgent` option namespace that can be imported from a consumer `devenv.yaml`.

The major design correction is binary exposure. The repository should **not create or promote a MYPI-owned `pi-agent` launcher**. It should install the upstream Pi package and expose the upstream CLI binary directly. Current upstream Pi is distributed as the npm package `@earendil-works/pi-coding-agent`, and the CLI remains `pi` after the Earendil migration. The bootstrap foundation should therefore make `pi` available on `PATH` from the project-local npm install, while keeping `mypi` as the control-plane command for `sync`, `doctor`, `paths`, and other MYPI-specific operations.

Overall assessment: **promising but not release-ready**.

**Current fit against the intended goal:** 6.5 / 10  
**Fit after the recommended P0 fixes:** approximately 8 / 10  
**Fit after P0 + P1 hardening:** approximately 9 / 10

The repository succeeds at the import-shape level. It is weaker at runtime determinism, upstream CLI fidelity, shell-entry failure handling, and settings ownership safety.

---

## 2. External Facts Used During Review

These are the external assumptions that affect the code review:

1. Pi is currently distributed as an npm package:

   ```bash
   npm install -g --ignore-scripts @earendil-works/pi-coding-agent
   ```

   Source: <https://pi.dev/docs/latest/quickstart>

2. Pi moved to the `earendil-works/pi` repository and the `@earendil-works` npm scope. The migration note states that the CLI is still `pi`.

   Source: <https://pi.dev/news/2026/5/7/pi-has-a-new-home>

3. Pi project settings live at `.pi/settings.json`; project settings override global settings. Paths inside `.pi/settings.json` resolve relative to `.pi`.

   Source: <https://pi.dev/docs/latest/settings>

4. Pi supports an `npmCommand` setting, which is used for npm package lookup/install operations, including dependency installs inside git packages.

   Source: <https://pi.dev/docs/latest/settings>

5. Devenv `imports` can reference inputs, and imported configuration is merged into the consuming environment. The relevant consumer pattern is therefore:

   ```yaml
   inputs:
     mypi-agent:
       url: github:ORG/mypi-agent
       flake: false
   imports:
     - mypi-agent
   ```

   Source: <https://devenv.sh/guides/polyrepo/> and <https://devenv.sh/reference/yaml-options/>

---

## 3. Revised Design Decision: Expose Upstream `pi` Directly

### Current behavior

The current code installs the npm package into the project-local agent root, then generates this launcher:

```text
.agents/pi/bin/pi-agent
```

That launcher executes:

```sh
../node_modules/.bin/pi
```

The Nix module optionally exposes a separate `pi-agent` command when `piAgent.exposePiAgentShim = true`.

### Why this should change

The upstream CLI is `pi`, not `pi-agent`. Creating a MYPI-owned `pi-agent` launcher introduces avoidable semantic drift:

- it makes users think there is a distinct upstream `pi-agent` binary;
- it creates a second command path to document and test;
- it risks hiding upstream CLI behavior behind MYPI-specific indirection;
- it makes `doctor`, `paths`, and README language less accurate;
- it conflicts with the stated desire to install and expose the normal upstream Pi agent functionality.

### Recommended target behavior

The repository should expose two command surfaces:

```text
mypi  -> MYPI bootstrap/control plane
pi    -> upstream Pi CLI from the project-local npm install
```

`mypi` remains the MYPI command. It owns:

```text
mypi sync
mypi doctor
mypi paths
mypi needs-sync
```

`pi` should be the actual upstream CLI exposed from:

```text
.agents/pi/node_modules/.bin/pi
```

No generated `.agents/pi/bin/pi-agent` launcher should be required for the default path.

### Recommended Nix-level shape

The module should add the project-local npm bin directory to `PATH` during shell entry:

```nix
enterShell = lib.mkAfter ''
  ${npmEnvCmd}
  root_rel=${cfgRootEscaped}
  project_root="''${DEVENV_ROOT:-$PWD}"
  export PATH="$project_root/$root_rel/node_modules/.bin:$PATH"
  ${bootstrapCmd}
'';
```

This is direct enough: there is no MYPI wrapper binary for `pi`; the shell simply includes the upstream npm `.bin` directory.

The Python runtime should also resolve Pi to:

```python
paths.agent_root / "node_modules" / ".bin" / "pi"
```

not:

```python
paths.agent_root / "bin" / "pi-agent"
```

### Compatibility option

If a `pi-agent` compatibility command is kept, it should be explicitly treated as legacy and false by default:

```nix
piAgent.exposePiAgentCompatibilityShim = false;
```

But for the cleanest foundation, remove it until there is a real consumer need.

---

## 4. What the Repository Gets Right

### 4.1 Public import surface is clean

Root `devenv.nix` is minimal:

```nix
{ lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.enable = lib.mkDefault true;
}
```

This is the right public contract for a `devenv.yaml` input import. A consumer can import the repo as an input, and the root `devenv.nix` enables the module by default.

### 4.2 Development-only environment is not part of the public path

The public root import path does not import `dev/` or `allium-env`. Given the clarification that `dev/` is gitignored and should be ignored, the earlier concern about development artifacts in the zip is withdrawn as a primary finding.

### 4.3 Module options are headed in the right direction

The module provides useful configuration points:

```nix
piAgent.root
piAgent.nodePackage
piAgent.piPackageName
piAgent.piPackageVersion
piAgent.npmInstallFlags
piAgent.bootstrap.mode
piAgent.exposePiAgentShim
```

This is the right idea. The option namespace is small, discoverable, and specific to the bootstrap purpose.

### 4.4 Project-local install intent is correct

The module sets repo-local npm state:

```bash
NPM_CONFIG_PREFIX="$MYPI_PROJECT_ROOT/$root_rel/npm-global"
NPM_CONFIG_CACHE="$MYPI_PROJECT_ROOT/$root_rel/.npm-cache"
```

and `sync.py` installs Pi using:

```python
npm install --prefix <agent_root> ... @earendil-works/pi-coding-agent
```

This aligns with the goal of avoiding global npm mutation. It needs hardening, but the direction is correct.

### 4.5 Contract fixtures are valuable

The `tests/fixtures/devenv/` scenarios are a strong addition, especially:

```text
tests/fixtures/devenv/yaml-import-only
```

That fixture tests the actual desired consumer path:

```yaml
inputs:
  mypi-agent:
    url: path:__REPO_ROOT__
    flake: false
imports:
  - mypi-agent
```

Keep these fixtures. They should become part of the repository’s core acceptance suite.

---

## 5. P0 Release-Blocking Findings

These issues should be fixed before treating the repo as a usable bootstrap foundation.

---

### P0.1 Replace the generated `pi-agent` launcher with direct upstream `pi` exposure

**Files:**

- `src/mypi_agent/models.py`
- `src/mypi_agent/sync.py`
- `src/mypi_agent/doctor.py`
- `src/mypi_agent/cli.py`
- `modules/pi-agent.nix`
- `README.md`
- tests expecting `.agents/pi/bin/pi-agent`

**Current evidence:**

`models.py` defines:

```python
@property
def pi_executable_path(self) -> Path:
    return self.agent_root / "bin" / "pi-agent"
```

`sync.py` writes a launcher:

```python
launcher = paths.agent_root / "bin" / "pi-agent"
launcher.write_text(
    "#!/usr/bin/env sh\nset -eu\nexec \"$(dirname \"$0\")/../node_modules/.bin/pi\" \"$@\"\n",
    encoding="utf-8",
)
```

`modules/pi-agent.nix` defines a `pi-agent` shim package.

**Why this matters:**

The upstream CLI is `pi`. The bootstrap foundation should make upstream Pi available normally, not invent a separate default launcher name.

**Required fix:**

Change `Paths.pi_executable_path`:

```python
@property
def pi_executable_path(self) -> Path:
    return self.agent_root / "node_modules" / ".bin" / "pi"
```

Delete the launcher creation from `_apply_sync_plan()`.

In `modules/pi-agent.nix`, remove `piAgentBin` from the normal command surface and add the npm `.bin` directory to `PATH`:

```nix
enterShell = lib.mkAfter ''
  ${npmEnvCmd}
  root_rel=${cfgRootEscaped}
  project_root="''${DEVENV_ROOT:-$PWD}"
  export PATH="$project_root/$root_rel/node_modules/.bin:$PATH"
  ${bootstrapCmd}
'';
```

Update docs to say generated runtime install contains:

```text
.agents/pi/node_modules/.bin/pi
```

not:

```text
.agents/pi/bin/pi-agent
```

**Acceptance tests:**

```bash
devenv shell -- which pi
pi --version
mypi paths --json
mypi doctor
```

Expected:

- `which pi` resolves to the project-local `.agents/pi/node_modules/.bin/pi` path.
- `mypi doctor` checks that exact path.
- no default `.agents/pi/bin/pi-agent` launcher is generated.

---

### P0.2 `mypi agent` and `mypi pi` do not pass through upstream flags

**File:** `src/mypi_agent/cli.py`

**Current evidence:**

```python
@app.command("agent")
def agent_command(args: list[str] = typer.Argument(None)) -> None:
```

This does not allow unknown options. A command such as:

```bash
mypi agent --version
```

fails as a Typer option parsing error:

```text
No such option: --version
```

This also breaks important Pi commands such as:

```bash
mypi pi --mode rpc
mypi pi --mode json
mypi pi -p "Summarize this repo"
```

**Why this matters:**

Pi’s normal interface is flag-heavy. If `mypi pi` exists, it must behave as a real passthrough.

**Required fix:**

Use Click/Typer passthrough settings:

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
    result = subprocess.run([str(pi_executable), *ctx.args], check=False)
    raise typer.Exit(code=result.returncode)
```

Then either:

1. remove `mypi agent` to avoid redundant naming; or
2. keep `mypi agent` as a deprecated alias to `mypi pi` with the same passthrough behavior.

**Acceptance tests:**

```python
def test_mypi_pi_passes_unknown_options(...):
    result = runner.invoke(app, ["pi", "--version"])
    assert result.exit_code == 0
```

Also test:

```bash
mypi pi --mode rpc
mypi pi -p "hello"
```

with a fake `pi` binary that records argv.

---

### P0.3 Bootstrap can mark itself complete even when Pi was not installed

**File:** `src/mypi_agent/sync.py`

**Current evidence:**

If npm is missing:

```python
if npm is None:
    warnings.append("pi_agent_install_skipped_no_npm")
```

If npm install fails:

```python
else:
    warnings.append("pi_agent_install_failed")
```

But the state still writes:

```python
paths.bootstrap_state_path: {
    "status": "completed",
    "trigger": trigger,
    "config_hash": _config_hash(paths),
}
```

and `run_sync()` returns:

```python
completed=True
```

`needs_sync()` only checks whether the agent root, settings file, manifest, and config hash exist/match. It does not check whether Pi is actually installed or executable.

**Why this matters:**

A failed first shell bootstrap can create enough state to suppress later retries. The user then sees a broken shell with no self-healing path except manual diagnosis.

**Required fix:**

Do not mark bootstrap as completed unless the upstream `pi` binary exists and is executable.

Add a runtime install verifier:

```python
def _pi_installed(paths: Paths) -> bool:
    pi = paths.pi_executable_path
    return pi.exists() and os.access(pi, os.X_OK)
```

Use it in both `run_sync()` and `needs_sync()`:

```python
def needs_sync(paths: Paths) -> bool:
    if not paths.agent_root.exists() or not paths.settings_path.exists() or not paths.manifest_path.exists():
        return True
    if not _pi_installed(paths):
        return True
    bootstrap = _read_json_or_none(paths.bootstrap_state_path)
    if not isinstance(bootstrap, dict):
        return True
    if bootstrap.get("status") != "completed":
        return True
    return bootstrap.get("config_hash") != _config_hash(paths)
```

Write explicit status:

```json
{
  "status": "completed",
  "pi_installed": true,
  "trigger": "shell",
  "config_hash": "...",
  "last_error": null
}
```

For failure:

```json
{
  "status": "failed",
  "pi_installed": false,
  "trigger": "shell",
  "config_hash": "...",
  "last_error": "pi_agent_install_failed"
}
```

**Acceptance tests:**

- missing npm should not write `status = completed`;
- failed npm install should not write `status = completed`;
- after failed install, `mypi needs-sync --trigger shell` should exit `0`;
- after successful fake install, `mypi needs-sync --trigger shell` should exit `1`.

---

### P0.4 Default install is not reproducible

**Files:**

- `modules/pi-agent.nix`
- `src/mypi_agent/sync.py`
- `README.md`

**Current evidence:**

`piPackageVersion` defaults to `null`:

```nix
piPackageVersion = lib.mkOption {
  type = lib.types.nullOr lib.types.str;
  default = null;
  description = "Pinned Pi package version. Required for reproducible pinned installs.";
};
```

When unset, `sync.py` installs the floating latest package:

```python
install_target = pi_package_name if pi_package_version is None else f"{pi_package_name}@{pi_package_version}"
```

It emits:

```python
warnings.append("pi_package_version_unset_for_pinned_npm")
```

but still proceeds.

**Why this matters:**

The README currently describes the module as bootstrapping Pi in a “project-local, reproducible way.” Project-local does not imply reproducible. Without a version pin, two developers entering the same devenv on different days can receive different Pi versions.

**Required fix:**

Choose one policy and make the docs/code match it.

Preferred policy:

```nix
piAgent.piPackageVersion = "0.74.0"; # example; update deliberately
```

Then allow floating installs only if the user explicitly opts into them:

```nix
piAgent.piPackageVersion = null;
piAgent.allowFloatingPiVersion = true;
```

Alternative policy:

Keep `null`, but change README language from “reproducible” to “project-local by default; reproducible when `piPackageVersion` is set.”

For this repository’s stated purpose, pinned-by-default is better.

**Acceptance tests:**

- default install target includes `@version`;
- explicit floating mode is required for unversioned install;
- `mypi doctor` warns or fails when floating installs are enabled without explicit acknowledgement.

---

### P0.5 User-owned `.pi/settings.json` can be taken over without meaningful repair gating

**File:** `src/mypi_agent/sync.py`

**Current evidence:**

Classification detects user-owned settings:

```python
if not has_marker:
    return "user_owned"
```

But `_merge_settings()` merges MYPI-managed keys into any existing dict:

```python
merged = dict(existing_payload)
for key in MANAGED_SETTINGS_KEYS:
    merged[key] = generated_payload[key]
merged["x-mypi-agent"] = generated_payload["x-mypi-agent"]
```

`repair_shim` only affects the reported `shim_updated` value:

```python
shim_updated = repair_shim or not paths.settings_path.exists() or existing_settings != merged_settings_payload
```

It does not prevent writing.

**Why this matters:**

Pi settings are user/project-owned config. MYPI should not silently claim ownership of a pre-existing `.pi/settings.json` unless the user explicitly asks it to repair/adopt the shim.

**Required fix:**

Before writing settings, classify the current file.

If classification is one of:

```text
user_owned
invalid_json
```

then fail unless `--repair-shim` is supplied.

Recommended behavior:

```text
error: .pi/settings.json already exists and is not MYPI-managed.
Run `mypi sync --repair-shim` to adopt/repair the settings shim.
```

For `managed_changed`, decide whether to preserve or require explicit sync based on the managed keys that changed.

**Acceptance tests:**

- user-owned settings + plain `mypi sync` fails and does not rewrite;
- user-owned settings + `mypi sync --repair-shim` adopts and preserves unrelated keys;
- invalid JSON + plain `mypi sync` fails and does not overwrite;
- invalid JSON + `--repair-shim` rewrites after explicit authorization.

---

### P0.6 `needs_sync()` is too shallow for shell-entry bootstrap

**File:** `src/mypi_agent/sync.py`

**Current evidence:**

```python
def needs_sync(paths: Paths) -> bool:
    if not paths.agent_root.exists() or not paths.settings_path.exists() or not paths.manifest_path.exists():
        return True
    bootstrap = _read_json_or_none(paths.bootstrap_state_path)
    if not isinstance(bootstrap, dict):
        return True
    return bootstrap.get("config_hash") != _config_hash(paths)
```

It does not check:

- upstream `pi` binary exists;
- upstream `pi` binary is executable;
- package version matches the configured version;
- resource directories exist;
- bootstrap status is completed;
- previous install failed;
- `package-lock.json` matches the requested package identity.

**Why this matters:**

Shell-entry bootstrap reliability depends on `needs_sync()` being conservative. A stale or partially deleted runtime should trigger repair.

**Required fix:**

Make `needs_sync()` check all required runtime invariants.

Minimum:

```python
if not paths.pi_executable_path.exists(): return True
if not os.access(paths.pi_executable_path, os.X_OK): return True
for resource_dir in RESOURCE_DIRS:
    if not (paths.agent_root / resource_dir).is_dir(): return True
```

Better:

- validate manifest schema;
- validate bootstrap status;
- validate installed package version against `MYPI_PI_PACKAGE_VERSION`;
- validate current settings marker and agent root;
- validate npm package metadata from `package-lock.json`.

---

### P0.7 Test suite performs real npm work unless externally faked

**Files:**

- `tests/integration/test_sync.py`
- `tests/integration/test_cli.py`
- `tests/integration/test_doctor.py`

**Current evidence:**

Several tests call `run_sync()` without monkeypatching npm. In a normal environment where `npm` exists, these tests can perform actual npm installs.

A test run with real npm available timed out. With fake `node` and fake `npm` placed first in `PATH`, the test suite produced:

```text
37 passed, 5 skipped
```

The 5 skipped tests were devenv fixture tests skipped because `devenv` was not available in the execution environment.

**Why this matters:**

The fast test suite should be hermetic. Real network/npm work should be isolated behind explicit smoke tests.

**Required fix:**

Make fake npm the default for unit/integration tests that exercise `run_sync()`.

Suggested pattern:

```python
@pytest.fixture(autouse=True)
def fake_node_and_npm(monkeypatch, tmp_path):
    ...
```

Then mark real npm/devenv tests separately:

```python
@pytest.mark.real_npm
@pytest.mark.devenv_smoke
```

**Acceptance tests:**

- `python -m pytest` never touches the network;
- real npm/devenv smoke tests require explicit opt-in;
- CI has one fast hermetic job and one slower environment smoke job.

---

## 6. P1 Important Hardening Findings

These are not necessarily blockers for a local prototype, but they should be fixed before wider reuse.

---

### P1.1 Generate Pi `npmCommand` in `.pi/settings.json`

**Files:**

- `src/mypi_agent/sync.py`
- `modules/pi-agent.nix`
- `README.md`

Pi supports an `npmCommand` setting for package lookup/install operations. Since this repository’s job is to make Pi work inside a devenv shell, MYPI should configure Pi to use the devenv-provided npm explicitly.

Current generated settings include:

```json
{
  "packages": [],
  "extensions": ["../.agents/pi/extensions"],
  "skills": ["../.agents/pi/skills"],
  "prompts": ["../.agents/pi/prompts"],
  "themes": ["../.agents/pi/themes"],
  "enableSkillCommands": true
}
```

Recommended addition:

```json
{
  "npmCommand": ["/nix/store/...-nodejs-22/bin/npm"]
}
```

A more stable approach is to generate a small MYPI npm wrapper under the project-local agent root and set:

```json
{
  "npmCommand": ["../.agents/pi/bin/npm"]
}
```

But if the goal is “no wrapping” for Pi itself, keep that distinction clear:

- `pi` should be direct upstream CLI;
- an npm wrapper is acceptable only if needed to pin npm behavior for Pi package operations.

If `npmCommand` is MYPI-owned, add it to `MANAGED_SETTINGS_KEYS`.

---

### P1.2 Add sync locking

**File:** `src/mypi_agent/sync.py`

Two shells can enter the same project and run `mypi sync` concurrently. The code runs npm install and writes several JSON files without a lock.

`atomic_write_json()` is atomic per file, but it uses a deterministic temp path:

```python
tmp_path = path.with_suffix(path.suffix + ".tmp")
```

Two writers can collide on the same temp file.

Recommended fix:

- create `.agents/pi/.state/sync.lock`;
- use `fcntl.flock()` on Unix;
- use unique temp files for JSON writes, e.g. `NamedTemporaryFile(delete=False, dir=path.parent)`;
- hold the lock across npm install and state writes.

---

### P1.3 Source-filter the Python package input

**File:** `packages/mypi-agent-cli.nix`

Because `dev/` is intentionally ignored, this is no longer a finding about the provided zip’s `dev/` directory. Still, the package source should be filtered defensively.

Current code:

```nix
src = ../.;
```

Recommended:

```nix
src = lib.fileset.toSource {
  root = ../.;
  fileset = lib.fileset.unions [
    ../pyproject.toml
    ../README.md
    ../src
  ];
};
```

or:

```nix
src = lib.cleanSourceWith {
  src = ../.;
  filter = path: type:
    let base = baseNameOf path;
    in !(base == ".devenv"
      || base == ".pytest_cache"
      || base == ".agents"
      || base == ".pi"
      || base == "node_modules"
      || base == ".npm-cache");
};
```

The allowlist approach is preferable for a small Python CLI package.

---

### P1.4 Validate `piAgent.root`

**Files:**

- `modules/pi-agent.nix`
- `src/mypi_agent/models.py`

`piAgent.root` is documented as project-relative, but the current implementation does not robustly reject absolute paths or `..` traversal.

In Nix:

```nix
assertions = [
  {
    assertion = !(lib.hasPrefix "/" cfg.root) && !(lib.hasInfix ".." cfg.root);
    message = "piAgent.root must be a project-relative path without '..'.";
  }
];
```

In Python, resolve and verify containment:

```python
root = (self.project_root / override).resolve()
if self.project_root.resolve() not in root.parents and root != self.project_root.resolve():
    raise RuntimeError("error: MYPI_AGENT_ROOT must stay inside the project root")
```

This matters because sync writes files and runs npm install under that root.

---

### P1.5 Strengthen `doctor`

**File:** `src/mypi_agent/doctor.py`

Current doctor checks are useful but incomplete.

Add checks for:

- `pi` path points to `node_modules/.bin/pi`;
- `pi --version` succeeds;
- installed package version equals configured `MYPI_PI_PACKAGE_VERSION` when pinned;
- `package-lock.json` contains the expected package identity;
- `.pi/settings.json` includes expected `npmCommand`;
- bootstrap status is `completed`;
- bootstrap state has `pi_installed = true`;
- settings classification is not `user_owned` or `invalid_json`;
- resource directories exist;
- Node major version is compatible with current Pi requirements, if upstream documents one.

Also make warnings distinct from errors. For example, a floating package version should be a warning if explicitly allowed, not necessarily an error.

---

### P1.6 State files churn on every sync

**File:** `src/mypi_agent/sync.py`

`primitive-registry.json` includes:

```python
"installed_at_rfc3339_utc": _utc_now_rfc3339()
```

That value changes on every non-diff sync, even when nothing material changed. This can make state noisy and complicate drift checks.

Recommended behavior:

- only update `installed_at_rfc3339_utc` when npm install actually changed or reinstalled the package;
- preserve previous registry entry when package identity is unchanged;
- add `last_checked_at` separately if needed.

---

### P1.7 Clarify package-install strategy

The code currently uses:

```bash
npm install --prefix .agents/pi @earendil-works/pi-coding-agent
```

This is not the same as upstream’s global install command, but it is the correct shape for a project-local devenv bootstrap. The docs should say this explicitly:

> MYPI installs the upstream Pi npm package into the project-local agent root and exposes the upstream `pi` binary from that local install. It does not install Pi globally.

That statement avoids confusing “normal upstream functionality” with global mutation.

---

## 7. P2 Cleanup and Quality Findings

### P2.1 Remove leftover Allium/template naming

**Files:**

- `src/mypi_agent/base_model.py`
- `pyproject.toml`

Current class:

```python
class AlliumBase(BaseModel):
```

Current project description:

```toml
description = "A Python project template with modern tooling."
```

Recommended:

```python
class MypiBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
```

and:

```toml
description = "MYPI bootstrap tooling for project-local Pi agent integration in devenv shells."
```

Also remove stale commented `template-py` URLs.

---

### P2.2 Remove or wire `runtime.py`

`runtime.py` currently returns hard-coded policy values and is not integrated into the command surface. It reads like scaffolding from an earlier design.

Either:

1. wire it into `mypi doctor`; or
2. remove it until there is real runtime policy behavior.

Unwired policy stubs weaken confidence in the foundation.

---

### P2.3 Rename result fields from `pi_agent_*` to `pi_*`

If the upstream command is `pi`, then internal names should follow.

Examples:

```python
pi_agent_installed
pi_agent_executable_not_executable
missing_pi_agent_executable
```

should become:

```python
pi_installed
pi_executable_not_executable
missing_pi_executable
```

This is not urgent, but it will reduce conceptual noise.

---

### P2.4 README needs a contract rewrite

The README should be revised after the direct-`pi` decision.

Current generated file list says:

```text
.agents/pi/bin/pi-agent (launcher when installed)
```

Recommended generated file list:

```text
.pi/settings.json
.agents/pi/manifest.json
.agents/pi/node_modules/.bin/pi
.agents/pi/node_modules/
.agents/pi/.npm-cache/
.agents/pi/.state/
```

Recommended command list:

```text
mypi sync
mypi doctor
mypi needs-sync
mypi paths
pi [normal upstream Pi args]
```

Optional:

```text
mypi pi [normal upstream Pi args]
```

but only if passthrough is fixed.

---

## 8. File-by-File Review

### 8.1 `devenv.nix`

Current:

```nix
{ lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.enable = lib.mkDefault true;
}
```

Assessment: good.

This is the correct root public import surface. A consumer importing `mypi-agent` from `devenv.yaml` receives the module enabled by default.

Risk: auto-enable via `mkDefault true` is appropriate for this repo’s intended import contract, but it should be documented. If this repo later becomes a library of several modules, auto-enable may become surprising.

Recommendation: keep for now.

---

### 8.2 `devenv.yaml`

Assessment: acceptable.

The root `devenv.yaml` contains normal input wiring. Because the public import behavior is defined by root `devenv.nix`, this is not a concern for consumer import.

Recommendation: keep minimal. Avoid moving development-specific imports here.

---

### 8.3 `modules/pi-agent.nix`

Strengths:

- clean option namespace;
- uses `pkgs.nodejs_22` by default;
- exports `MYPI_PROJECT_ROOT`, `MYPI_AGENT_ROOT`, package name/version, and npm install flags;
- supports `bootstrap.mode`;
- root `devenv.nix` can enable it by default.

Problems:

1. It exposes a `pi-agent` compatibility shim instead of exposing upstream `pi` directly.
2. It does not put `.agents/pi/node_modules/.bin` on `PATH`.
3. It does not export `MYPI_AGENT_VERSION`, even though the Python config hash includes it.
4. It does not validate `piAgent.root`.
5. `piPackageVersion = null` by default undercuts reproducibility.
6. It does not generate or pass an explicit npm command for Pi’s own package operations.

Recommended changes:

- add `$project_root/$root_rel/node_modules/.bin` to `PATH`;
- remove `piAgentBin` or make it legacy-only;
- export `MYPI_AGENT_VERSION` from the Nix package version;
- validate `cfg.root`;
- pin default `piPackageVersion`, or explicitly rename the default mode as floating;
- support generated `npmCommand` in settings.

---

### 8.4 `packages/mypi-agent-cli.nix`

Current:

```nix
src = ../.;
```

Assessment: functional but too broad.

Even ignoring `dev/`, this can include tests, fixtures, generated local files, cache files, or accidental state when built from a local path. For a small CLI package, the Nix source should be allowlisted.

Recommended:

```nix
src = lib.fileset.toSource {
  root = ../.;
  fileset = lib.fileset.unions [
    ../pyproject.toml
    ../README.md
    ../src
  ];
};
```

Also consider whether `python313Packages` is intentionally strict. If Python 3.13 is a policy, document it. If not, make it easier to override.

---

### 8.5 `src/mypi_agent/models.py`

Strengths:

- `Paths.discover()` is simple;
- project-root discovery from subdirectories is useful;
- centralized paths are good.

Problems:

- `pi_executable_path` points to `.agents/pi/bin/pi-agent`, not upstream `.agents/pi/node_modules/.bin/pi`;
- `agent_root` does not validate containment inside project root;
- `relative_to(paths.project_root)` can fail if a malicious or invalid root escapes the project.

Required change:

```python
@property
def pi_executable_path(self) -> Path:
    return self.agent_root / "node_modules" / ".bin" / "pi"
```

Add root containment validation.

---

### 8.6 `src/mypi_agent/sync.py`

This is the most important file.

Strengths:

- clear generated layout;
- manifest schema exists;
- settings marker exists;
- diff mode is intended to be read-only;
- package metadata is partially captured;
- `npmInstallFlags` are configurable.

Problems:

1. Writes a `pi-agent` wrapper instead of exposing upstream `pi` directly.
2. Can mark failed/skipped installs as completed.
3. `needs_sync()` ignores actual installed executable state.
4. User-owned `.pi/settings.json` can be adopted without explicit repair.
5. No sync lock.
6. Deterministic temp file path can collide under concurrent writes.
7. Floating latest install is allowed by default.
8. `installed_at_rfc3339_utc` changes on every sync.
9. `manifest_healed` treats a missing manifest as invalid/healed, which is acceptable but semantically imprecise.
10. It does not generate `npmCommand`.

Highest-priority changes:

- remove launcher generation;
- verify `node_modules/.bin/pi` after npm install;
- only write completed bootstrap state after verification;
- require `--repair-shim` before adopting user-owned or invalid settings;
- improve `needs_sync()`;
- add locking.

---

### 8.7 `src/mypi_agent/cli.py`

Strengths:

- concise command surface;
- `--json` support is useful;
- `--allow-unmanaged` is useful for tests/sandboxes.

Problems:

1. `mypi agent` and `mypi pi` do not pass upstream flags.
2. The command naming conflicts with the direct upstream `pi` decision.
3. `require_settings_shim_actor()` only checks actor type; it does not enforce meaningful permissions.
4. `doctor` cannot run outside a valid settings actor even though doctor should often be the recovery tool.

Recommended command model:

```text
mypi sync
mypi doctor
mypi paths
mypi needs-sync
mypi pi      # optional passthrough alias
pi           # primary upstream CLI
```

If `mypi pi` remains, implement true passthrough.

Consider letting `mypi doctor` run even when the settings shim is missing/invalid. Doctor should diagnose broken bootstrap states, not be blocked by them.

---

### 8.8 `src/mypi_agent/doctor.py`

Strengths:

- checks missing settings;
- checks missing root;
- checks manifest schema;
- checks npm prefix locality;
- checks node/npm existence;
- checks executable and version command.

Problems:

- checks wrong executable path under the direct upstream model;
- does not validate installed package version;
- does not inspect package lock identity deeply;
- does not check bootstrap status;
- does not check generated `npmCommand`;
- secret check is crude and case-sensitive;
- all diagnostics are errors; warnings would be useful.

Recommended result model:

```python
class DoctorResult(MypiBaseModel):
    errors: list[Diagnostic]
    warnings: list[Diagnostic]
    info: list[Diagnostic]
    exit_code: int
```

---

### 8.9 `src/mypi_agent/surfaces_runtime.py`

The actor model is currently mostly ceremonial.

`require_settings_shim_actor()` only verifies the object type:

```python
if not isinstance(actor, SettingsShimActor):
    raise PermissionError(...)
```

It does not reject invalid classifications, root mismatches, or user-owned settings.

Recommendation:

- either make this a real policy gate;
- or remove it until the policy has meaningful enforcement.

Do not let a decorative authorization model create false confidence.

---

### 8.10 `src/mypi_agent/runtime.py`

This file is a stub.

Recommendation: remove or wire into `doctor`.

---

### 8.11 `tests/`

Strengths:

- useful sync coverage;
- useful CLI path discovery tests;
- valuable devenv fixture strategy;
- fake npm test for install path exists.

Problems:

- normal tests can invoke real npm;
- passthrough behavior is not tested;
- direct upstream `pi` exposure is not tested;
- failed npm install semantics are not tested;
- settings takeover safety is not tested;
- root traversal is not tested;
- concurrency is not tested.

Recommended new tests:

```text
test_pi_path_points_to_node_modules_bin_pi
test_sync_does_not_generate_pi_agent_wrapper
test_devenv_shell_exposes_pi_command
test_mypi_pi_passes_unknown_options
test_missing_npm_does_not_mark_bootstrap_completed
test_failed_npm_install_keeps_needs_sync_true
test_user_owned_settings_requires_repair_shim
test_invalid_settings_requires_repair_shim
test_agent_root_cannot_escape_project
test_concurrent_sync_uses_lock
```

---

## 9. Recommended Target Architecture

### 9.1 Command contract

```text
mypi sync         # create/update MYPI-managed runtime files
mypi doctor       # diagnose bootstrap and Pi install
mypi paths        # print resolved paths
mypi needs-sync   # shell-entry predicate
pi                # upstream Pi CLI, directly from project-local npm install
```

Optional:

```text
mypi pi           # passthrough alias to upstream pi
```

### 9.2 Runtime layout

```text
.pi/
  settings.json

.agents/pi/
  manifest.json
  package.json                 # optional, if npm needs it
  package-lock.json
  node_modules/
    .bin/pi                    # upstream CLI exposed on PATH
    @earendil-works/pi-coding-agent/
  extensions/
  skills/
  prompts/
  themes/
  .npm-cache/
  .state/
    bootstrap.json
    diagnostics.jsonl
    drift-report.json
    installed-packages.json
    primitive-registry.json
    sync.lock
```

No default:

```text
.agents/pi/bin/pi-agent
```

### 9.3 Generated `.pi/settings.json`

Recommended shape:

```json
{
  "packages": [],
  "extensions": ["../.agents/pi/extensions"],
  "skills": ["../.agents/pi/skills"],
  "prompts": ["../.agents/pi/prompts"],
  "themes": ["../.agents/pi/themes"],
  "enableSkillCommands": true,
  "npmCommand": ["/path/to/devenv/npm"],
  "x-mypi-agent": {
    "managed": true,
    "schemaVersion": 1,
    "agentRoot": "../.agents/pi",
    "managedKeys": [
      "extensions",
      "skills",
      "prompts",
      "themes",
      "enableSkillCommands",
      "npmCommand"
    ]
  }
}
```

If `npmCommand` uses a generated wrapper, document that it controls npm behavior only. It should not wrap `pi` itself.

### 9.4 Bootstrap state

Recommended success:

```json
{
  "schema_version": 1,
  "status": "completed",
  "trigger": "shell",
  "config_hash": "...",
  "pi_installed": true,
  "pi_executable": ".agents/pi/node_modules/.bin/pi",
  "package_name": "@earendil-works/pi-coding-agent",
  "package_version": "0.74.0",
  "last_error": null
}
```

Recommended failure:

```json
{
  "schema_version": 1,
  "status": "failed",
  "trigger": "shell",
  "config_hash": "...",
  "pi_installed": false,
  "last_error": "pi_install_failed"
}
```

`needs_sync()` should return true for failure or partial status.

---

## 10. Suggested Refactor Plan

### Phase 1: Direct upstream `pi` contract

1. Change `Paths.pi_executable_path` to `node_modules/.bin/pi`.
2. Remove launcher generation from `sync.py`.
3. Add `.agents/pi/node_modules/.bin` to shell `PATH`.
4. Remove or deprecate `piAgent.exposePiAgentShim`.
5. Update doctor to check upstream `pi`.
6. Update README generated-file and command sections.
7. Update tests that expect `.agents/pi/bin/pi-agent`.

### Phase 2: Bootstrap correctness

1. Add `_pi_installed()` verifier.
2. Change bootstrap state to `completed | failed | partial`.
3. Make `needs_sync()` verify executable state and bootstrap status.
4. Prevent failed installs from suppressing retries.
5. Make fake npm the default test path.

### Phase 3: Settings ownership and npm behavior

1. Require `--repair-shim` for user-owned/invalid settings.
2. Add `npmCommand` to generated Pi settings.
3. Add `npmCommand` to managed keys.
4. Update doctor to validate `npmCommand`.
5. Add tests for settings preservation and takeover prevention.

### Phase 4: Reproducibility and release hygiene

1. Pin `piPackageVersion` by default, or require explicit floating opt-in.
2. Source-filter `packages/mypi-agent-cli.nix`.
3. Add root validation.
4. Add sync lock.
5. Remove template naming and stale metadata.
6. Remove or wire `runtime.py`.

---

## 11. Concrete Acceptance Criteria

The repo should not be considered ready until these pass.

### Import behavior

In a temporary devenv-managed consumer repo:

```yaml
inputs:
  mypi-agent:
    url: path:/path/to/mypi-agent
    flake: false
imports:
  - mypi-agent
```

Run:

```bash
devenv shell -- command -v mypi
devenv shell -- command -v node
devenv shell -- command -v npm
devenv shell -- mypi sync --trigger shell
devenv shell -- command -v pi
devenv shell -- pi --version
devenv shell -- mypi doctor
```

Expected: all succeed.

### Direct upstream binary behavior

```bash
devenv shell -- which pi
```

Expected path pattern:

```text
<consumer-repo>/.agents/pi/node_modules/.bin/pi
```

Not:

```text
<consumer-repo>/.agents/pi/bin/pi-agent
```

### Bootstrap retry behavior

With npm missing or fake npm failing:

```bash
mypi sync --trigger shell
mypi needs-sync --trigger shell
```

Expected:

- sync reports failure/skipped install;
- bootstrap state is not completed;
- `needs-sync` returns true.

### Settings safety

With pre-existing `.pi/settings.json` lacking the MYPI marker:

```bash
mypi sync
```

Expected: fails without rewriting.

Then:

```bash
mypi sync --repair-shim
```

Expected: adopts/repairs settings and preserves unrelated user keys.

### Reproducibility

Default install target should be versioned, or floating latest must be explicitly configured and reported by doctor.

### Tests

Fast test suite:

```bash
python -m pytest
```

Expected:

- no network;
- no real npm install;
- deterministic pass/fail behavior.

Devenv smoke suite:

```bash
pytest -m devenv_smoke
```

Expected:

- creates a temporary consumer repo;
- imports this repo through `devenv.yaml`;
- verifies `mypi`, `node`, `npm`, and `pi`.

---

## 12. Updated Scorecard

| Area | Score | Notes |
|---|---:|---|
| Public devenv import surface | 8/10 | Root `devenv.nix` shape is good. |
| Separation from dev-only environment | 8/10 | Good given `dev/` is ignored and not imported. |
| Upstream Pi CLI fidelity | 4/10 | Current `pi-agent` wrapper should be removed in favor of direct `pi`. |
| Runtime determinism | 4/10 | Floating npm version by default. |
| Bootstrap reliability | 4/10 | Failed installs can be marked completed. |
| Settings safety | 5/10 | Classification exists, but repair gating is not enforced. |
| Test strategy | 6/10 | Good coverage direction; needs hermetic npm and stronger devenv smoke path. |
| Documentation | 6/10 | Clear but must be revised around direct `pi` and reproducibility limits. |
| Maintainability | 7/10 | Small codebase, good module structure; some stale template/runtime debris. |

Overall: **6.5 / 10**.

---

## 13. Bottom Line

The repository has the right foundation-level concept: a small devenv-importable module that installs Pi into a project-local runtime and provides a MYPI control plane. The public import shape is largely correct, and the `dev/` directory is not a concern when it is truly ignored and absent from the tracked public source.

The main correction is to stop treating `pi-agent` as the default runtime command. The upstream CLI is `pi`; MYPI should expose that binary directly from the project-local npm install. `mypi` should remain the control-plane command, not a replacement identity for the upstream agent.

After that, the most important hardening work is bootstrap correctness: failed installs must not be marked complete, `needs_sync()` must verify actual runtime state, user-owned settings should not be silently adopted, and tests must not depend on real npm by default.

Fix those issues and this becomes a credible minimal bootstrap library for importing Pi into devenv-managed projects through `devenv.yaml`.
