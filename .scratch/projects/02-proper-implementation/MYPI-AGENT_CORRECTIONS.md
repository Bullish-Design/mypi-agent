# MYPI-AGENT Corrections

Date: 2026-05-29

## Executive summary

The current import-bootstrap implementation plan should be corrected before implementation. The plan has the right high-level goal—make `MYPI-AGENT` reusable from other devenv projects—but it uses the wrong primary import mechanism for the revised scope and exposes the wrong command surface.

The corrected scope is:

1. `MYPI-AGENT` only needs to support projects that are managed by `devenv.nix`.
2. A consuming project may still use `devenv.yaml` for inputs and locking, because that is how devenv provides external inputs to `devenv.nix`.
3. All project configuration for `MYPI-AGENT` must live in the consuming project's `devenv.nix`.
4. All user-facing CLI commands must be subcommands of `mypi`.
5. No `pi-agent-sync`, `pi-agent-doctor`, or separate `pi-agent` command should be part of the accepted public interface.
6. The repo should include reusable devenv fixture projects under tests so import behavior can be evaluated in a temporary directory.

The most important correction is to stop relying on `devenv.yaml imports` as the primary module-loading mechanism. For this project, the consumer should declare the repo as a devenv input and import the module from inside `devenv.nix`:

```yaml
# devenv.yaml
inputs:
  mypi-agent:
    url: github:090l060/mypi-agent
    flake: false
```

```nix
# devenv.nix
{ inputs, ... }:

{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent.enable = true;
}
```

This keeps the project in the devenv module system, avoids accidentally importing the library repo's own development environment, and ensures the consuming repo controls `piAgent.*` from `devenv.nix`.

---

## Source basis

This correction document is based on:

- The attached `mypi-agent_v001` repository.
- The current `IMPORT_BOOTSTRAP_V1_IMPLEMENTATION_MAPPING.md` plan.
- The current Python CLI implementation under `src/mypi_agent`.
- The current tests under `tests/integration`.
- Current devenv documentation for inputs, imports, remote composition, tasks, and test workflows.
- Current Pi documentation for project settings and package/resource loading.

Local verification performed:

```text
PYTHONPATH=src pytest -q
```

Result:

```text
20 passed
```

That confirms the current Python-level behavior, but it does not validate imported devenv behavior. The repo currently has no fixture that creates an external devenv project and imports `MYPI-AGENT` as a consumer would.

---

## Finding 1: the plan uses the wrong primary import model for the desired scope

### Current plan

The implementation plan says to add:

```text
flake.nix
  devenvModules.default = import ./modules/pi-agent.nix;
```

and then expects a consumer to get the module through:

```yaml
imports:
  - mypi-agent
```

### Why this needs to be fixed

`devenv.yaml` imports are for importing `devenv.nix` and, for local imports, `devenv.yaml` configurations. The documented `imports` option is a list of relative paths, absolute paths, or input references to import `devenv.nix` and `devenv.yaml` files. A flake output named `devenvModules.default` is not the same thing as a `devenv.yaml imports` target.

Remote polyrepo imports merge the imported project's `devenv.nix` into the consumer. That means importing `mypi-agent` at the top level would import whatever the root `devenv.nix` contains. In this repo, the root `devenv.nix` is currently a development shell for building and checking this repository itself. It includes Allium, Python tooling, `hello`, `allium-check`, `allium-analyse`, and `install-allium-codex-skills`. Those are not consumer-facing MYPI runtime features.

If consumers import the repo root, they will inherit repo-development tools and scripts that should remain internal to the `mypi-agent` repo.

### Correct fix

Use the consuming project's `devenv.nix` as the import boundary. Keep `devenv.yaml` only for declaring the `mypi-agent` input.

Consumer pattern:

```yaml
# devenv.yaml
inputs:
  mypi-agent:
    url: github:090l060/mypi-agent
    flake: false
```

```nix
# devenv.nix
{ inputs, ... }:

{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    root = ".agents/pi";
    bootstrap.mode = "first_entry_only";
  };
}
```

This works with the intended scope because devenv inputs are passed into `devenv.nix`, and the consumer can import a concrete module path from the input. It also avoids relying on remote `devenv.yaml` import behavior.

### Implementation action

Update the implementation plan from this:

```text
Add flake.nix module export and expect imports: [ mypi-agent ].
```

to this:

```text
Add modules/pi-agent.nix as the importable module.
Consumers add the repo as a devenv.yaml input.
Consumers import inputs.mypi-agent + "/modules/pi-agent.nix" from their own devenv.nix.
```

A `flake.nix` can still be added later for flake-oriented users, but it must not be the primary path for this repo-scoped devenv integration.

---

## Finding 2: the root `devenv.nix` is currently a repo-development shell, not a consumer module

### Current repo state

The current root `devenv.nix` defines:

- A pinned Allium binary derivation.
- `pkgs.git`, `pkgs.uv`, and `allium` packages.
- Python 3.13 with uv-enabled virtualenv support.
- `scripts.hello`.
- `scripts.allium-check`.
- `scripts.allium-analyse`.
- `scripts.install-allium-codex-skills`.
- A simple `enterShell` greeting and Git version output.

This is appropriate for developing the `mypi-agent` repository itself.

### Why this needs to be fixed

A reusable module repo needs a clean boundary between:

1. The library's own development environment.
2. The module imported by downstream projects.

If downstream projects import the repo root, they inherit all of the repo's development-only configuration. That makes the consumer environment noisy and unpredictable. It also makes testing misleading, because a successful import may simply mean the library's own dev shell evaluated, not that the actual `piAgent.*` module works correctly.

### Correct fix

Keep the current root `devenv.nix` for self-development if desired, but do not instruct consumers to import it. Consumers should import only:

```nix
(inputs.mypi-agent + "/modules/pi-agent.nix")
```

The repo should be organized like this:

```text
mypi-agent/
├── devenv.nix                         # self-development environment only
├── devenv.yaml                        # self-development inputs only
├── modules/
│   └── pi-agent.nix                   # consumer module
├── packages/
│   └── mypi-agent-cli.nix             # package exposing `mypi`
├── src/mypi_agent/                    # Python CLI/runtime
├── tests/
│   ├── integration/
│   └── fixtures/
│       └── devenv/
│           ├── basic/
│           ├── custom-root/
│           └── preserve-local-edits/
└── .scratch/
```

### Implementation action

Create `modules/pi-agent.nix` and make it independent of the root development environment. It must not import or depend on `scripts.allium-*`, `env.GREET`, or any local development-only behavior.

---

## Finding 3: the command surface is wrong; everything must go through `mypi`

### Current plan

The implementation plan exposes:

```text
pi-agent-sync -> bootstrap/sync.sh
pi-agent-doctor -> bootstrap/doctor.sh
```

The concept/spec material also uses mixed naming: some sections refer to `mypi`, while others refer to `pi-agent` or `pi-agent-*`.

### Current repo state

The Python package already declares:

```toml
[project.scripts]
mypi = "mypi_agent.cli:main"
```

The implemented Typer CLI currently has these commands:

```text
mypi sync
mypi doctor
mypi run
```

### Why this needs to be fixed

The user-facing contract should be stable before implementation. If the repo exposes both `mypi` and `pi-agent-*`, downstream scripts, docs, tests, and workflows will diverge quickly.

The revised requirement is explicit: all CLI commands must be called from `mypi`.

### Correct fix

Do not add `pi-agent-sync`, `pi-agent-doctor`, or a standalone `pi-agent` command.

The accepted CLI surface should be:

```text
mypi sync
mypi doctor
mypi run
```

Additional commands can be added later, but they must remain under `mypi`, for example:

```text
mypi diff
mypi repair
mypi packages list
mypi packages sync
mypi bootstrap status
```

### Implementation action

Replace every planned shell command with a `mypi` invocation:

```text
Old: pi-agent-sync --trigger shell
New: mypi sync --trigger shell

Old: pi-agent-doctor --json
New: mypi doctor --json
```

Update all specs, tests, scripts, README examples, and Allium plans to use `mypi` consistently.

---

## Finding 4: the current CLI does not yet support the full planned behavior

### Current repo state

The current CLI has:

```text
mypi sync [--repair-shim]
mypi doctor
mypi run
```

The current implementation does not yet include:

- `mypi sync --trigger shell`.
- `mypi sync --json`.
- `mypi doctor --json`.
- Bootstrap state read/write.
- Drift report generation.
- Package reconciliation.
- Machine-readable diagnostics output.

### Why this needs to be fixed

The implementation plan describes first-entry shell bootstrap, diagnostics, drift reporting, and package reconciliation. Those behaviors cannot be cleanly driven from devenv tasks unless the `mypi` CLI exposes enough flags for scripted invocation.

The first-entry task should not depend on private shell scripts such as `bootstrap/sync.sh`. The module should invoke the same public command a user can invoke manually:

```text
mypi sync --trigger shell
```

### Correct fix

Extend the CLI while preserving the existing commands:

```text
mypi sync
  --trigger manual|shell
  --repair-shim
  --json

mypi doctor
  --json

mypi run
```

Suggested Typer model:

```python
@app.command("sync")
def sync_command(
    trigger: str = typer.Option("manual", "--trigger"),
    repair_shim: bool = typer.Option(False, "--repair-shim"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    ...

@app.command("doctor")
def doctor_command(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    ...
```

### Implementation action

Add tests for:

```text
mypi sync --trigger shell
mypi sync --json
mypi doctor --json
```

Then update the devenv module to call only `mypi sync --trigger shell` from bootstrap automation.

---

## Finding 5: the module must package and expose the real Python CLI, not ad hoc shell scripts

### Current plan

The plan creates shell scripts:

```text
bootstrap/sync.sh
bootstrap/doctor.sh
```

and exposes those as shell commands.

### Why this needs to be fixed

The repo already has a Python package and a Python CLI. If the devenv module exposes separate shell scripts, behavior will split into two implementations:

1. Python behavior used by tests and direct CLI usage.
2. Shell-script behavior used by imported devenv projects.

That would make drift inevitable.

### Correct fix

The imported devenv module should package the Python application and put the `mypi` executable on PATH.

Skeleton direction:

```nix
# packages/mypi-agent-cli.nix
{ pkgs, lib, ... }:

pkgs.python313Packages.buildPythonApplication {
  pname = "mypi-agent";
  version = "0.1.0";
  src = ../.;
  pyproject = true;

  build-system = [ pkgs.python313Packages.hatchling ];

  dependencies = with pkgs.python313Packages; [
    pydantic
    typer
  ];
}
```

Then in `modules/pi-agent.nix`:

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.piAgent;
  mypi = pkgs.callPackage ../packages/mypi-agent-cli.nix { };
in
{
  options.piAgent.enable = lib.mkEnableOption "MYPI-AGENT";

  config = lib.mkIf cfg.enable {
    packages = [ mypi ];
  };
}
```

### Implementation action

Use the packaged Python CLI as the single source of truth. Any bootstrap shell logic that remains should be thin wrapper logic inside the Nix module or a `mypi` subcommand, not a parallel implementation.

---

## Finding 6: the `.pi/settings.json` shim is not currently Pi-compatible enough

### Current repo state

The current `run_sync` writes this file when missing:

```json
{
  "agent_root": "../.agents/pi"
}
```

### Why this needs to be fixed

Pi's documented project settings are loaded from `.pi/settings.json`. They include resource settings such as `packages`, `extensions`, `skills`, `prompts`, and `themes`. Paths in project settings resolve relative to `.pi/settings.json`'s directory, namely `.pi`.

A custom key like `agent_root` may be useful for `MYPI-AGENT` metadata, but it does not by itself tell Pi where to load packages, skills, prompts, themes, or extensions.

### Correct fix

Generate project settings that Pi can actually consume.

Default generated `.pi/settings.json` should be closer to:

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

If `piAgent.packages` is declared in `devenv.nix`, render those declarations into Pi's `packages` array using Pi's accepted npm/git package source forms.

Example:

```nix
piAgent.packages = [
  {
    source = "npm:@org/pi-tools@1.2.3";
  }
  {
    source = "git:github.com/org/pi-tools?rev=abc123";
    skills = [ "review" "plan" ];
    extensions = [ ];
  }
];
```

Rendered settings:

```json
{
  "packages": [
    "npm:@org/pi-tools@1.2.3",
    {
      "source": "git:github.com/org/pi-tools?rev=abc123",
      "skills": ["review", "plan"],
      "extensions": []
    }
  ],
  "extensions": ["../.agents/pi/extensions"],
  "skills": ["../.agents/pi/skills"],
  "prompts": ["../.agents/pi/prompts"],
  "themes": ["../.agents/pi/themes"],
  "enableSkillCommands": true
}
```

### Implementation action

Replace the current shim renderer with a Pi settings renderer. Keep `agent_root` only if it is namespaced to avoid collision, for example:

```json
{
  "x-mypi-agent": {
    "agentRoot": "../.agents/pi"
  }
}
```

But the operational Pi fields must still be present.

---

## Finding 7: the manifest path/name is inconsistent

### Current plan

The plan refers to:

```text
.agents/pi/manifest.json
```

### Current repo state

The current Python model uses:

```text
.agents/pi/installed.json
```

### Why this needs to be fixed

The manifest is part of the contract. If docs, tests, and code disagree about its path, fixture tests may pass while real consumers fail.

The current `installed.json` also contains only:

```json
{
  "schema_version": 1,
  "primitives": []
}
```

That is not enough to represent bootstrap state, package state, diagnostics, or drift.

### Correct fix

Use a stable file layout:

```text
.agents/pi/
├── manifest.json
├── extensions/
├── skills/
├── prompts/
├── themes/
└── .state/
    ├── bootstrap.json
    ├── diagnostics.jsonl
    ├── drift-report.json
    └── installed-packages.json
```

Recommended meanings:

- `manifest.json`: human-reviewable MYPI agent-root manifest.
- `.state/bootstrap.json`: first-entry bootstrap state.
- `.state/diagnostics.jsonl`: append-only run diagnostics.
- `.state/drift-report.json`: latest drift report.
- `.state/installed-packages.json`: resolved package state if MYPI does any package reconciliation beyond Pi's own package manager.

### Implementation action

Change `Paths.manifest_path` from:

```python
return self.agent_root / "installed.json"
```

to:

```python
return self.agent_root / "manifest.json"
```

Add separate path properties for state files.

---

## Finding 8: package reconciliation should align with Pi package behavior

### Current plan

The plan proposes directly installing packages into:

```text
.agents/pi/packages/<name>
```

for npm, git, and local-path packages.

### Why this needs to be fixed

Pi already has package/resource concepts. It supports project settings in `.pi/settings.json`, package declarations, npm/git package sources, and project-local package install behavior. For pinned npm specs and pinned git refs, Pi can be the package resolver and installer.

If `MYPI-AGENT` separately installs packages into `.agents/pi/packages`, it risks building a second package manager that diverges from Pi's own behavior.

### Correct fix

For v1, `MYPI-AGENT` should render declared package intent into `.pi/settings.json` and let Pi reconcile package installation at startup or via Pi's package commands.

Use MYPI state only for:

- Declared-vs-rendered diffing.
- Drift reporting.
- Doctor checks.
- Optional repair of generated local resource directories.

Do not implement a full npm/git package manager in v1 unless Pi lacks a required feature.

### Implementation action

Change `piAgent.packages` from the current custom shape:

```nix
{
  name = "...";
  sourceKind = "npm";
  sourceRef = "...";
  declaredVersion = "...";
  desiredState = "installed";
}
```

to a Pi-centered shape:

```nix
{
  source = "npm:@org/pkg@1.2.3";
  skills = [ "skill-a" ];
  extensions = [ ];
  prompts = [ ];
  themes = [ ];
  desiredState = "present";
}
```

Then render directly into settings. A future package-reconcile engine can be added only after fixture tests show what Pi does and does not handle.

---

## Finding 9: bootstrap should be a devenv task, not raw `enterShell` logic

### Current plan

The plan says to run bootstrap logic directly inside `enterShell`.

### Why this needs to be fixed

`enterShell` works for simple messages and basic hooks, but bootstrap has state, status, idempotence, and failure behavior. devenv tasks are better suited for this because they provide explicit task names, ordering, and `status` checks.

Tasks can also be run directly:

```text
devenv tasks run mypi:bootstrap
```

That makes testing and debugging easier.

### Correct fix

The module should register a task and attach it to shell entry when bootstrap mode requires it.

Skeleton:

```nix
{ config, lib, ... }:

let
  cfg = config.piAgent;
in
{
  config = lib.mkIf cfg.enable {
    tasks."mypi:bootstrap" = {
      before = lib.mkIf (cfg.bootstrap.mode != "manual_only") [ "devenv:enterShell" ];
      exec = ''
        set -euo pipefail
        cd "$DEVENV_ROOT"
        mypi sync --trigger shell
      '';
      status = lib.mkIf (cfg.bootstrap.mode == "first_entry_only") ''
        test -f "$DEVENV_ROOT/${cfg.bootstrap.stateFile}" \
          && ${config.packages.jq or "jq"} -e '.status == "completed"' \
            "$DEVENV_ROOT/${cfg.bootstrap.stateFile}" >/dev/null
      '';
    };
  };
}
```

The exact `jq` wiring should be implemented with a real package reference, not the pseudo-expression above. The important correction is the task shape: public command, explicit status check, and no parallel shell script behavior.

### Implementation action

Implement `tasks."mypi:bootstrap"` and update tests to verify it runs in a fixture project.

---

## Finding 10: the module options need to be narrowed for v1

### Current plan

The proposed options are:

```text
piAgent.enable
piAgent.root
piAgent.bootstrap.mode
piAgent.bootstrap.stateFile
piAgent.packages[].name
piAgent.packages[].sourceKind
piAgent.packages[].sourceRef
piAgent.packages[].declaredVersion
piAgent.packages[].desiredState
```

### Why this needs to be fixed

The options mix MYPI state management with a custom package manager. That is too much for the first importable module and overlaps with Pi package settings.

### Correct fix

Start with a smaller, Pi-compatible option set:

```nix
piAgent = {
  enable = true;

  root = ".agents/pi";

  bootstrap = {
    mode = "first_entry_only"; # first_entry_only | manual_only | every_entry
    stateFile = ".agents/pi/.state/bootstrap.json";
  };

  resources = {
    extensions = [ ];
    skills = [ ];
    prompts = [ ];
    themes = [ ];
  };

  packages = [
    # string source form or object form
  ];

  settings = {
    enableSkillCommands = true;
  };
};
```

Use the Nix module to render a desired-state JSON file or environment variable for `mypi sync`, but keep Pi-specific package semantics in Pi's settings format.

### Implementation action

Write `modules/pi-agent.nix` with this smaller contract first. Add package reconciliation later only if there is a fixture proving the missing behavior.

---

## Finding 11: the current tests do not evaluate imported devenv behavior

### Current repo state

The current tests validate:

- Python model fields.
- Sync file creation.
- Doctor checks.
- Typer CLI behavior.
- Allium contract field presence.

They do not validate:

- That a separate project can import `modules/pi-agent.nix`.
- That `mypi` is available inside a consumer devenv shell.
- That the first-entry bootstrap task works.
- That generated `.pi/settings.json` is Pi-compatible.
- That local edits are preserved in a real consumer repo.

### Why this needs to be fixed

The main risk in this plan is not the Python code. The main risk is the boundary between:

```text
consumer devenv.nix -> imported module -> packaged mypi CLI -> generated project files
```

That boundary must be tested by creating a real temporary consumer project and running devenv against it.

### Correct fix

Add fixture projects under the repo:

```text
tests/fixtures/devenv/
├── basic/
│   ├── devenv.yaml
│   └── devenv.nix
├── custom-root/
│   ├── devenv.yaml
│   └── devenv.nix
└── preserve-local-edits/
    ├── devenv.yaml
    ├── devenv.nix
    ├── .pi/settings.json
    └── .agents/pi/manifest.json
```

Each fixture should be copied to a temporary directory during tests. The fixture's `devenv.yaml` should contain a placeholder for the local path to the checked-out `mypi-agent` repo.

Example fixture `devenv.yaml`:

```yaml
inputs:
  mypi-agent:
    url: path:__MYPI_AGENT_REPO__
    flake: false
```

Example fixture `devenv.nix`:

```nix
{ inputs, ... }:

{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    root = ".agents/pi";
    bootstrap.mode = "first_entry_only";
  };

  enterTest = ''
    set -euo pipefail

    command -v mypi

    mypi sync --trigger manual

    test -f .pi/settings.json
    test -f .agents/pi/manifest.json
    test -d .agents/pi/skills
    test -d .agents/pi/extensions
    test -d .agents/pi/prompts
    test -d .agents/pi/themes

    mypi doctor
  '';
}
```

Then add a Python integration test that copies the fixture to a temp directory, rewrites the placeholder, and runs `devenv test`.

Example test skeleton:

```python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "devenv"


def _require_devenv() -> None:
    if shutil.which("devenv") is None:
        pytest.skip("devenv is not installed in this test environment")


def _materialize_fixture(name: str, tmp_path: Path) -> Path:
    src = FIXTURES / name
    dst = tmp_path / name
    shutil.copytree(src, dst)

    yaml_path = dst / "devenv.yaml"
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8").replace(
            "__MYPI_AGENT_REPO__",
            str(ROOT),
        ),
        encoding="utf-8",
    )
    return dst


@pytest.mark.integration_devenv
def test_basic_devenv_consumer_fixture(tmp_path: Path) -> None:
    _require_devenv()
    project = _materialize_fixture("basic", tmp_path)

    result = subprocess.run(
        ["devenv", "test"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
```

### Implementation action

Add fixture tests as soon as `modules/pi-agent.nix` exists. Mark them so they can be skipped in environments without devenv, but run them in any environment where devenv is available.

---

## Required fixture coverage

### Fixture 1: `basic`

Purpose: prove a clean external devenv project can import the module and call `mypi`.

Assertions:

```text
command -v mypi succeeds
mypi sync succeeds
mypi doctor succeeds after sync
.pi/settings.json exists
.agents/pi/manifest.json exists
resource directories exist
```

### Fixture 2: `custom-root`

Purpose: prove the configured root works and generated Pi paths remain valid.

`devenv.nix`:

```nix
piAgent = {
  enable = true;
  root = ".custom/mypi";
};
```

Assertions:

```text
.custom/mypi/manifest.json exists
.pi/settings.json points to ../.custom/mypi/... paths
mypi doctor succeeds
```

### Fixture 3: `preserve-local-edits`

Purpose: prove sync preserves existing user-edited settings and reports drift instead of silently overwriting.

Pre-existing fixture files:

```text
.pi/settings.json
.agents/pi/manifest.json
```

Assertions:

```text
mypi sync does not overwrite local edits
mypi sync --json reports drift
mypi sync --repair-shim repairs only when explicitly requested
```

### Fixture 4: `bootstrap-task`

Purpose: prove the devenv task path works independently of manual sync.

Assertions:

```text
devenv tasks run mypi:bootstrap succeeds
.agents/pi/.state/bootstrap.json has status completed
second run is idempotent
```

### Fixture 5: `package-settings-render`

Purpose: prove `piAgent.packages` renders into Pi-compatible project settings.

Assertions:

```text
.pi/settings.json contains declared package source strings or package objects
rendered package entries match Pi settings format
mypi doctor validates package declaration shape
```

---

## Recommended implementation sequence

### Phase 1: align docs and specs

Update these files first:

```text
.scratch/projects/01-mypi-agent-brainstorming/plans/IMPORT_BOOTSTRAP_V1_IMPLEMENTATION_MAPPING.md
.scratch/projects/01-mypi-agent-brainstorming/MYPI-AGENT_CONCEPT.md
.scratch/specs/ELICITATION.md
README.md
```

Required edits:

1. Replace `pi-agent-sync` with `mypi sync`.
2. Replace `pi-agent-doctor` with `mypi doctor`.
3. Replace `devenv.yaml imports: [ mypi-agent ]` as the primary pattern with `devenv.nix` module import from `inputs.mypi-agent`.
4. Clarify that `devenv.yaml` is used only to declare/pin inputs.
5. Clarify that imported projects configure `MYPI-AGENT` in `devenv.nix`.

### Phase 2: add the importable module

Create:

```text
modules/pi-agent.nix
packages/mypi-agent-cli.nix
```

Minimum module behavior:

```nix
{
  options.piAgent.enable = ...;
  options.piAgent.root = ...;
  options.piAgent.bootstrap.mode = ...;
  options.piAgent.bootstrap.stateFile = ...;

  config = mkIf cfg.enable {
    packages = [ mypi ];
    tasks."mypi:bootstrap" = ...;
  };
}
```

### Phase 3: package the Python CLI

Package the current Python project so the imported module exposes `mypi` in the consumer shell.

Acceptance check:

```text
command -v mypi
mypi --help
mypi sync --help
mypi doctor --help
```

must work inside a fixture project.

### Phase 4: extend CLI flags

Add:

```text
mypi sync --trigger manual|shell
mypi sync --json
mypi doctor --json
```

Preserve current behavior for existing commands.

### Phase 5: fix file layout and settings rendering

Change generated layout to:

```text
.pi/settings.json
.agents/pi/manifest.json
.agents/pi/extensions/
.agents/pi/skills/
.agents/pi/prompts/
.agents/pi/themes/
.agents/pi/.state/bootstrap.json
```

Render Pi-compatible settings fields.

### Phase 6: add fixture-based devenv tests

Add the fixture directories under:

```text
tests/fixtures/devenv/
```

Add integration tests that copy those fixtures into temp directories and run `devenv test`.

### Phase 7: add drift and repair semantics

Only after the import path is proven, add:

```text
drift-report.json
diagnostics.jsonl
mypi sync --repair-shim
mypi doctor --json
```

---

## Updated acceptance criteria

The corrected implementation is acceptable when all of the following pass.

### Python unit/integration tests

```text
PYTHONPATH=src pytest -q
```

Expected:

```text
all tests pass
```

### External fixture import test

A temp project copied from `tests/fixtures/devenv/basic` can run:

```text
devenv test
```

Expected:

```text
command -v mypi succeeds
mypi sync succeeds
mypi doctor succeeds
.pi/settings.json exists
.agents/pi/manifest.json exists
```

### CLI surface test

Inside the fixture project:

```text
mypi --help
mypi sync --help
mypi doctor --help
mypi run --help
```

Expected:

```text
all commands exist under mypi
no pi-agent-sync command is required
no pi-agent-doctor command is required
```

### Bootstrap task test

Inside the fixture project:

```text
devenv tasks run mypi:bootstrap
```

Expected:

```text
.agents/pi/.state/bootstrap.json exists
bootstrap status is completed
re-running the task is idempotent
```

### Pi settings compatibility test

Generated `.pi/settings.json` must contain Pi-recognized resource fields:

```json
{
  "packages": [],
  "extensions": ["../.agents/pi/extensions"],
  "skills": ["../.agents/pi/skills"],
  "prompts": ["../.agents/pi/prompts"],
  "themes": ["../.agents/pi/themes"]
}
```

Expected:

```text
paths resolve from .pi
resource directories exist
package entries match Pi settings syntax
```

---

## Concrete corrected consumer example

### `devenv.yaml`

```yaml
inputs:
  mypi-agent:
    url: github:090l060/mypi-agent
    flake: false
```

### `devenv.nix`

```nix
{ inputs, ... }:

{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    root = ".agents/pi";

    bootstrap = {
      mode = "first_entry_only";
      stateFile = ".agents/pi/.state/bootstrap.json";
    };

    resources = {
      extensions = [ ];
      skills = [ ];
      prompts = [ ];
      themes = [ ];
    };

    packages = [ ];
  };
}
```

### Expected user commands

```text
mypi sync
mypi doctor
mypi run
```

### Expected devenv command

```text
devenv tasks run mypi:bootstrap
```

---

## Specific edits to `IMPORT_BOOTSTRAP_V1_IMPLEMENTATION_MAPPING.md`

Replace section 1 with:

```text
## 1. File plan

- modules/pi-agent.nix
  - Define options.piAgent.*
  - Package and expose the `mypi` CLI
  - Register `tasks."mypi:bootstrap"`
  - Render desired-state JSON for `mypi sync`

- packages/mypi-agent-cli.nix
  - Build the Python application from pyproject.toml
  - Expose one binary: `mypi`

- src/mypi_agent/cli.py
  - Provide `mypi sync`, `mypi doctor`, and `mypi run`
  - Add `--json` support where needed
  - Add `--trigger manual|shell` to sync

- src/mypi_agent/sync.py
  - Materialize root files
  - Render Pi-compatible `.pi/settings.json`
  - Preserve local edits by default
  - Write bootstrap state, diagnostics, and drift reports

- src/mypi_agent/doctor.py
  - Validate generated layout
  - Validate Pi settings shape
  - Validate drift and diagnostics
  - Support human and JSON output

- tests/fixtures/devenv/*
  - Provide external devenv consumer projects
  - Exercise import behavior in temp directories
```

Replace command references:

```text
pi-agent-sync     -> mypi sync
pi-agent-doctor   -> mypi doctor
pi-agent          -> mypi, only if this refers to MYPI's wrapper CLI
```

Replace consumer import instructions:

```text
Do not document `imports: [ mypi-agent ]` as the main path.
Document `devenv.nix` imports from `inputs.mypi-agent + "/modules/pi-agent.nix"`.
```

---

## Notes on `devenv.yaml` versus `devenv.nix`

The corrected approach still uses `devenv.yaml`, but only for what `devenv.yaml` is best at here: declaring and locking inputs.

The actual module import and all project-specific MYPI configuration happen in `devenv.nix`.

That distinction matters:

- `devenv.yaml` inputs are passed into the `devenv.nix` function.
- Remote project imports merge the imported project's `devenv.nix`.
- Remote imported `devenv.yaml` is not evaluated in the same way local `devenv.yaml` imports are.
- Importing the repo root would merge the repo's own development environment unless the consumer imports only the module path from `devenv.nix`.

This is why the corrected import boundary is:

```nix
imports = [ (inputs.mypi-agent + "/modules/pi-agent.nix") ];
```

not:

```yaml
imports:
  - mypi-agent
```

---

## Documentation references

- devenv `devenv.yaml` reference: `imports` is a list of paths or input references to import `devenv.nix` and `devenv.yaml` files.  
  https://devenv.sh/reference/yaml-options/

- devenv inputs: inputs declared in `devenv.yaml` are passed as arguments to `devenv.nix`.  
  https://devenv.sh/inputs/

- devenv composing/imports: local `devenv.yaml` imports are supported, but remote `devenv.yaml` imports are not evaluated the same way.  
  https://devenv.sh/composing-using-imports/

- devenv polyrepo guide: importing a remote project merges its `devenv.nix`; remote repositories must use `devenv.nix` only for that import path.  
  https://devenv.sh/guides/polyrepo/

- devenv tasks: tasks can be explicitly run and can use repository-root-aware behavior.  
  https://devenv.sh/tasks/

- devenv getting started: `devenv test` is the appropriate command for validating a developer environment in CI-like checks.  
  https://devenv.sh/getting-started/

- Pi settings: project settings are stored in `.pi/settings.json`, with project settings overriding global settings.  
  https://pi.dev/docs/latest/settings

- Pi resource settings: `packages`, `extensions`, `skills`, `prompts`, and `themes` are documented resource fields, and project-setting paths resolve relative to `.pi`.  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md

- Pi packages: project settings can contain package declarations, and project packages can be shared with a team.  
  https://pi.dev/docs/latest/packages
