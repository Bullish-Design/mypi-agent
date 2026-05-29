# MYPI-AGENT Refactor Requirements

## 1. Executive summary

`mypi-agent` is intended to be a modular bootstrap foundation for `devenv.nix`-managed repositories. A consumer repository should be able to add `mypi-agent` as a `devenv.yaml` input/import and receive a repo-scoped Pi coding-agent environment through the imported `pi-agent.nix` module.

The current repository contains the right early pieces: a Nix module at `modules/pi-agent.nix`, a Python CLI named `mypi`, sync/doctor commands, and integration fixtures. However, the current repository does not yet satisfy the intended import contract. The most important problem is that the repository root `devenv.nix` is still the development environment for building this library. It imports and configures `allium-env`, which should remain private to the development workflow and must not be brought into downstream consumer repositories.

The refactor should make the root import surface export the Pi-agent module only, keep `allium-env` isolated to this repository's own development workflow, and ensure that JavaScript/npm support required by Pi is configured by `mypi-agent` itself.

## 2. Target behavior

A downstream `devenv.nix`-managed project should be able to consume this library with a small `devenv.yaml` entry similar to:

```yaml
inputs:
  mypi-agent:
    url: github:Bullish-Design/mypi-agent
    flake: false

imports:
  - mypi-agent
```

After entering the consumer project's shell, the consumer should have:

- `mypi` available on `PATH`.
- JavaScript/npm tooling available as required by Pi installation and Pi package operations.
- A repo-scoped Pi agent installation rooted under `.agents/pi` by default.
- A `.pi/settings.json` shim that points Pi at MYPI-managed resources.
- A predictable bootstrap/sync lifecycle.
- No `allium-env` options, tasks, packages, or assumptions leaking into the consumer project.

The imported module should be intentionally scoped to the current repository. This foundation should not manage multiple repositories. Each repository gets its own imported instance and local `.agents/pi` state.

## 3. Current-state evidence from the repository

### 3.1 Root `devenv.nix` is currently a local development shell

The current root `devenv.nix` includes general development packages and Python tooling:

```nix
packages = [
  pkgs.git
  pkgs.uv
];

languages = {
  python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
  };
};
```

It also contains `allium` configuration:

```nix
allium.enable = true;
allium.specsDir = ".scratch/specs";
allium.codexSkills.enable = true;
allium.codexSkills.autoInstall = true;
allium.codexSkills.targetDir = ".agents/skills";
```

This is appropriate for developing `mypi-agent`, but it is not appropriate as the public import surface for consumer repositories.

### 3.2 Root `devenv.yaml` imports `allium-env`

The current root `devenv.yaml` contains:

```yaml
inputs:
  allium-env:
    url: github:Bullish-Design/allium-env?ref=v0.1.0
    flake: false

imports:
  - allium-env
```

This confirms that `allium-env` is a development dependency of this repository. It must be moved out of the public import path.

### 3.3 The actual module exists, but consumers do not get it from the root import

The repository does include `modules/pi-agent.nix`, which defines:

```nix
options.piAgent = {
  enable = lib.mkEnableOption "MYPI agent tooling";
  root = lib.mkOption {
    type = lib.types.str;
    default = ".agents/pi";
  };
  bootstrap.mode = lib.mkOption {
    type = lib.types.enum [ "first_entry_only" "manual_only" "every_entry" ];
    default = "first_entry_only";
  };
};
```

The fixtures import this module explicitly with:

```nix
imports = [
  (inputs.mypi-agent + "/modules/pi-agent.nix")
];
```

That bypasses the desired user-facing contract. The intended contract is `imports: - mypi-agent` in `devenv.yaml`, not manual Nix-path import of `modules/pi-agent.nix` in every consumer repository.

## 4. Relevant external behavior to design against

The devenv documentation describes `devenv.yaml` imports as a list of relative paths, absolute paths, or input references that import `devenv.nix` and `devenv.yaml` files. It also documents `inputs.<name>.flake`, where `false` means the input contains `devenv.nix` rather than a flake. See:

- https://devenv.sh/reference/yaml-options/
- https://devenv.sh/extending/
- https://devenv.sh/composing-using-imports/

The Pi documentation states that Pi is distributed as the npm package `@earendil-works/pi-coding-agent`, typically installed with:

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

It also documents that Pi packages can bundle extensions, skills, prompt templates, and themes. See:

- https://pi.dev/docs/latest
- https://pi.dev/docs/latest/quickstart
- https://github.com/earendil-works/pi

These points drive two requirements:

1. The imported devenv input must expose the MYPI module, not this repository's development shell.
2. `mypi-agent` must configure JavaScript/npm support because Pi installation and Pi package management are npm-based.

## 5. Refactor requirement: split public module surface from development environment

### Requirement R-001: Root import must expose `modules/pi-agent.nix`

The repository root `devenv.nix` should become the public import surface. It should import `modules/pi-agent.nix` and should not include this repository's own development-time dependencies.

Recommended root `devenv.nix` shape:

```nix
{ lib, ... }:
{
  imports = [
    ./modules/pi-agent.nix
  ];

  piAgent.enable = lib.mkDefault true;
}
```

This makes the simple consumer import install the module by default. If explicit opt-in is preferred, remove the `mkDefault true` line and document that consumers must add `piAgent.enable = true;` to their own `devenv.nix`.

Given the stated goal that importing this foundation should install the agent into the shell environment, `lib.mkDefault true` is the recommended behavior.

### Requirement R-002: Move development environment to a private profile/location

The current local development shell should be moved out of the root public import path. Acceptable options:

```text
dev/devenv.nix
dev/devenv.yaml
```

or:

```text
.devenv-dev/devenv.nix
.devenv-dev/devenv.yaml
```

or a documented development profile, as long as it is not loaded by downstream `imports: - mypi-agent` consumers.

The moved development environment may keep:

- `allium-env`
- Python 3.13 venv configuration
- `uv`
- local test tasks
- development-only scripts
- this repo's own automation/tooling

It must not be part of the public module import.

### Requirement R-003: Remove `allium-env` from the public path

`allium-env` must remain a private development dependency only. The consumer import of `mypi-agent` must not require or evaluate:

- `allium.enable`
- `allium.specsDir`
- `allium.codexSkills.*`
- any `allium-env` input
- any `allium-env` task or package

Acceptance criteria:

- A clean consumer fixture using only `imports: - mypi-agent` evaluates without `allium-env` in its `devenv.yaml`.
- Removing allium-related files from the consumer fixture does not affect MYPI functionality.
- The public root `devenv.nix` does not reference `allium` options.

## 6. Refactor requirement: module must configure JavaScript/npm for Pi

### Requirement R-004: `piAgent` module must provide npm-capable runtime tooling

The current `modules/pi-agent.nix` installs only:

```nix
packages = [ mypiPkg mypiBin piAgentBin ];
```

The Python sync code attempts to find `npm` dynamically:

```python
npm = shutil.which("npm")
if npm is None:
    warnings.append("pi_agent_install_skipped_no_npm")
```

That means the module can install `mypi` while failing to provide the tool required to install Pi itself. This must be corrected.

The module should install a Node.js package that provides `node`, `npm`, and `npx` in the devenv shell. Recommended default:

```nix
packages = [
  mypiBin
  nodePackage
];
```

with an option similar to:

```nix
piAgent.nodePackage = lib.mkOption {
  type = lib.types.package;
  default = pkgs.nodejs_22;
  description = "Node.js package used for Pi/npm installation and Pi package operations.";
};
```

If the selected `nodePackage` exposes `npm` separately in the chosen nixpkgs set, the module must include the required npm package as well.

### Requirement R-005: npm install behavior must be deterministic or explicitly declared non-deterministic

The current sync command installs:

```bash
npm install --prefix .agents/pi --ignore-scripts --no-audit --no-fund @earendil-works/pi-coding-agent
```

Without a version pin, this installs whatever version npm resolves at runtime. That is undesirable in a Nix/devenv environment.

The refactor should support one of the following strategies.

#### Preferred strategy: Nix-packaged Pi

Create a Nix derivation for the Pi CLI package and expose it directly through the shell. This avoids runtime registry access during shell bootstrap.

Benefits:

- Reproducible.
- Cacheable.
- Works without network during `devenv shell`.
- Aligns with Nix expectations.

#### Acceptable initial strategy: pinned npm package

Add options:

```nix
piAgent.piPackageName = "@earendil-works/pi-coding-agent";
piAgent.piPackageVersion = "<pinned-version>";
piAgent.npmInstallFlags = [ "--ignore-scripts" "--no-audit" "--no-fund" ];
```

Then install:

```bash
npm install --prefix "$MYPI_AGENT_ROOT" \
  --ignore-scripts \
  --no-audit \
  --no-fund \
  "@earendil-works/pi-coding-agent@<pinned-version>"
```

The chosen version should be recorded in the generated manifest and state files.

### Requirement R-006: npm configuration must be repo-scoped

The module and CLI should avoid polluting the user's global npm state. Pi installation should go under the configured `piAgent.root`, normally `.agents/pi`.

Recommended environment variables inside the shell:

```bash
export MYPI_AGENT_ROOT=.agents/pi
export MYPI_PROJECT_ROOT=<repo-root>
export NPM_CONFIG_PREFIX="$MYPI_PROJECT_ROOT/.agents/pi/npm-global"
export NPM_CONFIG_CACHE="$MYPI_PROJECT_ROOT/.agents/pi/.npm-cache"
export NPM_CONFIG_AUDIT=false
export NPM_CONFIG_FUND=false
```

The exact names may vary, but the design requirement is clear: npm state needed by Pi should remain project-local unless the user explicitly opts out.

### Requirement R-007: Pi executable must be verified by `doctor`

`mypi doctor` must not pass when Pi is missing. The current implementation can pass if `.pi/settings.json`, `.agents/pi`, and a dict-like manifest exist, even if `.agents/pi/bin/pi-agent` is absent.

Doctor must check:

- `node` exists when runtime npm installation is enabled.
- `npm` exists when runtime npm installation is enabled.
- configured Pi package is installed or packaged Pi binary is available.
- `.agents/pi/bin/pi-agent` exists if using the local launcher model.
- the launcher is executable.
- `pi --version` or equivalent succeeds, where practical.

Failure codes should distinguish:

```text
missing_node
missing_npm
missing_pi_agent_executable
pi_agent_executable_not_executable
pi_agent_version_check_failed
```

## 7. Refactor requirement: define the public CLI model

### Requirement R-008: All user-facing operations should go through `mypi`

The stated goal is that all CLI commands should be called from `mypi`. The current module exposes both:

- `mypi`
- `pi-agent`

and the current `mypi run` command does not launch Pi.

The public interface should be:

```bash
mypi sync
mypi doctor
mypi paths
mypi agent [args...]
```

Optional aliases:

```bash
mypi pi [args...]
```

The separate `pi-agent` binary should either be removed from default packages or made an opt-in compatibility shim:

```nix
piAgent.exposePiAgentShim = lib.mkOption {
  type = lib.types.bool;
  default = false;
};
```

### Requirement R-009: `mypi run` must either run something or be removed

The current `mypi run` only evaluates runtime policy and prints a warning. It does not launch the agent. This is misleading.

Acceptable fixes:

1. Rename it to `mypi runtime-check` if it is intended as diagnostics.
2. Remove it until it has a real purpose.
3. Make it an alias for `mypi agent`.

The recommended choice is to add `mypi agent` as the real Pi launcher and remove or repurpose `mypi run`.

## 8. Refactor requirement: safe sync semantics

### Requirement R-010: `mypi sync --diff` must be read-only

The current sync implementation accepts `diff_requested=True`, but still creates directories, writes JSON files, may install npm packages, and writes state. A diff mode must not mutate the repository.

Required design:

1. Build a sync plan.
2. If `--diff` is set, print or return the plan and exit without writes.
3. If `--diff` is not set, apply the plan.

Acceptance criteria:

- Hash or snapshot the project tree before `mypi sync --diff`.
- Run `mypi sync --diff`.
- Verify no filesystem changes occurred.

### Requirement R-011: Settings repair must merge, not overwrite

Pi's `.pi/settings.json` can contain user-controlled project settings. The current `repair_shim=True` path replaces the whole file with MYPI's generated payload.

The refactor must preserve user-owned keys and only manage the MYPI-owned resource path keys. Managed keys should include:

```json
[
  "extensions",
  "skills",
  "prompts",
  "themes",
  "enableSkillCommands",
  "x-mypi-agent"
]
```

If a future design needs to manage more keys, those keys must be added explicitly to a managed-key list in the marker.

Recommended marker:

```json
"x-mypi-agent": {
  "managed": true,
  "schemaVersion": 1,
  "agentRoot": "../.agents/pi",
  "managedKeys": ["extensions", "skills", "prompts", "themes", "enableSkillCommands"]
}
```

### Requirement R-012: Sync must truthfully report overwrites

The current result always returns:

```python
existing_files_overwritten=False
```

but the function overwrites several files. This is inaccurate and will hide destructive behavior.

The refactor should track write actions:

```python
class WriteAction(BaseModel):
    path: Path
    existed_before: bool
    content_changed: bool
    managed: bool
```

Then compute:

```python
existing_files_overwritten = any(
    action.existed_before and action.content_changed
    for action in write_actions
)
```

### Requirement R-013: File classification must be content-aware

The current primitive file classification marks any existing settings shim as `locally_modified`, regardless of whether it exactly matches the generated payload.

Required classifications:

```text
missing
managed_unchanged
managed_changed
user_owned
user_modified
invalid_json
```

Classification must compare actual content, not only file existence.

### Requirement R-014: Manifest validation must be schema-based

The current manifest validator accepts any JSON object. It should validate a real schema.

Recommended Pydantic model:

```python
from typing import Literal
from pydantic import BaseModel

class Manifest(BaseModel):
    schema_version: Literal[1]
    resources: list[Literal["extensions", "skills", "prompts", "themes"]]
    pi_package: str
    pi_version: str | None = None
    node_version: str | None = None
    generated_by: str = "mypi-agent"
```

`doctor` and `sync` should use this same schema.

### Requirement R-015: Generated state must record meaningful source identity

The current `source_hash` hashes the package name string. That does not identify the installed artifact.

The state should record one or more of:

- exact package name
- exact package version
- npm resolved URL
- npm integrity hash, if available
- Nix store path, if using Nix-packaged Pi
- generated settings hash
- generated resource manifest hash

This is required for meaningful drift detection and upgrades.

## 9. Refactor requirement: project-root and devenv scope enforcement

### Requirement R-016: `mypi` must discover the repository/devenv root

The current CLI uses `Path.cwd()` as the project root. If a user runs `mypi sync` from a subdirectory, it can create `.pi` and `.agents` in the wrong place.

Required behavior:

1. If `MYPI_PROJECT_ROOT` is set by the Nix wrapper, use it.
2. Otherwise walk upward until finding `devenv.nix`, `devenv.yaml`, or another explicit project marker.
3. If no devenv-managed root is found, fail by default.

### Requirement R-017: `mypi` should only operate inside a devenv-managed project by default

The intended scope is `devenv.nix`-managed projects. The CLI should reject unmanaged directories unless an explicit escape hatch is provided for tests or advanced usage.

Possible error:

```text
error: mypi must be run inside a devenv-managed project
```

Optional override:

```bash
mypi sync --allow-unmanaged
```

or an environment variable only used in tests:

```bash
MYPI_ALLOW_UNMANAGED=1
```

## 10. Refactor requirement: module option cleanup and hardening

### Requirement R-018: `sourceRoot` must be removed or implemented

`modules/pi-agent.nix` declares `piAgent.sourceRoot` but does not use it. Remove it unless there is a concrete supported override behavior.

If retained, it should actually affect package/module source selection.

### Requirement R-019: Shell quoting must be robust

The module currently interpolates `cfg.root` directly into shell scripts:

```nix
export MYPI_AGENT_ROOT="${cfg.root}"
launcher="${cfg.root}/bin/pi-agent"
```

Use Nix shell escaping, and validate that the root is project-relative.

Recommended shape:

```nix
export MYPI_AGENT_ROOT=${lib.escapeShellArg cfg.root}
```

### Requirement R-020: Python version pinning must be consistent

`pyproject.toml` requires Python `>=3.13`, while `packages/mypi-agent-cli.nix` uses generic `python3Packages`. The Nix package should use a Python package set compatible with the project metadata, such as `python313Packages`, or provide a configurable Python package set.

## 11. Refactor requirement: bootstrap lifecycle must be visible and reliable

### Requirement R-021: Shell bootstrap must not silently swallow failures

Current bootstrap:

```nix
mypi sync >/dev/null 2>&1 || true
```

This hides failures. It also calls `mypi sync` without `--trigger shell`.

Recommended behavior:

```nix
enterShell = lib.mkAfter ''
  if mypi needs-sync --trigger shell; then
    if ! mypi sync --trigger shell; then
      echo "warning: mypi bootstrap failed; run: mypi doctor" >&2
    fi
  fi
'';
```

The exact command names may vary, but requirements are:

- shell-triggered sync records `trigger=shell`.
- errors are visible.
- normal no-op shell entry is quiet.
- bootstrap does not repeatedly perform expensive network installs unless needed.

### Requirement R-022: Add `mypi needs-sync`

A lightweight check should determine whether bootstrap work is needed. It should compare a config hash/state file rather than relying only on `.pi/settings.json` existence.

Inputs to hash should include:

- `piAgent.root`
- Pi package name/version
- npm install flags
- managed settings schema version
- managed resources manifest schema version
- `mypi-agent` version

## 12. Refactor requirement: generated file policy

### Requirement R-023: Define what is committed and ignored

The README and generated state should clearly define which files are intended for source control.

Recommended default:

Commit:

```text
.pi/settings.json
```

Probably ignore:

```text
.agents/pi/node_modules/
.agents/pi/.npm-cache/
.agents/pi/bin/
.agents/pi/.state/
```

Potentially commit only if needed:

```text
.agents/pi/manifest.json
.agents/pi/extensions/
.agents/pi/skills/
.agents/pi/prompts/
.agents/pi/themes/
```

The final policy depends on whether MYPI-managed resource directories become user-editable. The important requirement is that the policy must be explicit.

### Requirement R-024: Use atomic writes

Generated JSON files should be written atomically to avoid corrupt files if sync is interrupted.

Recommended pattern:

1. Write to temporary file in the same directory.
2. `fsync` if appropriate.
3. Rename into place.

## 13. Test requirements

### Requirement R-025: Add a YAML import-only consumer fixture

This is the most important missing test.

Fixture layout:

```text
tests/fixtures/devenv/yaml-import-only/devenv.yaml
tests/fixtures/devenv/yaml-import-only/devenv.nix
```

`devenv.yaml`:

```yaml
inputs:
  mypi-agent:
    url: path:__REPO_ROOT__
    flake: false

imports:
  - mypi-agent
```

`devenv.nix`:

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

This fixture proves the real consumer contract.

### Requirement R-026: Add tmp repo fixture test

Create a test that constructs a fresh temporary repository and writes a minimal `devenv.yaml` importing the local `mypi-agent` checkout.

Required checks:

```bash
command -v mypi
command -v node
command -v npm
mypi sync --trigger shell
mypi doctor
mypi agent --version || true
```

This should be the canonical acceptance test for the bootstrap foundation.

### Requirement R-027: Skip devenv integration tests when devenv is unavailable

Current integration tests attempt to run `devenv` without checking whether it exists. Add:

```python
if shutil.which("devenv") is None:
    pytest.skip("devenv is not installed")
```

This keeps local Python test runs usable in environments that do not have `devenv` installed.

### Requirement R-028: Add no-network/sandboxed sync tests

The current sync behavior may attempt real npm registry access if npm exists. Tests should be deterministic.

Add tests for:

- npm absent
- fake npm success
- fake npm failure
- pinned package argument passed correctly
- no network access in non-integration tests

### Requirement R-029: Add `--diff` no-mutation test

Example:

```python
before = tree_hash(tmp_path)
result = run_sync(paths, explicit=True, repair_shim=False, diff_requested=True)
after = tree_hash(tmp_path)
assert before == after
assert result.diff_requested is True
```

### Requirement R-030: Add custom-root settings actor test

When `MYPI_AGENT_ROOT=.agents/custom-pi`, generated settings should point to `../.agents/custom-pi`, and runtime checks should report `points_to_configured_root=True`.

The current implementation hardcodes `../.agents/pi` in `build_settings_shim_actor`, so this test should fail before the refactor and pass after it.

### Requirement R-031: Add doctor failure tests for missing Pi executable

`doctor` must fail when sync skipped Pi installation or when the launcher is missing.

Required cases:

- settings and manifest exist, but Pi executable missing.
- Pi executable exists but is not executable.
- npm absent while runtime npm install is enabled.
- node absent while runtime npm install is enabled.

### Requirement R-032: Add subdirectory invocation tests

From a nested path like:

```text
repo/packages/example/src
```

run:

```bash
mypi paths --json
mypi sync
```

The reported `project_root` must be the devenv repository root, not the subdirectory.

## 14. Documentation requirements

### Requirement R-033: Rewrite README around consumer usage

The README should stop being a placeholder and should document:

- what `mypi-agent` is
- how to import it from `devenv.yaml`
- whether import auto-enables `piAgent`
- how to run `mypi sync`
- how to run `mypi doctor`
- how to launch Pi through `mypi agent`
- how npm/Node are provided
- where generated files live
- what to commit/ignore
- how to pin the input
- how to override `piAgent.root`
- how to disable shell bootstrap
- how to troubleshoot npm/Pi install failures

### Requirement R-034: Rewrite `AGENTS.md`

Current `AGENTS.md` is Allium-specific. It should be rewritten for this repository.

It should say:

- this repo provides a repo-scoped MYPI/Pi agent bootstrap module
- public import must stay free of development-only dependencies
- `allium-env` is development-only
- all user-facing runtime commands should go through `mypi`
- Nix/devenv fixtures are contract tests
- generated file policy must be respected

### Requirement R-035: Add a LICENSE file

`pyproject.toml` and the Nix package metadata both claim MIT licensing, but the repository does not include a `LICENSE` file. Add the license file.

## 15. Proposed target repository layout

Recommended layout after refactor:

```text
.
├── devenv.nix                     # public import surface: imports ./modules/pi-agent.nix
├── devenv.yaml                    # public input metadata only, no allium-env
├── modules/
│   └── pi-agent.nix               # actual module
├── packages/
│   ├── mypi-agent-cli.nix
│   └── pi-coding-agent.nix        # optional preferred Nix-packaged Pi
├── src/
│   └── mypi_agent/
├── tests/
│   ├── fixtures/devenv/
│   │   ├── yaml-import-only/
│   │   ├── custom-root/
│   │   └── preserve-local-edits/
│   └── integration/
├── dev/
│   ├── devenv.nix                 # private development environment
│   └── devenv.yaml                # may import allium-env
├── README.md
├── AGENTS.md
└── LICENSE
```

If `devenv.yaml` at root is needed for public consumers, it must not import `allium-env`. The `dev/devenv.yaml` can import `allium-env` for local library development.

## 16. Proposed `modules/pi-agent.nix` option set

The module should evolve toward this option shape:

```nix
options.piAgent = {
  enable = lib.mkEnableOption "repo-scoped MYPI/Pi agent tooling";

  root = lib.mkOption {
    type = lib.types.str;
    default = ".agents/pi";
    description = "Project-relative root for MYPI/Pi agent artifacts.";
  };

  nodePackage = lib.mkOption {
    type = lib.types.package;
    default = pkgs.nodejs_22;
    description = "Node.js package used for npm-based Pi installation and package operations.";
  };

  piPackageName = lib.mkOption {
    type = lib.types.str;
    default = "@earendil-works/pi-coding-agent";
    description = "npm package name for Pi when runtime npm installation is used.";
  };

  piPackageVersion = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    description = "Pinned Pi package version. Required for reproducible runtime npm installs.";
  };

  bootstrap.mode = lib.mkOption {
    type = lib.types.enum [ "first_entry_only" "manual_only" "every_entry" ];
    default = "first_entry_only";
    description = "Bootstrap sync policy on shell entry.";
  };

  exposePiAgentShim = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Expose a compatibility pi-agent command in addition to mypi.";
  };
};
```

## 17. Proposed implementation sequence

### Phase 1: Correct the public import contract

1. Replace root `devenv.nix` with a thin import of `./modules/pi-agent.nix`.
2. Move current development shell to `dev/devenv.nix` and `dev/devenv.yaml`.
3. Ensure no `allium-env` is present in root public import path.
4. Add the YAML import-only fixture.
5. Update README with the target consumer import snippet.

Exit criteria:

- A temp consumer repo can import `mypi-agent` with `imports: - mypi-agent`.
- `allium-env` is not evaluated in that consumer repo.
- `mypi` appears on `PATH`.

### Phase 2: Provide Node/npm through the module

1. Add `piAgent.nodePackage` option.
2. Add Node/npm package to shell packages.
3. Add repo-local npm configuration.
4. Update `mypi doctor` to check node/npm.
5. Update fixture verification tasks to assert `node` and `npm` availability.

Exit criteria:

- Consumer shell has `node` and `npm` without declaring them separately.
- `mypi sync` no longer skips Pi installation because the module forgot npm.

### Phase 3: Make Pi installation deterministic

1. Add `piPackageName` and `piPackageVersion` options.
2. Prefer or plan a Nix-packaged Pi derivation.
3. Record package/version/source identity in manifest and state.
4. Add fake npm tests that verify exact install arguments.

Exit criteria:

- Sync records exactly what was installed.
- Runtime install does not silently float versions unless explicitly configured to do so.

### Phase 4: Fix CLI and sync safety

1. Add `mypi agent`.
2. Remove or rename misleading `mypi run`.
3. Make `--diff` read-only.
4. Merge settings instead of overwriting.
5. Add schema validation for manifest.
6. Add atomic writes and truthful overwrite reporting.

Exit criteria:

- `mypi doctor` fails when Pi is not actually usable.
- `mypi sync --diff` produces no filesystem changes.
- user-owned Pi settings are preserved.

### Phase 5: Harden project-root behavior

1. Set `MYPI_PROJECT_ROOT` in the Nix wrapper.
2. Add root discovery fallback.
3. Reject unmanaged directories by default.
4. Add subdirectory invocation tests.

Exit criteria:

- Running `mypi` from nested directories still targets the repo root.
- Running outside a devenv project fails with a clear error.

## 18. Acceptance checklist

The refactor is complete when all of the following are true:

- [ ] Root `devenv.nix` imports `./modules/pi-agent.nix` and does not configure `allium`.
- [ ] `allium-env` exists only in a private development environment, not the public import path.
- [ ] A consumer can use `devenv.yaml` with `imports: - mypi-agent`.
- [ ] The consumer receives `mypi` on `PATH`.
- [ ] The consumer receives `node` and `npm` on `PATH` when Pi runtime npm install is enabled.
- [ ] npm cache/prefix are project-local by default.
- [ ] `mypi sync --trigger shell` can install or provision Pi.
- [ ] `mypi doctor` fails if Pi is missing or unusable.
- [ ] `mypi agent` launches Pi or forwards arguments to Pi.
- [ ] `mypi sync --diff` is read-only.
- [ ] `.pi/settings.json` repair merges MYPI-owned keys and preserves user settings.
- [ ] manifest validation uses a real schema.
- [ ] state records exact Pi package/version/source identity.
- [ ] `mypi` discovers the project root instead of using arbitrary `cwd`.
- [ ] integration tests skip cleanly if `devenv` is unavailable.
- [ ] fixture tests cover the real YAML import path.
- [ ] README documents consumer setup and generated file policy.
- [ ] `AGENTS.md` no longer describes Allium as the project contract.
- [ ] `LICENSE` exists and matches project metadata.

## 19. Key design decision

The key decision is to treat this repository as two separate things:

1. **The public MYPI module library** consumed by downstream devenv projects.
2. **The private MYPI library development environment** used to build and test that library.

The public module library must be minimal, predictable, and self-contained. It should import `pi-agent.nix`, configure `mypi`, configure Node/npm support needed by Pi, and avoid bringing along unrelated development dependencies.

The private development environment can keep `allium-env`, Python venvs, local helper scripts, and development tooling. It must not leak into consumer repositories.

That split is the central refactor. Most other changes are hardening work required to make the module safe, reproducible, and testable.
