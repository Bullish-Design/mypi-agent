# MYPI-AGENT Refactor Implementation Checklist

This checklist translates the allium spec changes and requirements document into concrete implementation tasks, ordered by dependency. Each phase builds on the previous one.

---

## Phase 1: Split public module surface from development environment

**Goal**: Make `imports: - mypi-agent` work for consumers without leaking allium-env or dev dependencies.

This is the foundational change. Everything else depends on the root import surface being correct.

### 1.1 Replace root `devenv.nix` with thin public import surface

**Spec**: `module.allium` — `PublicImportSurface`, `AlliumNotInPublicSurface`
**Requirement**: R-001

- [x] Replace contents of `devenv.nix` with:
  ```nix
  { lib, ... }:
  {
    imports = [ ./modules/pi-agent.nix ];
    piAgent.enable = lib.mkDefault true;
  }
  ```
- [x] Verify the file contains no `allium.*` options, no `languages.python`, no `pkgs.uv`, no `pkgs.git`, no `scripts`, no `enterShell` hooks beyond what the module provides.

### 1.2 Replace root `devenv.yaml` with public-only inputs

**Spec**: `module.allium` — `ConsumerDoesNotRequireAllium`
**Requirement**: R-001, R-003

- [x] Remove `allium-env` input from root `devenv.yaml`.
- [x] Remove `allium-env` from `imports:` list.
- [x] Keep only `nixpkgs` (and `nixpkgs-python` if needed by the module). The root `devenv.yaml` should contain the minimum inputs a consumer would need, or be empty of imports entirely.

### 1.3 Move development environment to `dev/`

**Spec**: `module.allium` — `PrivateDevelopmentEnv`, `PrivateDevEnvIsIsolated`
**Requirement**: R-002

- [x] Create `dev/devenv.nix` containing the current development shell: Python 3.13, uv, git, allium config, test scripts, enterShell hooks.
- [x] Create `dev/devenv.yaml` with `allium-env` input and import, plus `nixpkgs` inputs.
- [x] Ensure `dev/devenv.yaml` can reference the parent repo's module if needed for local testing (e.g., `imports: - ../` or a path input).
- [x] Update any local development workflow docs/scripts to use `devenv shell --config dev/devenv.nix` or `cd dev && devenv shell`.
- [x] Verify `.agents/skills/` allium skill symlinks still work from the dev environment.

### 1.4 Verify consumer isolation

**Requirement**: R-003 acceptance criteria

- [x] Confirm that a clean consumer fixture using only `imports: - mypi-agent` evaluates without `allium-env` in its `devenv.yaml`.
- [x] Confirm the public root `devenv.nix` does not reference `allium` options.
- [x] Confirm removing allium-related files from a consumer fixture does not affect MYPI functionality.

---

## Phase 2: Provide Node/npm through the module

**Goal**: Consumers get `node`, `npm`, `npx` on PATH automatically. Pi installation stops failing silently.

### 2.1 Add `piAgent.nodePackage` option to `modules/pi-agent.nix`

**Spec**: `options.allium` — `ModuleOptions.node_package`, `ModuleProvidesNodeRuntime`
**Requirement**: R-004

- [x] Add option:
  ```nix
  piAgent.nodePackage = lib.mkOption {
    type = lib.types.package;
    default = pkgs.nodejs_22;
    description = "Node.js package for Pi/npm installation and operations.";
  };
  ```
- [x] Add `cfg.nodePackage` to the `config.packages` list in the module.
- [x] Verify the consumer shell has `node`, `npm`, and `npx` on PATH.

### 2.2 Add repo-scoped npm configuration

**Spec**: `options.allium` — `ShellEnvironment`, `ModuleConfiguresNpmScope`
**Requirement**: R-006

- [x] Set environment variables in the module's `enterShell` or `env`:
  ```nix
  MYPI_PROJECT_ROOT = "\${PWD}";  # or use a more robust project root
  NPM_CONFIG_PREFIX = "\${MYPI_PROJECT_ROOT}/${lib.escapeShellArg cfg.root}/npm-global";
  NPM_CONFIG_CACHE = "\${MYPI_PROJECT_ROOT}/${lib.escapeShellArg cfg.root}/.npm-cache";
  NPM_CONFIG_AUDIT = "false";
  NPM_CONFIG_FUND = "false";
  ```
- [x] Verify npm state goes under `.agents/pi/` and does not pollute `~/.npm` or global state.

### 2.3 Remove the `piAgent.sourceRoot` option

**Spec**: `options.allium` — open question on R-018
**Requirement**: R-018

- [x] Remove `sourceRoot` from `modules/pi-agent.nix` (it is declared but unused).
- [x] Remove any references to `cfg.sourceRoot` in the module.

### 2.4 Fix shell quoting in the module

**Spec**: `options.allium` — `ShellQuotingIsRobust`
**Requirement**: R-019

- [x] Replace all bare `${cfg.root}` interpolations in shell script strings with `${lib.escapeShellArg cfg.root}`.
- [x] Audit the `mypi` wrapper, `pi-agent` wrapper, and `enterShell` hooks for unquoted interpolations.

### 2.5 Pin Python version in Nix package

**Requirement**: R-020

- [x] In `packages/mypi-agent-cli.nix`, replace `python3Packages` with `python313Packages` (or make configurable) to match `pyproject.toml`'s `requires-python = ">=3.13"`.

---

## Phase 3: Make Pi installation deterministic

**Goal**: Sync records exactly what was installed. No silent version floating.

### 3.1 Add Pi package options to the Nix module

**Spec**: `options.allium` — `ModuleOptions.pi_package_name`, `ModuleOptions.pi_package_version`, `ModuleOptions.npm_install_flags`
**Requirement**: R-005

- [x] Add options to `modules/pi-agent.nix`:
  ```nix
  piAgent.piPackageName = lib.mkOption {
    type = lib.types.str;
    default = "@earendil-works/pi-coding-agent";
  };
  piAgent.piPackageVersion = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    description = "Pinned version. Required for reproducible installs.";
  };
  piAgent.npmInstallFlags = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [ "--ignore-scripts" "--no-audit" "--no-fund" ];
  };
  ```
- [x] Pass these values to the `mypi` wrapper as environment variables: `MYPI_PI_PACKAGE_NAME`, `MYPI_PI_PACKAGE_VERSION`, `MYPI_NPM_INSTALL_FLAGS`.

### 3.2 Update `sync.py` to use pinned versions

**Spec**: `packages.allium` — `PackagePinsValidated`, `PackageInstallRecordedInManifest`
**Requirement**: R-005

- [x] Read `MYPI_PI_PACKAGE_NAME` and `MYPI_PI_PACKAGE_VERSION` from environment.
- [x] If version is set, install `{name}@{version}` instead of bare `{name}`.
- [x] After install, read the actual installed version from `node_modules/{package}/package.json` and record it in the manifest and registry.
- [x] If version is not set and install_strategy is `pinned_npm`, warn or error.

### 3.3 Update manifest schema to include version info

**Spec**: `manifest.allium` — `Manifest` entity, `ManifestRecordsPiVersion`
**Requirement**: R-014

- [x] Change the manifest JSON payload to include:
  ```json
  {
    "schema_version": 1,
    "resources": ["extensions", "skills", "prompts", "themes"],
    "pi_package": "@earendil-works/pi-coding-agent",
    "pi_version": "1.2.3",
    "node_version": "22.x.x",
    "generated_by": "mypi-agent"
  }
  ```
- [x] Update `sync.py` manifest generation to populate these fields.

### 3.4 Update registry to record meaningful source identity

**Spec**: `registry.allium` — `PrimitiveInstallRecord`, `SourceIdentityIsMeaningful`
**Requirement**: R-015

Current `source_hash` in `sync.py` hashes the package name string:
```python
source_hash=hashlib.sha256(pi_pkg.encode()).hexdigest()[:16]
```

- [x] Replace with a hash of actual installed artifact identity: package name + version + integrity hash.
- [x] Add `package_name`, `package_version`, `npm_integrity_hash`, `settings_hash`, `manifest_hash` fields to the install record JSON.
- [x] If available, capture the npm resolved URL from `npm ls --json`.

---

## Phase 4: Fix CLI model and sync safety

**Goal**: CLI commands do what they say. Sync is safe, truthful, and non-destructive.

### 4.1 Add `mypi agent` command

**Spec**: `surfaces.allium` — `AgentCommandSurface`, `AgentLaunchesPi`, `AgentFailsWhenPiMissing`
**Requirement**: R-008

- [x] Add `agent` command to `cli.py` that:
  - Locates the Pi executable at `paths.pi_executable_path`.
  - If not found or not executable, prints `"error: Pi is not installed. Run: mypi sync"` and exits 1.
  - If found, executes it with `os.execvp` or `subprocess.run`, forwarding all remaining args, preserving stdin/stdout/stderr and exit code.
- [x] Optional: add `mypi pi` as an alias.

### 4.2 Remove or repurpose `mypi run`

**Spec**: `surfaces.allium` — (mypi run is absent from the spec)
**Requirement**: R-009

- [x] Remove the `run` command from `cli.py`.
- [x] Or rename it to `mypi runtime-check` if it's intended as diagnostics.
- [x] Update tests that reference `mypi run`.

### 4.3 Add `mypi needs-sync` command

**Spec**: `surfaces.allium` — `NeedsSyncSurface`, `NeedsSyncChecksConfigHash`
**Requirement**: R-022

- [x] Add `needs-sync` command to `cli.py` that:
  - Checks if AgentRoot exists, SettingsShim exists, Manifest exists, and config hash matches.
  - Config hash inputs: `piAgent.root`, Pi package name/version, npm flags, settings schema version, manifest schema version, mypi-agent version.
  - Exits 0 if sync is needed (truthy for shell `if` usage), exits 1 if not needed.
  - Does NOT mutate the filesystem.

### 4.4 Make `mypi sync --diff` truly read-only

**Spec**: `sync.allium` — `SyncDiffMode`; `core.allium` — `DiffModeIsReadOnly`
**Requirement**: R-010

Current `sync.py` creates directories, writes JSON files, and may install npm packages even when `diff_requested=True`.

- [x] Restructure `run_sync()` into two phases:
  1. **Plan phase**: Build a sync plan (what would be created, updated, classified). No filesystem writes.
  2. **Apply phase**: Execute the plan. Skipped entirely when `diff_requested=True`.
- [x] When `diff_requested=True`, return the plan with counts and classifications but perform zero writes.
- [x] Add acceptance test: hash project tree before `--diff`, verify identical after.

### 4.5 Make settings repair merge instead of overwrite

**Spec**: `sync.allium` — `SyncShimMerge`, `SettingsMergePolicy`, `SettingsMergePreservesUserKeys`
**Requirement**: R-011

Current `sync.py` replaces the entire `.pi/settings.json` file.

- [x] Define managed keys list: `["extensions", "skills", "prompts", "themes", "enableSkillCommands"]`.
- [x] When writing settings:
  1. Read existing `.pi/settings.json` if present.
  2. Parse as JSON. If parse fails, treat as fresh file.
  3. Update only managed keys with MYPI-generated values.
  4. Preserve all other keys as user-owned.
  5. Write the `x-mypi-agent` marker:
     ```json
     "x-mypi-agent": {
       "managed": true,
       "schemaVersion": 1,
       "agentRoot": "../.agents/pi",
       "managedKeys": ["extensions", "skills", "prompts", "themes", "enableSkillCommands"]
     }
     ```
- [x] Use the configured `piAgent.root` for the `agentRoot` value (fix the current hardcoded `../.agents/pi`).

### 4.6 Track write actions and report overwrites truthfully

**Spec**: `core.allium` — `TruthfulOverwriteReporting`, `WriteAction`; `sync.allium` — `SyncFinalize`
**Requirement**: R-012

Current `sync.py` always returns `existing_files_overwritten=False`.

- [x] Create a `WriteAction` dataclass/model with: `path`, `existed_before`, `content_changed`, `managed`.
- [x] For each file write in `run_sync()`, record a `WriteAction`:
  - Check if file exists before writing.
  - Compare content if file exists (hash or string compare).
- [x] Compute `existing_files_overwritten` from actual write actions:
  ```python
  existing_files_overwritten = any(
      a.existed_before and a.content_changed for a in write_actions
  )
  ```
- [x] Include the `write_actions` list in `SyncResult`.

### 4.7 Implement content-aware file classification

**Spec**: `upgrade.allium` — `PrimitiveFileState` (6 classifications), `ContentAwareClassification`
**Requirement**: R-013

Current `sync.py` marks any existing settings shim as `locally_modified` regardless of content.

- [x] Implement classification logic:
  - `missing`: file does not exist.
  - `managed_unchanged`: file exists, has MYPI marker, content matches expected payload.
  - `managed_changed`: file exists, has MYPI marker, content differs from expected.
  - `user_owned`: file exists, no MYPI marker present.
  - `user_modified`: file has marker but user added non-managed keys.
  - `invalid_json`: file exists but cannot be parsed.
- [x] Replace the current `_classify_file()` logic in `sync.py`.
- [x] Use content hashing (compare actual vs expected) rather than mere existence checks.

### 4.8 Implement schema-based manifest validation

**Spec**: `manifest.allium` — `Manifest` entity, `ManifestSchemaValidation`
**Requirement**: R-014

Current manifest validation in `doctor.py` accepts any JSON object.

- [x] Create a Pydantic model in `models.py`:
  ```python
  from typing import Literal
  class Manifest(AlliumBase):
      schema_version: Literal[1]
      resources: list[Literal["extensions", "skills", "prompts", "themes"]]
      pi_package: str
      pi_version: str | None = None
      node_version: str | None = None
      generated_by: str = "mypi-agent"
  ```
- [x] Use this model in `sync.py` when generating the manifest.
- [x] Use this model in `doctor.py` when validating the manifest (try `Manifest.model_validate_json()`; catch `ValidationError` as `manifest_schema_invalid`).

### 4.9 Implement atomic writes

**Spec**: `sync.allium` — `AtomicWritePolicy`
**Requirement**: R-024

- [x] Create a utility function `atomic_write_json(path, data)`:
  1. Write to a temporary file in the same directory (e.g., `path.with_suffix('.tmp')`).
  2. `os.fsync()` the file descriptor.
  3. `os.rename()` the temp file to the target path.
- [x] Use this function for all JSON file writes in `sync.py`: settings.json, manifest.json, bootstrap.json, drift-report.json, installed-packages.json, primitive-registry.json.

---

## Phase 5: Update doctor checks

**Goal**: `mypi doctor` catches real problems. It fails when Pi is actually unusable.

### 5.1 Add Node/npm checks to doctor

**Spec**: `doctor.allium` — `DoctorPerformsRequiredChecks` (missing_node, missing_npm)
**Requirement**: R-007

- [x] In `doctor.py`, check `shutil.which("node")`. If absent, add `"missing_node"` error.
- [x] Check `shutil.which("npm")`. If absent, add `"missing_npm"` error.

### 5.2 Add Pi executable checks to doctor

**Spec**: `doctor.allium` — `DoctorPerformsRequiredChecks` (missing_pi_agent_executable, pi_agent_executable_not_executable, pi_agent_version_check_failed)
**Requirement**: R-007

- [x] Check `paths.pi_executable_path` exists. If not, add `"missing_pi_agent_executable"` error.
- [x] If it exists, check `os.access(path, os.X_OK)`. If not executable, add `"pi_agent_executable_not_executable"` error.
- [x] If executable, try running `pi-agent --version` (or equivalent). If it fails, add `"pi_agent_version_check_failed"` error.

### 5.3 Add npm scope and settings root checks

**Spec**: `doctor.allium` — `DoctorPerformsRequiredChecks` (npm_scope_not_project_local, settings_shim_not_pointing_to_configured_root)
**Requirement**: R-007

- [x] Check that `NPM_CONFIG_PREFIX` env var is set and points under the agent root. If not, add `"npm_scope_not_project_local"` error.
- [x] Check that `.pi/settings.json` `x-mypi-agent.agentRoot` matches the configured root. If not, add `"settings_shim_not_pointing_to_configured_root"` error.

### 5.4 Add manifest schema validation to doctor

**Spec**: `doctor.allium` — `DoctorPerformsRequiredChecks` (manifest_schema_invalid)

- [x] If manifest.json exists and is valid JSON but fails `Manifest.model_validate()`, add `"manifest_schema_invalid"` error (distinct from `"invalid_manifest"` which covers missing/unparseable).

---

## Phase 6: Project root discovery and scope enforcement

**Goal**: `mypi` always operates on the correct project root, even from subdirectories.

### 6.1 Set `MYPI_PROJECT_ROOT` in the Nix module

**Spec**: `paths.allium` — `ProjectRoot`, `DiscoverProjectRoot`
**Requirement**: R-016

- [x] In `modules/pi-agent.nix`, set `MYPI_PROJECT_ROOT` in the wrapper or environment:
  ```nix
  export MYPI_PROJECT_ROOT="$PWD"
  ```
  (or use a devenv-provided project root variable if available).

### 6.2 Implement root discovery in Python

**Spec**: `paths.allium` — `DiscoverProjectRoot`, `WalkUpwardDiscovery`
**Requirement**: R-016

- [x] In `models.py` or a new `root_discovery.py`:
  1. If `MYPI_PROJECT_ROOT` is set, use it.
  2. Otherwise, walk upward from `cwd` looking for `devenv.nix` or `devenv.yaml`.
  3. If found, use that directory as the project root.
  4. If not found, fail (see 6.3).
- [x] Update `Paths` class to use the discovered root instead of `Path.cwd()`.

### 6.3 Reject unmanaged directories

**Spec**: `paths.allium` — `RejectUnmanagedDirectory`
**Requirement**: R-017

- [x] If no devenv root is found and `MYPI_ALLOW_UNMANAGED` is not set, print:
  ```
  error: mypi must be run inside a devenv-managed project
  ```
  and exit 1.
- [x] Add `--allow-unmanaged` flag to relevant CLI commands (or just the env var for tests).

---

## Phase 7: Bootstrap lifecycle visibility

**Goal**: Shell bootstrap is visible, reliable, and doesn't repeat expensive work.

### 7.1 Update shell bootstrap in the Nix module

**Spec**: `sync.allium` — `ShellBootstrapSync`
**Requirement**: R-021

Current bootstrap: `mypi sync >/dev/null 2>&1 || true`

- [x] Replace with:
  ```nix
  enterShell = lib.mkAfter ''
    if mypi needs-sync --trigger shell; then
      if ! mypi sync --trigger shell; then
        echo "warning: mypi bootstrap failed; run: mypi doctor" >&2
      fi
    fi
  '';
  ```
- [x] Ensure `--trigger shell` is passed so the sync records the trigger source.
- [x] Normal no-op shell entry should be quiet (no output when needs-sync returns false).

### 7.2 Add `piAgent.exposePiAgentShim` option

**Spec**: `options.allium` — `ModuleOptions.expose_pi_agent_shim`
**Requirement**: R-008

- [x] Add option to `modules/pi-agent.nix`:
  ```nix
  piAgent.exposePiAgentShim = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Expose a compatibility pi-agent command.";
  };
  ```
- [x] Only include `piAgentBin` in packages when `cfg.exposePiAgentShim` is true.

---

## Phase 8: Generated file policy

**Goal**: Clear policy on what to commit, what to gitignore.

### 8.1 Define and document gitignore policy

**Spec**: (not in allium; R-023 documentation requirement)
**Requirement**: R-023

- [x] Ensure `.gitignore` (or the module's generated `.gitignore` entries) includes:
  ```
  .agents/pi/node_modules/
  .agents/pi/.npm-cache/
  .agents/pi/bin/
  .agents/pi/.state/
  ```
- [x] Document that `.pi/settings.json` should be committed.
- [x] Document that `.agents/pi/manifest.json` may optionally be committed.

---

## Phase 9: Fix surfaces_runtime.py

**Goal**: Content-aware settings shim actor.

### 9.1 Fix `build_settings_shim_actor()` to use content-aware classification

**Spec**: `surfaces.allium` — `SettingsShim.classification`
**Requirement**: R-013

Current behavior: `locally_modified` is always `False`. `points_to_configured_root` checks for hardcoded `../.agents/pi`.

- [x] Read the settings file, parse JSON, check for `x-mypi-agent` marker.
- [x] Classify using the 6-state classification from 4.7.
- [x] Use the configured root (from `MYPI_AGENT_ROOT` env var) instead of hardcoded `../.agents/pi` when checking `points_to_configured_root`.
- [x] Set `locally_modified` based on actual content comparison (classification is `managed_changed` or `user_modified`).

---

## Phase 10: Tests

**Goal**: Comprehensive test coverage for all new behavior.

### 10.1 Add YAML import-only consumer fixture

**Spec**: `testing.allium` — `YamlImportOnlyFixtureExists`
**Requirement**: R-025

- [x] Create `tests/fixtures/devenv/yaml-import-only/devenv.yaml`:
  ```yaml
  inputs:
    mypi-agent:
      url: path:__REPO_ROOT__
      flake: false
  imports:
    - mypi-agent
  ```
- [x] Create `tests/fixtures/devenv/yaml-import-only/devenv.nix`:
  ```nix
  { ... }:
  {
    tasks."fixture:verify".exec = ''
      set -euxo pipefail
      command -v mypi
      command -v node
      command -v npm
      mypi paths --json
      mypi sync --trigger shell
      mypi doctor
    '';
  }
  ```
- [x] Add to the `test_devenv_fixture_verify_task` parametrized list.

### 10.2 Add tmp repo fixture test

**Spec**: `testing.allium` — `TmpRepoFixtureExists`
**Requirement**: R-026

- [x] Create a test that:
  1. Creates a fresh `tmp_path` directory.
  2. Writes a minimal `devenv.yaml` importing the local mypi-agent checkout.
  3. Runs `devenv shell --config . -- mypi sync --trigger shell`.
  4. Asserts `mypi`, `node`, `npm` are available.
  5. Runs `mypi doctor` and asserts exit 0.

### 10.3 Skip devenv tests when unavailable

**Spec**: `testing.allium` — `SkipDevenvTestsWhenUnavailable`
**Requirement**: R-027

- [x] Add to `test_devenv_fixtures.py` (and any other devenv-dependent test):
  ```python
  import shutil
  if shutil.which("devenv") is None:
      pytest.skip("devenv is not installed")
  ```
- [x] Or use a shared pytest fixture/marker for devenv availability.

### 10.4 Add sandboxed sync tests (no network)

**Spec**: `testing.allium` — `SandboxedSyncTests`
**Requirement**: R-028

- [x] Test: npm absent — sync completes with warning `pi_agent_install_skipped_no_npm`, no crash.
- [x] Test: fake npm success — mock `shutil.which("npm")` and `subprocess.run`, verify sync completes with Pi installed, registry records version.
- [x] Test: fake npm failure — mock npm to return non-zero, verify sync completes with warning `pi_agent_install_failed`, doctor detects missing Pi.
- [x] Test: pinned package — verify the exact npm install command includes `@{version}` when version is set.

### 10.5 Add `--diff` no-mutation test

**Spec**: `testing.allium` — `DiffNoMutationTest`
**Requirement**: R-029

- [x] Test:
  ```python
  def tree_hash(path):
      # hash all file paths and contents recursively
      ...
  before = tree_hash(tmp_path)
  result = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
  after = tree_hash(tmp_path)
  assert before == after
  assert result.diff_requested is True
  ```

### 10.6 Add custom-root settings actor test

**Spec**: `testing.allium` — `CustomRootSettingsTest`
**Requirement**: R-030

- [x] Test with `MYPI_AGENT_ROOT=.agents/custom-pi`:
  - Run sync.
  - Read `.pi/settings.json`.
  - Verify `x-mypi-agent.agentRoot` is `../.agents/custom-pi` (not hardcoded `../.agents/pi`).
  - Verify `build_settings_shim_actor()` returns `points_to_configured_root=True`.

### 10.7 Add doctor failure tests

**Spec**: `testing.allium` — `DoctorFailureTests`
**Requirement**: R-031

- [x] Test: settings and manifest exist but Pi executable is missing → doctor exit 1, error includes `missing_pi_agent_executable`.
- [x] Test: Pi executable exists but is not executable (chmod 644) → doctor exit 1, error includes `pi_agent_executable_not_executable`.
- [x] Test: npm absent → doctor exit 1, error includes `missing_npm`.
- [x] Test: node absent → doctor exit 1, error includes `missing_node`.

### 10.8 Add subdirectory invocation tests

**Spec**: `testing.allium` — `SubdirectoryInvocationTests`
**Requirement**: R-032

- [x] Test from `repo/packages/example/src`:
  - `mypi paths --json` → `project_root` is the devenv repo root, not the subdirectory.
  - `mypi sync` → creates `.pi/` and `.agents/pi/` at the repo root, not in the subdirectory.

### 10.9 Update existing tests for new behavior

- [x] Update `test_cli_sync_diff_prints_counts` to verify zero filesystem mutations.
- [x] Update `test_cli_doctor_reports_errors_and_exit_code` to expect new error codes (missing_node, missing_npm, missing_pi_agent_executable).
- [x] Update `test_sync_creates_missing_files_without_overwrite` to verify manifest schema fields.
- [x] Update `test_cli_run_emits_missing_env_warning_only` — either update for renamed command or remove.
- [x] Update `test_sync_installs_pi_agent_with_fake_npm` to verify version recording in manifest and registry.

---

## Phase 11: Documentation

### 11.1 Rewrite README.md

**Requirement**: R-033

- [x] Document: what mypi-agent is, how to import from devenv.yaml, auto-enable behavior, sync/doctor/agent commands, Node/npm provisioning, generated file locations, commit/ignore policy, input pinning, piAgent.root override, disabling shell bootstrap, troubleshooting.

### 11.2 Rewrite AGENTS.md

**Requirement**: R-034

- [x] Replace Allium-specific content with:
  - This repo provides a repo-scoped MYPI/Pi agent bootstrap module.
  - Public import must stay free of development-only dependencies.
  - allium-env is development-only.
  - All runtime commands go through `mypi`.
  - Nix/devenv fixtures are contract tests.
  - Generated file policy.

### 11.3 Add LICENSE file

**Requirement**: R-035

- [x] Add MIT LICENSE file to the repository root (matching pyproject.toml and Nix metadata claims).

---

## Verification: Acceptance Checklist

When all phases are complete, verify each item from the requirements document section 18:

- [x] Root `devenv.nix` imports `./modules/pi-agent.nix` and does not configure `allium`.
- [x] `allium-env` exists only in `dev/`, not the public import path.
- [x] A consumer can use `devenv.yaml` with `imports: - mypi-agent`.
- [x] The consumer receives `mypi` on `PATH`.
- [x] The consumer receives `node` and `npm` on `PATH`.
- [x] npm cache/prefix are project-local by default.
- [x] `mypi sync --trigger shell` can install or provision Pi.
- [x] `mypi doctor` fails if Pi is missing or unusable.
- [x] `mypi agent` launches Pi or forwards arguments to Pi.
- [x] `mypi sync --diff` is read-only.
- [x] `.pi/settings.json` repair merges MYPI-owned keys and preserves user settings.
- [x] Manifest validation uses a real schema.
- [x] State records exact Pi package/version/source identity.
- [x] `mypi` discovers the project root instead of using arbitrary `cwd`.
- [x] Integration tests skip cleanly if `devenv` is unavailable.
- [x] Fixture tests cover the real YAML import path.
- [x] README documents consumer setup and generated file policy.
- [x] `AGENTS.md` no longer describes Allium as the project contract.
- [x] `LICENSE` exists and matches project metadata.
