# MYPI-AGENT: Simplified Spec vs Implementation Review

**Date:** 2026-05-30
**Spec version:** Allium v3, post-consolidation (11 files, ~1,450 lines)
**Source review:** `MYPI-AGENT_CODE_REVIEW.md` (same directory)
**Spec location:** `.scratch/specs/allium/`

---

## Executive Summary

The consolidated allium specs define a clear, behaviour-focused contract for mypi-agent. Comparing these specs against the current implementation reveals **7 P0 gaps**, **6 P1 gaps**, and **4 P2 cleanups** that need refactoring. The spec consolidation removed implementation noise but the core behavioural requirements remain — and the code doesn't yet satisfy them.

The three biggest themes:

1. **Direct `pi` exposure** (P0.1) — spec says `node_modules/.bin/pi` on PATH; code generates `bin/pi-agent` wrapper
2. **Bootstrap correctness** (P0.3) — spec says failed installs must not be marked completed; code always writes `completed=True`
3. **Settings safety** (P0.5) — spec says user-owned settings require `--repair-shim`; code silently adopts them

---

## Spec-to-Code Gap Analysis

### P0: Release-Blocking

| ID | Spec Requirement | Spec File(s) | Code File(s) | Current State | What to Refactor |
|---|---|---|---|---|---|
| P0.1 | Pi exposed via `node_modules/.bin/pi` on PATH, no wrapper | `core.allium:32-35`, `environment.allium:139-143`, `module.allium:75-78`, `surfaces.allium:57-58` | `models.py:pi_executable_path`, `sync.py:_apply_sync_plan`, `modules/pi-agent.nix` | `pi_executable_path` returns `bin/pi-agent`; sync generates a shell launcher; Nix module doesn't add `node_modules/.bin` to PATH | Change `pi_executable_path` to `agent_root / "node_modules" / ".bin" / "pi"`. Delete launcher generation from `sync.py`. Add `$MYPI_AGENT_ROOT/node_modules/.bin` to `PATH` in `pi-agent.nix`. Remove `piAgentBin`/`exposePiAgentShim` options. |
| P0.2 | `mypi pi` passes all upstream args and exit code | `surfaces.allium:62-74` (rule `PiLaunchesPi`) | `cli.py:agent_command` | Uses `typer.Argument(None)` which doesn't capture unknown flags like `--version`, `-p`, `--mode` | Add `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}` and use `ctx.args` instead of `typer.Argument`. |
| P0.3 | Bootstrap only completed when pi binary exists and is executable | `core.allium:148-159` (invariant `BootstrapCompletedImpliesPiInstalled`), `sync.allium:165-184` (rule `SyncVerifyPiInstalled`) | `sync.py:run_sync` | `run_sync()` always sets `completed=True` and writes bootstrap state as `completed` regardless of npm outcome. `pi_agent_installed` is set from plan but not verified post-install. | Add `_pi_installed()` check after npm install. Only write `status: completed` when binary is confirmed. Write `status: failed` with `last_error` on failure. Make `BootstrapState` use the spec's `completed | failed | partial` enum. |
| P0.4 | Pinned version by default; floating requires explicit opt-in | `packages.allium:29-34` (default), `packages.allium:62-74` (rule `FloatingInstallRequiresOptIn`), `environment.allium:59` (`allow_floating_pi_version: false`) | `modules/pi-agent.nix`, `sync.py` | `piPackageVersion` defaults to `null`, floating latest is silently used. No opt-in gate. | Add `allowFloatingPiVersion` option (default `false`) to Nix module. Error when version is null and floating not opted into. Expose `MYPI_ALLOW_FLOATING_PI_VERSION` env var. |
| P0.5 | User-owned/invalid settings require `--repair-shim` | `sync.allium:98-107` (rule `SyncRejectsUserOwnedSettings`), `sync.allium:258-266` (invariants) | `sync.py`, `cli.py` | `--repair-shim` flag exists but sync doesn't gate on settings classification. User-owned settings are silently merged. | Check `SettingsShimActor.classification` before sync proceeds. If `user_owned` or `invalid_json` and `--repair-shim` not set, error with guidance message and exit 1. |
| P0.6 | `needs_sync()` verifies actual runtime state | `surfaces.allium:129-152` (rule `NeedsSyncChecksRuntimeState`) | `sync.py:needs_sync` | Only checks agent root, settings, manifest existence and config hash. Does not check pi executable, bootstrap status, or resource dirs. | Add checks for: pi binary exists at `node_modules/.bin/pi`, pi is executable, bootstrap state is `completed`, resource dirs exist. |
| P0.7 | Tests must not invoke real npm | `core.allium` (invariant `NpmScopeIsProjectLocal`), general test safety | `tests/` | Some test paths can reach real npm. No hermetic fake npm by default. | Make fake npm the default test fixture. Ensure no test path calls real npm install. |

### P1: Hardening

| ID | Spec Requirement | Spec File(s) | Code File(s) | What to Refactor |
|---|---|---|---|---|
| P1.1 | Generate `npmCommand` in `.pi/settings.json` | `sync.allium:132-142` (rule `SyncGeneratesNpmCommand`), `sync.allium:25` (managed keys includes `npmCommand`) | `sync.py`, `surfaces_runtime.py` | Add `npmCommand` to `MANAGED_SETTINGS_KEYS`. Generate it pointing to devenv-provided npm (Nix store path or wrapper). Add to settings payload during sync. |
| P1.2 | Sync locking prevents concurrent races | `core.allium:67-72` (entity `SyncLock`), `sync.allium:44-52` (rule `SyncAcquireLock`), `sync.allium:232-238` (rule `SyncReleaseLock`) | `sync.py` | Add `fcntl.flock()` on `.agents/pi/.state/sync.lock`. Hold across npm install and state writes. Use `try/finally` for release. Replace deterministic `.tmp` suffix with `NamedTemporaryFile`. |
| P1.3 | Nix source filtering | Not in allium spec (implementation concern) | `packages/mypi-agent-cli.nix` | Replace `src = ../.;` with `lib.fileset.toSource` allowlisting `pyproject.toml`, `README.md`, `src`. |
| P1.4 | Validate agent root stays inside project | `environment.allium:104-109` (rule `ValidateAgentRootContainment`), `environment.allium:147-155` (invariants) | `models.py`, `modules/pi-agent.nix` | In Nix: assert root has no `/` prefix or `..`. In Python: resolve and verify containment in `Paths.agent_root`. |
| P1.5 | Doctor separates warnings from errors; adds new checks | `doctor.allium:22-27` (entity `Diagnostic` with severity), `doctor.allium:118-137` (warning-level checks), `doctor.allium:155-165` (exit code policy) | `doctor.py` | Add `warnings` list to `DoctorResult`. Add `warning_count` field. Add checks: bootstrap status, version mismatch, missing `npmCommand`, resource dirs. Warnings don't cause exit 1. |
| P1.6 | Registry doesn't churn on unchanged installs | `registry.allium:23-32` (rule `RecordInstalledPackage`) | `sync.py` | Only update `installed_at_rfc3339_utc` when package identity actually changes. Preserve existing registry entry when name/version/integrity match. |

### P2: Cleanup

| ID | What to Refactor | Code File(s) |
|---|---|---|
| P2.1 | Rename `AlliumBase` to `MypiBaseModel`; fix `pyproject.toml` description | `base_model.py`, `pyproject.toml` |
| P2.2 | Remove or wire `runtime.py` | `runtime.py` |
| P2.3 | Rename `pi_agent_*` → `pi_*` in error reasons, field names, diagnostics | `doctor.py`, `sync.py`, `surfaces_runtime.py` |
| P2.4 | Rewrite README generated-file list and command sections | `README.md` |

---

## Spec Entity → Code Model Mapping

This table maps spec entities to their implementation counterparts to guide refactoring.

| Spec Entity | Spec File | Code Model | Status |
|---|---|---|---|
| `AgentRoot` | `core.allium` | `Paths.agent_root` (property) | Partial — no `required_dirs_present` check |
| `InstalledManifest` | `core.allium` | `Manifest` (Pydantic model) | OK — schema validation via Pydantic |
| `NodeRuntime` | `core.allium` | `doctor.py` (inline `shutil.which` checks) | OK but not a model |
| `PiExecutable` | `core.allium` | `Paths.pi_executable_path` + inline checks | Wrong path; needs model extraction |
| `NpmScope` | `core.allium` | `doctor.py` (inline env checks) | OK but not a model |
| `WriteAction` | `core.allium` | `sync.py:WriteAction` | OK |
| `BootstrapState` | `core.allium` | `sync.py` (inline JSON writes) | Missing `failed`/`partial` states; always writes `completed` |
| `SyncLock` | `core.allium` | Not implemented | Missing entirely |
| `SyncRun` | `core.allium` | `sync.py:SyncResult` | Partial — missing fields like `filesystem_mutated` |
| `SecretRuntimePolicy` | `core.allium` | `runtime.py` | Stub; hardcoded values; not wired |
| `SettingsMergePolicy` | `sync.allium` | `sync.py:MANAGED_SETTINGS_KEYS` | Missing `npmCommand` in managed keys |
| `SettingsShim` | `surfaces.allium` | `surfaces_runtime.py:SettingsShimActor` | Good classification logic; missing `npm_command_configured` |
| `NeedsSyncResult` | `surfaces.allium` | `sync.py:needs_sync()` (returns bool) | Too shallow; needs runtime state checks |
| `DoctorRun` | `doctor.allium` | `doctor.py:DoctorResult` | Missing `warning_count`; all diagnostics are errors |
| `Diagnostic` | `doctor.allium` | `doctor.py:diagnostics` (dict list) | Missing severity enum; no warning support |
| `ProjectRoot` | `environment.allium` | `Paths.discover()` | OK — does walk-upward discovery |
| `ShellEnvironment` | `environment.allium` | `modules/pi-agent.nix` (env exports) | Missing `path_includes_node_modules_bin` |
| `ModuleOptions` | `environment.allium` | `modules/pi-agent.nix` (option declarations) | Missing `allow_floating_pi_version`, `mypi_agent_version` |
| `Manifest` | `manifest.allium` | `models.py:Manifest` | OK |
| `PiPackage` | `packages.allium` | Environment vars + inline code | No dedicated model; no `install_strategy` |
| `InstallRegistry` | `registry.allium` | `sync.py` (inline `primitive-registry.json` writes) | Churns on every sync |
| `DesiredState` | `upgrade.allium` | `sync.py:build_config_hash_inputs` | OK — hash computation exists |
| `PrimitiveFileState` | `upgrade.allium` | `surfaces_runtime.py` (classification logic) | OK — content-aware classification exists |
| `SyncPlan` | `upgrade.allium` | `sync.py:SyncPlan` (dataclass) | OK |
| `PublicImportSurface` | `module.allium` | Root `devenv.nix` + `modules/pi-agent.nix` | OK |
| `ConsumerProject` | `module.allium` | Not modelled; verified by fixture tests | OK |

---

## Spec Invariants → Code Verification

| Invariant | Spec File | Enforced in Code? | Gap |
|---|---|---|---|
| `BootstrapCompletedImpliesPiInstalled` | `core.allium:150-155` | No | Code writes completed regardless of install outcome |
| `FailedBootstrapRetriggersSync` | `core.allium:157-159` | No | Failed state doesn't exist; needs_sync doesn't check it |
| `SyncRequiresLock` | `core.allium:163-165` | No | No locking implemented |
| `SyncNonDestructive` | `core.allium:102-104` | Partial | Copy-if-missing intent exists but no strict check |
| `DiffModeIsReadOnly` | `core.allium:113-116` | Partial | Diff mode skips npm but still creates dirs |
| `NoSecretPersistence` | `core.allium:136-138` | Stub only | `runtime.py` returns hardcoded safe values |
| `NpmScopeIsProjectLocal` | `core.allium:131-134` | Partial | Env vars set by Nix; doctor checks but not enforced |
| `PinnedNpmRequiresVersion` | `packages.allium:105-107` | No | Null version silently uses latest |
| `FloatingNpmIsExplicit` | `packages.allium:109-115` | No | No opt-in gate exists |
| `UserOwnedSettingsRequireRepairShim` | `sync.allium:258-261` | No | User-owned settings silently adopted |
| `DoctorWarningsAreNonFatal` | `doctor.allium:184-187` | No | All diagnostics are errors |
| `RootIsProjectRelative` | `environment.allium:147-151` | No | No validation of root path |
| `AgentRootContainedInProject` | `environment.allium:153-155` | No | No containment check |
| `ContentAwareClassification` | `upgrade.allium:122-126` | Yes | Classification logic in `surfaces_runtime.py` is content-aware |
| `AtomicWritePolicy` | `sync.allium:242-245` | Partial | Uses rename but deterministic temp path risks collision |

---

## Recommended Refactor Phases

### Phase 1: Direct `pi` Contract (P0.1, P0.2)

**Goal:** Upstream `pi` is the user-facing command, not a generated wrapper.

1. `models.py` — Change `pi_executable_path` to `self.agent_root / "node_modules" / ".bin" / "pi"`
2. `sync.py` — Delete the `bin/pi-agent` launcher generation block in `_apply_sync_plan()`
3. `modules/pi-agent.nix` — Add `"$MYPI_AGENT_ROOT/node_modules/.bin"` to `PATH`; remove `piAgentBin` derivation
4. `cli.py` — Fix `pi_command`/`agent_command` with `allow_extra_args=True, ignore_unknown_options=True`
5. `doctor.py` — Update executable check to use new path; rename `pi_agent_*` error codes to `pi_*`
6. Tests — Update all assertions expecting `bin/pi-agent` path

### Phase 2: Bootstrap Correctness (P0.3, P0.6)

**Goal:** Failed installs are never marked completed; `needs_sync` checks real state.

1. `sync.py` — Add `_pi_installed(paths)` verifier checking `node_modules/.bin/pi` exists + executable
2. `sync.py` — Only write `status: completed` after `_pi_installed()` passes; write `status: failed` on failure
3. `sync.py` — Add `BootstrapState` model with `completed | failed | partial` status enum
4. `sync.py:needs_sync()` — Add checks: pi binary exists, pi executable, bootstrap status is completed, resource dirs exist
5. Tests — Add `test_failed_npm_install_keeps_needs_sync_true`, `test_missing_pi_binary_triggers_resync`

### Phase 3: Settings Safety + npmCommand (P0.5, P1.1)

**Goal:** User-owned settings cannot be silently adopted; `npmCommand` is generated.

1. `sync.py` — Before sync proceeds, check `SettingsShimActor.classification`; if `user_owned`/`invalid_json` and `--repair-shim` not set, error and exit
2. `surfaces_runtime.py` — Add `npmCommand` to `MANAGED_SETTINGS_KEYS`
3. `sync.py` — Generate `npmCommand` in settings payload pointing to devenv npm
4. `doctor.py` — Add warning check for missing `npmCommand`
5. Tests — Add `test_user_owned_settings_requires_repair_shim`, `test_npm_command_in_settings`

### Phase 4: Reproducibility + Locking (P0.4, P1.2, P1.4)

**Goal:** Pinned versions by default; concurrent sync safety; root validation.

1. `modules/pi-agent.nix` — Add `allowFloatingPiVersion` option (default `false`); assert version is set when floating not allowed
2. `sync.py` — Check version/floating policy before npm install; error if version null and floating not opted into
3. `sync.py` — Add `fcntl.flock()` on `sync.lock`; use `NamedTemporaryFile` for atomic writes
4. `models.py` — Add root containment validation in `Paths.agent_root`
5. `modules/pi-agent.nix` — Add assertion rejecting absolute paths and `..` in `piAgent.root`

### Phase 5: Doctor + Cleanup (P1.5, P2.1-P2.4)

**Goal:** Doctor distinguishes warnings from errors; remove template artifacts.

1. `doctor.py` — Add `warnings` field, `Diagnostic` model with severity, warning-level checks (floating version, version mismatch, missing npmCommand, missing resource dirs)
2. `doctor.py` — Warnings don't cause exit 1
3. `base_model.py` — Rename `AlliumBase` to `MypiBaseModel`
4. `runtime.py` — Remove (or wire into doctor if policy checks become real)
5. `pyproject.toml` — Fix description
6. `README.md` — Rewrite generated file list and command sections

---

## What the Spec Got Right (No Code Changes Needed)

These spec areas are already satisfied by the current implementation:

- **Project root discovery** (`environment.allium`) — `Paths.discover()` walks upward and checks for devenv markers
- **Manifest schema** (`manifest.allium`) — Pydantic model matches spec exactly
- **Content-aware classification** (`upgrade.allium`) — `surfaces_runtime.py` does content-hash-based classification
- **Config hash computation** (`upgrade.allium`) — `build_config_hash_inputs()` captures the right inputs
- **Public import surface** (`module.allium`) — Root `devenv.nix` is minimal and correct
- **Dev environment isolation** (`module.allium`) — `dev/` directory not imported by consumers
- **Resource directories** — Standard `extensions/skills/prompts/themes` layout matches spec
- **Diff mode intent** (`sync.allium`) — `diff_requested` flag exists and skips npm install
- **Settings merge logic** (`sync.allium`) — Marker-based managed/user key separation works correctly

---

## Summary

The spec consolidation successfully removed ~24% of noise while preserving all behavioural requirements. The remaining specs are crisp and testable. The implementation gaps are well-understood and phased — Phase 1 (direct `pi`) and Phase 2 (bootstrap correctness) are the highest-impact refactors that bring the code into alignment with spec intent.
