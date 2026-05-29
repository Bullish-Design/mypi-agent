# MYPI-AGENT Concept

**Status:** Concept and implementation blueprint  
**Date:** 2026-05-29  
**Target repository:** `pi-agent-devenv` / `mypi-agent`  
**Primary consumer:** Linux development repositories managed with `devenv.sh`  
**Primary goal:** Provide a minimal, reproducible, importable foundation for using Pi Coding Agent across repos, while keeping each repo's agent configuration editable and bootstrap-friendly.

---

## 1. Executive summary

`MYPI-AGENT` is a small Nix/devenv module repository that can be imported into any repository managed by `devenv.sh`. It installs and wires up the Pi Coding Agent runtime, creates a minimal project-local Pi configuration, and materializes an editable hidden agent root inside the consuming repository.

The module is deliberately minimal. It should not try to predefine a full agent operating system. Its role is to create a reliable foundation that each repo can extend declaratively and then evolve locally with help from the agent itself.

The default model is:

1. A project imports the module through `devenv.yaml`.
2. Project-specific options live in that repo's `devenv.nix`.
3. On first shell entry, the module bootstraps missing files only.
4. Generated files are committed and editable.
5. Local changes are preserved.
6. Upgrades are explicit and version-aware.
7. Secrets are never written into generated configuration.

Recommended default hidden root:

```text
.agents/pi
```

Recommended Pi compatibility shim:

```text
.pi/settings.json
```

The `.pi/settings.json` file remains small and points Pi at the configurable root under `.agents/pi`.

---

## 2. Goals

### 2.1 Primary goals

- Create an importable Nix/devenv module repo.
- Allow any Linux project using `devenv.sh` and `devenv.nix` to enable Pi with minimal configuration.
- Materialize visible, editable agent configuration files inside the consuming repo.
- Support per-repo custom hidden roots, including non-root-level paths such as `.agents/pi`.
- Preserve local changes after initial bootstrap.
- Version core primitives individually.
- Keep the initial primitive set absolutely minimal.
- Support future growth into extensions, skills, prompts, themes, Pi packages, models, and providers.
- Keep all configuration declarative where practical.
- Support private/internal Pi packages via pinned git, npm, or local paths.
- Never write API keys, OAuth tokens, or other secrets into generated config.

### 2.2 Secondary goals

- Make the generated repo-local structure understandable to both humans and agents.
- Provide diagnostic commands that can explain what was installed, where it came from, and whether local state is healthy.
- Prepare for future CI/headless support without prioritizing it initially.
- Allow mature local primitives to be promoted into shareable Pi packages later.

---

## 3. Non-goals

The first version should not:

- Provide a large bundled collection of skills or extensions.
- Attempt to manage every Pi feature through Nix immediately.
- Force all Pi packages through the Nix store.
- Overwrite user-edited files automatically.
- Store secrets in committed config.
- Depend on macOS support.
- Prioritize CI before the interactive developer shell workflow is stable.
- Require consuming repos to use flakes directly, beyond what devenv itself requires.

---

## 4. External assumptions and constraints

### 4.1 Devenv import model

The intended consumer interface relies on `devenv.yaml` inputs and imports. Devenv supports declaring Nix inputs in `devenv.yaml`, and imported devenv configurations are merged into the consuming environment.

Expected consumer `devenv.yaml`:

```yaml
inputs:
  mypi-agent:
    url: github:090l060/mypi-agent

imports:
  - mypi-agent
```

Project-specific configuration is then placed in `devenv.nix`.

### 4.2 Pi project config model

Pi's documented project-level settings are centered around a `.pi/settings.json` file in the project. Project settings can reference local paths for resources such as extensions, skills, prompt templates, and themes.

Because this project wants a configurable root such as `.agents/pi`, `MYPI-AGENT` should generate a small `.pi/settings.json` compatibility shim that points Pi to the actual chosen root.

Recommended layout:

```text
repo/
├── .pi/
│   └── settings.json
└── .agents/
    └── pi/
        ├── extensions/
        ├── skills/
        ├── prompts/
        ├── themes/
        ├── packages/
        ├── models/
        ├── providers/
        └── manifest.json
```

---

## 5. Design decision summary

| Area | Decision |
|---|---|
| Library shape | Dedicated importable Nix/devenv module repository |
| Consumer import | Simple `devenv.yaml` input/import |
| Per-repo config | Rich `piAgent.*` options in `devenv.nix` |
| Default hidden root | `.agents/pi` |
| Custom hidden root | Supported per repo |
| Pi compatibility | Generate `.pi/settings.json` shim |
| File strategy | Materialized editable files |
| Initial sync behavior | Copy missing files only |
| Local edits | Preserve by default |
| Upgrade behavior | Manual, explicit, version-aware |
| Initial primitive set | Minimal bootstrap + doctor support |
| Primitive versioning | Individual primitive registry and installed manifest |
| Resource strategy | Raw directories first, package-ready structure |
| External packages | Support pinned npm, git, and local paths |
| Pi runtime source | Prefer pinned Nix package; fallback to pinned npm/GitHub derivation |
| Secrets | Runtime-only env/SecretSpec; never write values into config |
| Platform | Linux first |
| Initial mode | Interactive shells first |
| Future mode | CI/headless support later |

---

## 6. Repository architecture

Recommended library repo structure:

```text
mypi-agent/
├── README.md
├── MYPI-AGENT_CONCEPT.md
├── flake.nix
├── devenv.nix
├── modules/
│   └── pi-agent.nix
├── packages/
│   ├── pi-agent-wrapper.nix
│   └── pi-cli.nix
├── bootstrap/
│   ├── sync.sh
│   ├── doctor.sh
│   ├── diff.sh
│   ├── paths.sh
│   └── templates/
│       ├── settings.json.tpl
│       ├── manifest.json.tpl
│       ├── gitignore.tpl
│       └── README.md.tpl
├── primitives/
│   ├── registry.json
│   └── core/
│       ├── primitive.json
│       ├── skills/
│       │   └── doctor/
│       │       └── SKILL.md
│       ├── extensions/
│       │   └── README.md
│       ├── prompts/
│       │   └── README.md
│       ├── themes/
│       │   └── README.md
│       ├── models/
│       │   └── models.example.json
│       └── providers/
│           └── README.md
└── tests/
    ├── fixture-basic/
    ├── fixture-custom-root/
    └── fixture-preserve-local-edits/
```

### 6.1 `modules/pi-agent.nix`

This file defines the `piAgent.*` options exposed to consuming repositories.

Responsibilities:

- Add Pi runtime and wrapper scripts to the dev shell.
- Render desired-state metadata for the bootstrap script.
- Configure shell entry behavior.
- Expose package and primitive options.
- Avoid reading secret values at Nix evaluation time.

### 6.2 `packages/pi-agent-wrapper.nix`

This package should provide wrapper commands:

```text
pi-agent
pi-agent-sync
pi-agent-doctor
pi-agent-diff
pi-agent-paths
```

`pi-agent` should wrap the real Pi CLI and load runtime environment files or SecretSpec-provided values without embedding secrets into Nix store outputs.

### 6.3 `bootstrap/sync.sh`

This script materializes missing project-local files.

Responsibilities:

- Create `.pi/settings.json` when missing.
- Create the configured agent root when missing.
- Copy default primitive files when absent.
- Write or update `manifest.json` conservatively.
- Preserve local changes.
- Detect available upgrades without applying them automatically.

### 6.4 `bootstrap/doctor.sh`

This script checks whether the project is correctly configured.

Checks should include:

- Pi CLI is available.
- Configured root exists.
- `.pi/settings.json` exists and points to the configured root.
- Manifest exists.
- Required directories exist.
- No generated files are unexpectedly missing.
- Required environment variables are declared but not leaked.
- Optional private package sources are accessible where possible.

---

## 7. Consumer project shape

### 7.1 Minimal consumer `devenv.yaml`

```yaml
inputs:
  mypi-agent:
    url: github:090l060/mypi-agent

imports:
  - mypi-agent
```

### 7.2 Minimal consumer `devenv.nix`

```nix
{ config, pkgs, ... }:

{
  piAgent = {
    enable = true;
  };
}
```

### 7.3 Recommended consumer `devenv.nix`

```nix
{ config, pkgs, ... }:

{
  piAgent = {
    enable = true;

    root = ".agents/pi";

    sync = {
      mode = "copy-if-missing";
      preserveLocalChanges = true;
      upgradeMode = "manual";
      autoBootstrap = true;
    };

    primitives = {
      core.enable = true;
    };

    secrets = {
      mode = "runtime";
      envFiles = [
        "~/.config/pi-agent/env"
      ];
    };
  };
}
```

### 7.4 Generated project files

After first bootstrap:

```text
repo/
├── devenv.yaml
├── devenv.nix
├── .pi/
│   └── settings.json
└── .agents/
    └── pi/
        ├── README.md
        ├── manifest.json
        ├── extensions/
        ├── skills/
        │   └── doctor/
        │       └── SKILL.md
        ├── prompts/
        ├── themes/
        ├── packages/
        ├── models/
        └── providers/
```

---

## 8. Generated `.pi/settings.json`

The `.pi/settings.json` file should remain intentionally small. Its purpose is to point Pi at the configured root.

Example for default root `.agents/pi`:

```json
{
  "extensions": [
    "../.agents/pi/extensions/**/*.ts",
    "!../.agents/pi/extensions/**/node_modules/**"
  ],
  "skills": [
    "../.agents/pi/skills/*"
  ],
  "prompts": [
    "../.agents/pi/prompts/*"
  ],
  "themes": [
    "../.agents/pi/themes/*"
  ],
  "models": "../.agents/pi/models/models.json",
  "packages": [],
  "sessionDir": "../.agents/pi/state/sessions"
}
```

Notes:

- Relative path handling should be tested against the actual Pi behavior.
- The shim should be regenerated only when missing or when explicitly synced.
- If a local user edits it, sync should preserve the edit unless an explicit repair command is used.

---

## 9. Agent root structure

Recommended default:

```text
.agents/pi/
├── README.md
├── manifest.json
├── extensions/
│   └── README.md
├── skills/
│   └── doctor/
│       └── SKILL.md
├── prompts/
│   └── README.md
├── themes/
│   └── README.md
├── packages/
│   └── README.md
├── models/
│   ├── README.md
│   └── models.example.json
├── providers/
│   └── README.md
└── state/
    ├── .gitignore
    └── sessions/
```

The root is intentionally visible in git and editable. State and cache directories should be ignored.

Recommended `.gitignore` entries:

```gitignore
.agents/pi/state/
.agents/pi/**/node_modules/
.agents/pi/**/.cache/
```

Whether `.pi/settings.json` and `.agents/pi/**` are committed should be a project policy, but the default recommendation is to commit the generated config and primitives, excluding runtime state and dependency caches.

---

## 10. Sync semantics

### 10.1 Default mode

Default sync mode:

```nix
piAgent.sync.mode = "copy-if-missing";
```

Meaning:

- Missing directories are created.
- Missing primitive files are copied.
- Existing files are not overwritten.
- Existing local edits are preserved.
- Manifest entries are created for newly installed primitives.
- Available upgrades may be reported but not applied.

### 10.2 Upgrade mode

Default upgrade mode:

```nix
piAgent.sync.upgradeMode = "manual";
```

Supported future commands:

```bash
pi-agent sync --diff
pi-agent sync --upgrade core-bootstrap
pi-agent sync --upgrade all
pi-agent sync --repair-shim
```

### 10.3 Desired-state hash

Rather than syncing only when `devenv.yaml` changes, sync should compare a desired-state hash derived from:

- Imported `mypi-agent` module version.
- Resolved primitive versions.
- Relevant `piAgent.*` options from `devenv.nix`.
- Configured root path.
- Package declarations.
- Resource filters.

This handles changes made in either `devenv.yaml` or `devenv.nix`.

### 10.4 Local change preservation

A local file should never be overwritten by default.

To support safe upgrades, the manifest should store:

```json
{
  "installed": {
    "core-doctor-skill": {
      "version": "0.1.0",
      "sourceHash": "sha256-...",
      "installedPath": "skills/doctor/SKILL.md"
    }
  }
}
```

Upgrade logic can then classify files as:

| State | Meaning | Default action |
|---|---|---|
| Missing | File not present | Copy current version |
| Unchanged | File hash matches old source | Safe to upgrade manually |
| Locally modified | File differs from old source | Preserve and report |
| Unknown | File not in manifest | Preserve |

---

## 11. Primitive model

### 11.1 Primitive definition

A primitive is the smallest versioned unit distributed by this library.

Examples:

- `core-settings-shim`
- `core-root-readme`
- `core-doctor-skill`
- `core-models-example`
- `core-provider-readme`

### 11.2 Registry

`primitives/registry.json` should define available primitives:

```json
{
  "schemaVersion": 1,
  "primitives": {
    "core-doctor-skill": {
      "version": "0.1.0",
      "type": "skill",
      "path": "core/skills/doctor",
      "default": true,
      "description": "Minimal diagnostic skill for checking MYPI-AGENT setup."
    },
    "core-models-example": {
      "version": "0.1.0",
      "type": "models",
      "path": "core/models/models.example.json",
      "default": true,
      "description": "Example models file with no secrets."
    }
  }
}
```

### 11.3 Installed manifest

Each consuming repo gets:

```text
.agents/pi/manifest.json
```

Example:

```json
{
  "schemaVersion": 1,
  "root": ".agents/pi",
  "generatedBy": "mypi-agent",
  "moduleVersion": "0.1.0",
  "desiredStateHash": "sha256-...",
  "installed": {
    "core-doctor-skill": {
      "version": "0.1.0",
      "sourceHash": "sha256-...",
      "installedAt": "2026-05-29T00:00:00Z",
      "files": [
        "skills/doctor/SKILL.md"
      ]
    }
  }
}
```

---

## 12. Raw directories now, Pi packages later

### 12.1 Initial strategy: raw directories

Use raw materialized directories first:

```text
.agents/pi/extensions
.agents/pi/skills
.agents/pi/prompts
.agents/pi/themes
.agents/pi/models
.agents/pi/providers
```

Advantages:

- Easy to inspect.
- Easy to commit.
- Easy for the agent to modify.
- Easy to bootstrap in new repos.
- Avoids early package-manager complexity.

Tradeoffs:

- The library must maintain its own primitive manifest.
- TypeScript extension dependencies need a clear later convention.
- Reuse outside this module is less standardized until primitives become Pi packages.

### 12.2 Future strategy: Pi packages

Mature primitives can later become Pi packages. Pi packages are the natural distribution mechanism for shared extensions, skills, prompt templates, and themes.

Potential package-ready primitive layout:

```text
primitives/core-review/
├── package.json
├── pi.package.json
├── extensions/
├── skills/
├── prompts/
└── themes/
```

The consuming Nix interface should not need to change when a primitive moves from raw directory to packaged form.

---

## 13. Resource filters

Resource filters are not required on day one, but the options schema should make room for them.

Example future configuration:

```nix
piAgent.resources = {
  extensions = {
    enable = true;
    include = [ "extensions/**/*.ts" ];
    exclude = [ "extensions/experimental/**" ];
  };

  skills = {
    enable = true;
    include = [ "doctor" "bootstrap" ];
    exclude = [ "legacy-*" ];
  };

  prompts.enable = true;
  themes.enable = false;
};
```

Recommended semantics:

| Setting | Meaning |
|---|---|
| `enable = true` | Include default resources of this type |
| `enable = false` | Do not include resources of this type |
| `include = [...]` | Include matching paths or primitive IDs |
| `exclude = [...]` | Exclude matching paths or primitive IDs |
| Empty include list | Include none for that category |
| Omitted include list | Include defaults for that category |

This provides enough structure to support Pi's path/glob model while still allowing exact primitive IDs.

---

## 14. Nix option schema draft

Proposed `piAgent.*` options:

```nix
{
  piAgent = {
    enable = true;

    root = ".agents/pi";

    pi = {
      package = null; # defaults to packaged/pinned Pi CLI
      executable = "pi";
    };

    sync = {
      autoBootstrap = true;
      mode = "copy-if-missing";
      preserveLocalChanges = true;
      upgradeMode = "manual";
      writeGitignore = true;
      writeSettingsShim = true;
    };

    primitives = {
      core = {
        enable = true;
      };

      enable = [];
      disable = [];
    };

    resources = {
      extensions = {
        enable = true;
        include = [];
        exclude = [];
      };

      skills = {
        enable = true;
        include = [];
        exclude = [];
      };

      prompts = {
        enable = true;
        include = [];
        exclude = [];
      };

      themes = {
        enable = true;
        include = [];
        exclude = [];
      };
    };

    models = {
      enable = true;
      file = "models/models.json";
    };

    providers = {
      enable = true;
    };

    packages = [];

    secrets = {
      mode = "runtime";
      envFiles = [ "~/.config/pi-agent/env" ];
      secretspec = {
        enable = false;
      };
    };
  };
}
```

---

## 15. Package source model

Support pinned package sources from npm, git, and local paths.

Example:

```nix
piAgent.packages = [
  {
    name = "internal-review";
    source = "git:ssh://git@github.com/090l060/pi-internal-review.git?rev=abc123";
  }
  {
    name = "local-repo-tools";
    source = "./.agents/pi/packages/local-repo-tools";
  }
  {
    name = "shared-core";
    source = "npm:@090l060/pi-shared-core@0.1.0";
  }
];
```

Rules:

- Git sources must be pinned to a commit, tag, or revision.
- Npm sources must use exact versions, not floating ranges.
- Local paths are allowed and should be committed if they are required for repo operation.
- Private package access should rely on the developer's SSH agent, git credentials, npm token, or runtime environment.
- Credentials must not be written into generated files.

---

## 16. Runtime command surface

Expose a small command surface inside `devenv shell`.

### 16.1 `pi-agent`

Wrapper around the actual Pi CLI.

Responsibilities:

- Load configured runtime environment files.
- Avoid leaking secrets into generated config.
- Delegate to the real Pi executable.

Example:

```bash
pi-agent
pi-agent chat
pi-agent --help
```

### 16.2 `pi-agent sync`

Materialize missing files and optionally perform explicit upgrades.

Example:

```bash
pi-agent sync
pi-agent sync --diff
pi-agent sync --upgrade core-doctor-skill
pi-agent sync --upgrade all
```

### 16.3 `pi-agent doctor`

Run diagnostics.

Example checks:

- Pi executable found.
- Settings shim exists.
- Configured root exists.
- Manifest is valid JSON.
- Resource directories exist.
- Runtime env files are readable if configured.
- No secret values appear in generated config.

### 16.4 `pi-agent paths`

Print resolved paths.

Example output:

```text
Project root:        /home/andrew/src/example
Pi settings shim:    /home/andrew/src/example/.pi/settings.json
Agent root:          /home/andrew/src/example/.agents/pi
Manifest:            /home/andrew/src/example/.agents/pi/manifest.json
Pi executable:       /nix/store/.../bin/pi
```

---

## 17. Shell entry behavior

Recommended hybrid behavior:

- On first `devenv shell`, auto-bootstrap if required files are missing.
- If files already exist, do not modify them.
- If desired-state hash changed, print a short diagnostic message.
- Never auto-upgrade local primitives.

Example shell message:

```text
MYPI-AGENT: initialized .agents/pi and .pi/settings.json
```

If already initialized:

```text
MYPI-AGENT: ready (.agents/pi)
```

If an upgrade is available:

```text
MYPI-AGENT: module version changed; run `pi-agent sync --diff` to inspect available updates
```

---

## 18. Secrets model

### 18.1 Rules

- Never write API keys, OAuth tokens, refresh tokens, or provider secrets into `.pi/settings.json`.
- Never write secret values into `.agents/pi/**`.
- Never read local secret files during Nix evaluation.
- Load secrets only at runtime.
- Prefer SecretSpec where available.
- Support a common local env file path such as `~/.config/pi-agent/env` for initial convenience.

### 18.2 Runtime env file support

Example local file outside the repo:

```bash
# ~/.config/pi-agent/env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
```

Wrapper behavior:

```bash
set -a
[ -f "$HOME/.config/pi-agent/env" ] && . "$HOME/.config/pi-agent/env"
set +a
exec pi "$@"
```

The wrapper must be careful not to echo secret values.

### 18.3 SecretSpec support

SecretSpec should be the preferred future path because it separates secret declaration from secret provisioning and supports multiple providers.

A future `secretspec.toml` might declare:

```toml
[secrets.OPENAI_API_KEY]
description = "OpenAI API key for Pi"

[secrets.ANTHROPIC_API_KEY]
description = "Anthropic API key for Pi"
```

The developer or CI environment then provides those secrets through keyring, dotenv, 1Password, environment variables, or another supported backend.

---

## 19. Custom models and providers

### 19.1 Custom models

Custom model definitions should live in:

```text
.agents/pi/models/models.json
```

An example file may be generated as:

```text
.agents/pi/models/models.example.json
```

The example should avoid real secrets.

Example shape:

```json
{
  "providers": {
    "local-openai-compatible": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "env:LOCAL_MODEL_API_KEY"
    }
  },
  "models": {
    "local/qwen-coder": {
      "provider": "local-openai-compatible",
      "model": "qwen-coder"
    }
  }
}
```

The exact supported field names should be verified against Pi's current model schema during implementation.

### 19.2 Custom providers

Custom providers should eventually live under:

```text
.agents/pi/providers
```

or as TypeScript extensions under:

```text
.agents/pi/extensions/providers
```

Initial version should only create the directory and documentation. It should not ship OAuth implementation code.

---

## 20. Git strategy

Recommended default commit policy:

Commit:

```text
.pi/settings.json
.agents/pi/README.md
.agents/pi/manifest.json
.agents/pi/extensions/**
.agents/pi/skills/**
.agents/pi/prompts/**
.agents/pi/themes/**
.agents/pi/packages/**
.agents/pi/models/**
.agents/pi/providers/**
```

Ignore:

```text
.agents/pi/state/**
.agents/pi/**/node_modules/**
.agents/pi/**/.cache/**
```

Rationale:

- Config should be visible and reviewable.
- Repo-specific customizations should travel with the repo.
- Runtime state and caches should remain local.

---

## 21. Safety and trust model

Pi packages, extensions, and skills should be treated as executable project dependencies.

Security expectations:

- Pin external package versions.
- Review private/internal package code before use.
- Avoid floating npm ranges.
- Avoid unpinned git branches for production workflows.
- Do not import third-party Pi packages by default.
- Keep the initial bundled primitive set minimal.
- Make `doctor` warn about unpinned sources.
- Keep secrets runtime-only.

---

## 22. Testing strategy

### 22.1 Fixture tests

Create test fixtures:

```text
tests/fixture-basic
tests/fixture-custom-root
tests/fixture-preserve-local-edits
tests/fixture-upgrade-available
tests/fixture-private-package-declared
```

### 22.2 Test cases

Required tests:

1. Minimal project imports module and enters shell.
2. First bootstrap creates `.pi/settings.json` and `.agents/pi`.
3. Custom root path is honored.
4. Existing files are not overwritten.
5. Manifest is valid JSON.
6. Desired-state hash changes when relevant options change.
7. Runtime env file path is not read during Nix evaluation.
8. `doctor` detects missing shim.
9. `doctor` detects missing root.
10. Sync does not copy secrets into generated files.

### 22.3 Future CI tests

Later:

- Headless sync.
- Headless doctor.
- Package source resolution.
- Private package access failure handling.
- Pi CLI smoke test.

---

## 23. Implementation phases

### Phase 0: Concept and skeleton

Deliverables:

- `MYPI-AGENT_CONCEPT.md`
- repo skeleton
- initial `flake.nix`
- initial `devenv.nix`
- placeholder `modules/pi-agent.nix`

### Phase 1: Minimal module

Deliverables:

- `piAgent.enable`
- `piAgent.root`
- package the Pi CLI or wrapper placeholder
- add wrapper commands to shell
- render desired-state metadata

### Phase 2: Bootstrap sync

Deliverables:

- `pi-agent sync`
- first-run auto-bootstrap
- `.pi/settings.json` shim generation
- `.agents/pi` creation
- manifest generation
- copy-if-missing semantics

### Phase 3: Doctor command

Deliverables:

- `pi-agent doctor`
- path diagnostics
- manifest validation
- secret leakage checks
- unpinned package warnings

### Phase 4: Primitive registry

Deliverables:

- `primitives/registry.json`
- individual primitive versioning
- per-primitive manifest entries
- upgrade diff support

### Phase 5: Package source support

Deliverables:

- npm package declarations
- git package declarations
- local package declarations
- pin validation
- private source diagnostics

### Phase 6: Secrets integration

Deliverables:

- runtime env file wrapper
- SecretSpec support
- docs for local and CI secret provisioning

### Phase 7: CI/headless support

Deliverables:

- noninteractive sync
- noninteractive doctor
- fail-fast validation mode
- CI examples

---

## 24. Initial minimal primitive set

The first version should ship only:

### 24.1 Core root README

A generated `README.md` explaining:

- what `.agents/pi` is,
- which files are committed,
- which files are local runtime state,
- how to run `pi-agent doctor`,
- how to add skills/extensions/prompts/themes later.

### 24.2 Doctor skill

A minimal skill at:

```text
.agents/pi/skills/doctor/SKILL.md
```

Purpose:

- explain the local setup to Pi,
- instruct Pi how to inspect the generated root,
- help debug missing files or broken settings.

### 24.3 Example models file

A non-secret example at:

```text
.agents/pi/models/models.example.json
```

Purpose:

- show structure,
- discourage committed secrets,
- point to runtime env variables.

### 24.4 Directory READMEs

Small READMEs in:

```text
extensions/
skills/
prompts/
themes/
packages/
models/
providers/
```

Purpose:

- make empty directories visible in git,
- explain how each category should be customized.

---

## 25. Example generated root README

```markdown
# Project Pi Agent Configuration

This directory contains this repository's editable Pi Coding Agent configuration.

It was bootstrapped by `mypi-agent`, a devenv/Nix module. Local changes are preserved by default.

## Layout

- `extensions/` — TypeScript modules for tools, commands, events, and UI.
- `skills/` — reusable agent skills loaded on demand.
- `prompts/` — reusable prompt templates and slash-command expansions.
- `themes/` — terminal themes.
- `packages/` — local Pi packages.
- `models/` — custom model definitions. Do not commit secrets.
- `providers/` — custom provider notes or implementation files.
- `state/` — local runtime state. Do not commit.

## Commands

```bash
pi-agent doctor
pi-agent sync --diff
pi-agent sync --upgrade all
```

## Secrets

Secrets should be loaded at runtime through SecretSpec or a local env file such as:

```text
~/.config/pi-agent/env
```

Do not write API keys or OAuth tokens into this directory.
```

---

## 26. Example generated doctor skill

```markdown
---
name: doctor
summary: Inspect and explain this repository's MYPI-AGENT setup.
---

# Doctor Skill

Use this skill when the user asks about this repository's Pi agent configuration, generated files, missing paths, models, providers, package sources, or secrets wiring.

## Expected layout

- `.pi/settings.json` is a compatibility shim.
- `.agents/pi` is the default editable agent root unless configured otherwise.
- `.agents/pi/manifest.json` records installed primitive versions.
- `.agents/pi/state` is runtime state and should not be committed.

## Checks

1. Confirm `.pi/settings.json` exists.
2. Confirm the configured root exists.
3. Confirm required subdirectories exist.
4. Confirm `manifest.json` is valid JSON.
5. Confirm no obvious secret values are committed.
6. Confirm package sources are pinned where applicable.
7. Recommend `pi-agent doctor` for command-level diagnostics.
```

---

## 27. Open implementation questions

These are not conceptual blockers, but they should be answered during implementation:

1. What is the exact executable name and packaging method for the current Pi CLI version?
2. Does Pi accept all desired path fields exactly as assumed in `.pi/settings.json`?
3. Does Pi support a single models file path in project settings, or should model config be wired differently?
4. Should `.pi/settings.json` be repaired automatically if it matches an old generated hash and has no local edits?
5. Should package source installation be delegated entirely to Pi, or should `mypi-agent` pre-resolve packages?
6. Should the wrapper command be named `pi-agent`, `mypi`, or both?

Recommended initial answers:

- Use `pi-agent` as the wrapper command.
- Keep `pi` itself untouched if installed.
- Use `pi-agent sync --repair-shim` for repair rather than automatic overwrite.
- Let Pi handle Pi package installation initially.
- Add Nix-level strict package resolution only later if needed.

---

## 28. Reference links

The implementation should be checked against the latest upstream docs while building.

- Devenv inputs: https://devenv.sh/inputs/
- Devenv YAML options: https://devenv.sh/reference/yaml-options/
- Devenv imports/polyrepo guide: https://devenv.sh/guides/polyrepo/
- Devenv SecretSpec integration: https://devenv.sh/integrations/secretspec/
- Devenv dotenv integration warning/context: https://devenv.sh/integrations/dotenv/
- Pi settings: https://pi.dev/docs/latest/settings
- Pi skills: https://pi.dev/docs/latest/skills
- Pi packages: https://pi.dev/docs/latest/packages
- Pi custom models: https://pi.dev/docs/latest/models
- Pi custom providers: https://pi.dev/docs/latest/custom-provider
- Pi providers: https://pi.dev/docs/latest/providers
- Pi npm package: https://www.npmjs.com/package/@earendil-works/pi-coding-agent

---

## 29. Final position

`MYPI-AGENT` should be a minimal, importable devenv module that installs Pi, creates a small compatibility shim, and materializes an editable, versioned `.agents/pi` foundation into each consuming repository.

The correct first version is intentionally small:

- no broad default skill suite,
- no automatic overwrites,
- no committed secrets,
- no complicated package resolution,
- no CI-first workflow.

The library should establish the pattern, not the entire agent ecosystem. Once the pattern is stable, additional primitives can be added one at a time, individually versioned, and eventually promoted into proper Pi packages when they prove useful across many repositories.
