# Import Bootstrap V1 Implementation Mapping

Source spec: `.scratch/specs/mypi-agent/import-bootstrap-v1.allium`

## 1. File plan

- `flake.nix`
  - Export importable devenv module as `devenvModules.default = import ./modules/pi-agent.nix;`
- `modules/pi-agent.nix`
  - Define `options.piAgent.*`
  - Render desired state JSON into shell env
  - Register shell commands and first-entry hook
- `bootstrap/sync.sh`
  - Bootstrap root and shim
  - Reconcile external packages to declared version
  - Detect and report drift; preserve local files by default
- `bootstrap/doctor.sh`
  - Read latest diagnostics and drift report and print human + machine-readable output
- `bootstrap/templates/settings.json.tpl`
  - Shim template for `.pi/settings.json`
- `bootstrap/templates/manifest.json.tpl`
  - Initial `.agents/pi/manifest.json` template

## 2. piAgent options (module contract)

`modules/pi-agent.nix` should define:

- `piAgent.enable` (bool, default `false`)
- `piAgent.root` (string, default `.agents/pi`)
- `piAgent.bootstrap.mode` (enum: `first_entry_only`, `manual_only`, `every_entry`; default `first_entry_only`)
- `piAgent.bootstrap.stateFile` (string, default `.agents/pi/.state/bootstrap.json`)
- `piAgent.packages` (list of attrs):
  - `name` (string)
  - `sourceKind` (`npm` | `git` | `local_path`)
  - `sourceRef` (string)
  - `declaredVersion` (string)
  - `desiredState` (`installed` | `absent`, default `installed`)

Module should expose shell commands:

- `pi-agent-sync` -> `bootstrap/sync.sh`
- `pi-agent-doctor` -> `bootstrap/doctor.sh`

## 3. Rule-to-implementation mapping

### BootstrapOnFirstEntry

Spec intent: first shell entry triggers sync when enabled and `first_entry_only`.

Implementation:

- File: `modules/pi-agent.nix`
- In `enterShell`, evaluate:
  - if `piAgent.enable != true`, no-op
  - if mode = `manual_only`, no-op
  - if mode = `every_entry`, run `pi-agent-sync --trigger shell`
  - if mode = `first_entry_only` and state file missing or status `not_started`, run once

State representation:

- JSON file `${piAgent.root}/.state/bootstrap.json` with fields:
  - `status`: `not_started|completed|failed`
  - `lastRunAt`
  - `lastFailureReason`

### MaterializeMissingRootFiles

Spec intent: ensure root, manifest, and shim exist.

Implementation:

- File: `bootstrap/sync.sh`
- Steps:
  - `mkdir -p "$ROOT" "$ROOT/.state" .pi`
  - create `${ROOT}/manifest.json` from template only if missing
  - create `.pi/settings.json` from template only if missing
  - template interpolation includes resolved root path

Failure behavior:

- if any required file still missing after attempt:
  - append diagnostic `root_missing|manifest_missing|shim_missing`
  - mark sync failed

### FailWhenRootMaterializationCannotComplete

Spec intent: explicit failure transition for root materialization issues.

Implementation:

- File: `bootstrap/sync.sh`
- Write diagnostics JSONL to `${ROOT}/.state/diagnostics.jsonl`:
  - `{"code":"root_missing","severity":"error","detail":"..."}`
- Exit non-zero and persist bootstrap state with `status=failed`, `failureReason=root_materialization_failed`

### ReconcilePackagesToDeclaredVersion

Spec intent: installed packages match declared version exactly.

Implementation:

- File: `bootstrap/sync.sh`
- Desired-state input via env var from module:
  - `MYPI_AGENT_DESIRED_STATE_JSON`
- For each package with desired state `installed`:
  - `npm`: install exact (`name@declaredVersion`) into `${ROOT}/packages/<name>` or configured location
  - `git`: clone/fetch and checkout exact commit/tag declared
  - `local_path`: verify source path identity and copy/symlink strategy (no implicit version bump)
- Record actual resolved version/commit in `${ROOT}/.state/installed-packages.json`

Failure behavior:

- package operation errors write diagnostics:
  - `package_install_error` or `package_remove_error`
- mark sync failed with `failureReason=package_reconcile_failed`

### RemoveUndeclaredPackages

Spec intent: packages no longer declared should be absent.

Implementation:

- File: `bootstrap/sync.sh`
- Compare installed state file vs desired list
- Remove unmanaged package directories under `${ROOT}/packages`
- If remove fails, emit `package_remove_error` and fail run

### RecordDriftReport

Spec intent: produce artifact describing drift categories.

Implementation:

- File: `bootstrap/sync.sh`
- Drift checks:
  - shim differs from rendered template -> `shim_diff`
  - manifest differs from rendered template -> `manifest_diff`
  - installed set differs from declared set -> `package_set_diff`
  - installed version differs from declared -> `package_version_diff`
- Write `${ROOT}/.state/drift-report.json`:
  - `runId`, `rootPath`, `hasDrift`, `categories[]`, `entries[]`

### PreserveLocalEditsAndReportDrift

Spec intent: local files win by default.

Implementation:

- File: `bootstrap/sync.sh`
- Default mode: report-only for shim/manifest drift
- Never overwrite modified shim/manifest unless explicit flag exists (future `--repair-shim`)
- Continue successful run if only drift is detected and package reconcile succeeded

### CompleteSyncWhenNoDrift

Spec intent: succeed when no drift and no package/root failures.

Implementation:

- File: `bootstrap/sync.sh`
- Set bootstrap state `status=completed`
- Exit 0

### MarkBootstrapCompleted / MarkBootstrapFailed

Spec intent: persist environment bootstrap status.

Implementation:

- File: `bootstrap/sync.sh`
- Update `${ROOT}/.state/bootstrap.json` after each run with terminal status and reason

## 4. Surface-to-implementation mapping

### PiAgentModuleContract

- Exposed fields map to:
  - `module_imported` -> module import succeeds (implicit by evaluation)
  - `pi_agent_enabled` -> `piAgent.enable`
  - `bootstrap_mode` -> `piAgent.bootstrap.mode`
  - `bootstrap_status` -> `${ROOT}/.state/bootstrap.json.status`
  - `root_path` -> `piAgent.root`
- Operations map to:
  - `EnterShell(env)` -> `enterShell` hook in module
  - `RunSync(env)` -> `pi-agent-sync` command

### PiAgentDoctorContract

- File: `bootstrap/doctor.sh`
- Exposes run status/failure reason from `bootstrap.json`
- Exposes drift report categories from `drift-report.json`
- Exposes diagnostics from `diagnostics.jsonl`
- Operation:
  - `RunDoctor(env)` -> `pi-agent-doctor`

CLI behavior:

- Human summary by default
- `--json` outputs single machine-readable JSON document for automation

## 5. Execution order (build sequence)

1. Add `flake.nix` module export and create `modules/pi-agent.nix` with options only.
2. Add `bootstrap/sync.sh` skeleton with state read/write and root materialization.
3. Add package reconcile engine for `npm` then `git`, then `local_path`.
4. Add drift-report generation and local-preserve behavior.
5. Add `bootstrap/doctor.sh` with `--json` mode.
6. Wire `enterShell` first-entry logic.
7. Add minimal fixture tests for:
   - first-entry bootstrap
   - reconcile exact package versions
   - drift report without overwrite

## 6. Acceptance checks

- Consumer repo with `imports: [ mypi-agent ]` can enter shell and gets:
  - `.agents/pi/manifest.json` created if missing
  - `.pi/settings.json` created if missing
- Declared package version change causes reconcile on next sync.
- Local manual edits in shim/manifest are preserved; drift is reported.
- `pi-agent-doctor --json` returns status, diagnostics, drift categories.
