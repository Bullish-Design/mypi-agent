# SECRETSPEC_INDIVIDUAL_CONFIG.md

## Purpose

This document defines the **individual repo API configuration concept** for `mypi-agent`.

The goal is to let each devenv-managed project use its own upstream API keys while keeping the user experience simple:

```bash
pi
```

The `pi` command should run with the correct API keys for the current repo. The `mypi` CLI should remain a setup, sync, and validation tool. Actual API key values should never be committed to a repo.

The preferred pattern is:

```text
central local secrets root
  -> one subfolder per repo
    -> one .env file per repo
      -> canonical API key variable names
```

Each repo points SecretSpec at its own local `.env` file through uncommitted `devenv.local.yaml`.

---

## Summary recommendation

Use **one SecretSpec dotenv provider file per repo**.

Example:

```text
~/.config/mypi-agent/secrets/
  mypi-agent/
    .env
  repo-a/
    .env
  repo-b/
    .env
```

Each project-specific `.env` uses the standard variable names expected by Pi and LLM SDKs:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
```

Then each repo has an uncommitted local devenv override:

```yaml
# devenv.local.yaml
secretspec:
  enable: true
  provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/repo-a/.env
  profile: default
```

The committed repo contains only the SecretSpec declaration file:

```toml
# secretspec.toml
[project]
name = "repo-a"
revision = "1.0"

[profiles.default]
OPENAI_API_KEY = { description = "OpenAI API key for this repo's Pi usage", required = false }
ANTHROPIC_API_KEY = { description = "Anthropic API key for this repo's Pi usage", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for this repo's Pi usage", required = false }
```

This gives every repo independent API keys without requiring `mypi-agent` to translate repo-specific variable names into canonical runtime names.

---

## Why this is better than one flat central `.env`

A flat central `.env` would need unique names for every repo:

```dotenv
REPO_A_OPENAI_API_KEY=...
REPO_B_OPENAI_API_KEY=...
REPO_C_OPENAI_API_KEY=...
```

That creates a mapping problem because Pi usually expects canonical names:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

So `mypi-agent` would need a runtime translation layer:

```text
REPO_A_OPENAI_API_KEY -> OPENAI_API_KEY
REPO_A_ANTHROPIC_API_KEY -> ANTHROPIC_API_KEY
```

That is avoidable.

With one `.env` file per repo, every file can reuse canonical variable names:

```text
repo-a/.env contains OPENAI_API_KEY for repo-a
repo-b/.env contains OPENAI_API_KEY for repo-b
repo-c/.env contains OPENAI_API_KEY for repo-c
```

The selected provider path determines which key is used. No mapping layer is required.

---

## Core architecture

```text
User runs:
  pi

mypi-agent provides:
  pi wrapper

pi wrapper runs:
  secretspec run -- <real Pi binary>

SecretSpec loads:
  secretspec.toml from current repo
  dotenv provider from devenv.local.yaml

Provider points to:
  ~/.config/mypi-agent/secrets/<repo-slug>/.env

Real Pi process receives:
  OPENAI_API_KEY
  ANTHROPIC_API_KEY
  OPENROUTER_API_KEY
```

The important invariant:

```text
mypi configures and validates.
pi runs the agent.
Only pi receives LLM API keys by default.
```

---

## File responsibilities

### Committed files

These belong in the project repo.

```text
repo/
  devenv.yaml
  devenv.nix
  secretspec.toml
```

`devenv.yaml` imports `mypi-agent` and may enable shared project behavior.

`secretspec.toml` declares what secrets the project expects. It does **not** contain secret values.

`devenv.nix` contains normal project configuration.

### Uncommitted local files

These belong in the project repo but should not be committed.

```text
repo/
  devenv.local.yaml
```

`devenv.local.yaml` points this local checkout to the correct per-repo SecretSpec provider file.

### Central local secrets directory

This lives outside all project repos.

```text
~/.config/mypi-agent/secrets/
  repo-a/.env
  repo-b/.env
  repo-c/.env
```

Each `.env` file contains actual key values for one repo only.

---

## Recommended local secrets layout

Use a stable repo slug as the directory name.

```text
~/.config/mypi-agent/secrets/
  mypi-agent/
    .env
  telepi-experiments/
    .env
  personal-website/
    .env
  allium-lab/
    .env
```

Example file:

```dotenv
# ~/.config/mypi-agent/secrets/telepi-experiments/.env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=...
```

The slug should be stable and filesystem-safe:

```text
repo name: TelePi Experiments
slug: telepi-experiments
```

Recommended slug rule:

```text
lowercase
replace spaces/underscores with hyphens
remove characters that are not letters, numbers, dots, or hyphens
```

---

## Recommended `devenv.local.yaml`

Each repo should have a local, uncommitted file:

```yaml
# devenv.local.yaml
secretspec:
  enable: true
  provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
  profile: default
```

On Linux:

```yaml
# devenv.local.yaml
secretspec:
  enable: true
  provider: dotenv:/home/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
  profile: default
```

In a container:

```yaml
# devenv.local.yaml
secretspec:
  enable: true
  provider: dotenv:/run/secrets/mypi-agent/telepi-experiments/.env
  profile: default
```

Important: the SecretSpec dotenv provider should point to a **file**, not just a folder.

Preferred:

```yaml
provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/repo-a/.env
```

Not preferred:

```yaml
provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/repo-a/
```

---

## Recommended `secretspec.toml`

Each repo should commit a declaration file.

Minimal example:

```toml
[project]
name = "telepi-experiments"
revision = "1.0"

[profiles.default]
OPENAI_API_KEY = { description = "OpenAI API key for Pi usage in this repo", required = false }
ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi usage in this repo", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for Pi usage in this repo", required = false }
```

Stricter example:

```toml
[project]
name = "telepi-experiments"
revision = "1.0"

[profiles.default]
ANTHROPIC_API_KEY = { description = "Anthropic API key for primary Pi usage", required = true }
OPENAI_API_KEY = { description = "OpenAI API key for optional fallback usage", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for optional model routing", required = false }
```

Use `required = true` only for keys that must exist for the repo’s normal `pi` workflow.

---

## Profile usage

Profiles should describe **runtime mode**, not project identity.

Good use of profiles:

```toml
[profiles.default]
ANTHROPIC_API_KEY = { description = "Default local Anthropic key", required = true }
OPENAI_API_KEY = { description = "Optional OpenAI fallback key", required = false }

[profiles.ci]
ANTHROPIC_API_KEY = { description = "CI Anthropic key", required = true }
OPENAI_API_KEY = { description = "CI OpenAI fallback key", required = false }

[profiles.offline]
ANTHROPIC_API_KEY = { description = "Not required for offline checks", required = false }
OPENAI_API_KEY = { description = "Not required for offline checks", required = false }
```

Less useful use of profiles:

```toml
[profiles.repo_a]
OPENAI_API_KEY = { required = true }

[profiles.repo_b]
OPENAI_API_KEY = { required = true }
```

Project identity should be handled by the provider path:

```text
repo-a -> provider points to repo-a/.env
repo-b -> provider points to repo-b/.env
```

This keeps profiles available for real environment differences such as `default`, `ci`, `production`, or `offline`.

---

## `pi` wrapper behavior

The `pi` command exported by `mypi-agent` should be a wrapper.

Expected behavior:

```text
pi
  -> validate current project root
  -> locate the real installed Pi binary by absolute path
  -> run SecretSpec
  -> exec real Pi binary with all original args
```

Conceptual shell behavior:

```bash
set -euo pipefail

if [ -n "${DEVENV_ROOT:-}" ]; then
  cd "$DEVENV_ROOT"
fi

REAL_PI="$MYPI_AGENT_ROOT/node_modules/.bin/pi"

if [ ! -x "$REAL_PI" ]; then
  echo "Pi is not installed or not synced. Run: mypi sync" >&2
  exit 127
fi

exec secretspec run -- "$REAL_PI" "$@"
```

The wrapper must call the real Pi binary by absolute path. It must not run `pi` again, or it can recurse into itself.

---

## PATH shadowing hazard

If the devenv module prepends this path:

```text
.agents/pi/node_modules/.bin
```

before the devenv script directory, then the raw Node-installed `pi` binary may be found before the wrapper.

That would bypass SecretSpec.

Avoid this command resolution problem by ensuring the exported wrapper is the `pi` command users hit.

Recommended rules:

1. Do not rely on `PATH` to find the real Pi binary inside the wrapper.
2. Use an absolute path for `REAL_PI`.
3. Make sure the `pi` wrapper has priority over `.agents/pi/node_modules/.bin/pi`.
4. Keep raw `node_modules/.bin` paths available only when needed, not as the primary command source for `pi`.

---

## `mypi` CLI behavior

The `mypi` CLI should remain a setup and validation surface.

Recommended commands:

```text
mypi sync
mypi doctor
mypi paths
mypi needs-sync
mypi secrets init
mypi secrets check
mypi secrets path
mypi secrets doctor
```

### `mypi secrets init`

Should help create or validate local files:

```text
~/.config/mypi-agent/secrets/<repo-slug>/.env
repo/devenv.local.yaml
repo/secretspec.toml
```

It should not print secret values.

It may create an empty template:

```dotenv
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
```

### `mypi secrets check`

Should verify that SecretSpec can resolve the declared secrets.

Expected checks:

```text
- secretspec.toml exists
- devenv.local.yaml exists or provider/profile are supplied another way
- provider path uses dotenv:<absolute-file-path>
- target .env file exists
- required secrets are present
- command can run under secretspec without printing values
```

### `mypi secrets doctor`

Should provide higher-level diagnostics:

```text
- local provider configured
- provider file exists
- provider file is outside the repo
- provider file is not tracked by git
- required keys are declared in secretspec.toml
- required keys are present in the provider
- generated mypi state files do not contain secret values
- pi wrapper is ahead of raw node_modules pi on PATH
```

### `mypi secrets path`

Should print non-sensitive paths:

```text
repo slug: telepi-experiments
provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
profile: default
```

It should not print key values.

---

## Nix module options

`mypi-agent` should expose minimal options for this concept.

Example option shape:

```nix
mypi = {
  pi = {
    enable = true;
    commandName = "pi";
  };

  secrets = {
    enable = true;
    mode = "runtime"; # runtime | disabled
    profile = "default";
    provider = null;  # normally read from devenv.local.yaml
    defaultRoot = null;
    projectSlug = null;
  };
};
```

Recommended defaults:

```nix
mypi.pi.enable = true;
mypi.pi.commandName = "pi";
mypi.secrets.enable = true;
mypi.secrets.mode = "runtime";
mypi.secrets.provider = null;
mypi.secrets.profile = "default";
```

`provider = null` means the module should let devenv/SecretSpec resolve the provider from normal configuration, especially `devenv.local.yaml`.

Do not require every repo to hard-code the local secrets path inside committed Nix code.

---

## Bootstrap workflow for a new repo

Recommended setup flow:

```text
1. User creates or enters a devenv-managed repo.
2. Repo imports mypi-agent through devenv.yaml.
3. User runs mypi sync or mypi doctor.
4. mypi detects missing SecretSpec local config.
5. mypi proposes/creates a repo slug.
6. mypi creates local secrets folder outside the repo.
7. mypi creates or updates repo/devenv.local.yaml.
8. mypi creates or updates repo/secretspec.toml.
9. User fills in API key values in the local .env file.
10. User runs mypi secrets check.
11. User runs pi.
```

Example generated paths:

```text
repo path:
  /Users/YOU/dev/telepi-experiments

repo slug:
  telepi-experiments

local secret file:
  /Users/YOU/.config/mypi-agent/secrets/telepi-experiments/.env

local devenv override:
  /Users/YOU/dev/telepi-experiments/devenv.local.yaml
```

---

## Git ignore requirements

Each project should ignore local devenv overrides and dotenv files.

Recommended `.gitignore` additions:

```gitignore
devenv.local.yaml
.env
.env.*
```

The central secrets directory is outside the repo, so it should not normally be reachable by git. Still, the repo should ignore local dotenv files in case a user creates one during debugging.

---

## API usage monitoring model

SecretSpec does not measure API usage. It selects and injects the correct key.

Usage monitoring should happen at the upstream API provider layer.

Recommended pattern:

```text
repo-a/.env contains API keys created specifically for repo-a
repo-b/.env contains API keys created specifically for repo-b
repo-c/.env contains API keys created specifically for repo-c
```

Then usage can be attributed by:

```text
provider project
provider workspace
provider API key
billing dashboard filter
usage API query
```

Recommended naming convention for upstream keys:

```text
mypi-agent / telepi-experiments / local
mypi-agent / telepi-experiments / remote-pc
mypi-agent / personal-website / local
```

This makes provider dashboards easier to read.

---

## Multi-machine behavior

Because `devenv.local.yaml` is uncommitted, each machine can point the same repo to a different local provider path.

Laptop:

```yaml
secretspec:
  enable: true
  provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
  profile: default
```

Linux workstation:

```yaml
secretspec:
  enable: true
  provider: dotenv:/home/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
  profile: default
```

Container:

```yaml
secretspec:
  enable: true
  provider: dotenv:/run/secrets/mypi-agent/telepi-experiments/.env
  profile: default
```

This keeps repo configuration portable while allowing each machine to manage its own local secret storage.

---

## Container and remote computer model

For a remote machine or containerized repo environment, mount the per-repo secret file into the container and point `devenv.local.yaml` at the mounted path.

Host layout:

```text
/home/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
```

Container layout:

```text
/run/secrets/mypi-agent/telepi-experiments/.env
```

Container `devenv.local.yaml`:

```yaml
secretspec:
  enable: true
  provider: dotenv:/run/secrets/mypi-agent/telepi-experiments/.env
  profile: default
```

Recommended mount behavior:

```text
read-only mount
project-specific file only
no broad mount of all secrets unless needed
```

This limits the blast radius if a container or repo process is compromised.

---

## Security posture

This pattern is not the strongest possible secret-storage model because dotenv files are plaintext. It is still a practical local-development model when combined with:

```text
- files outside project repos
- one file per repo
- uncommitted devenv.local.yaml
- runtime injection through SecretSpec
- no global shell export of API keys
- no API keys in generated mypi state files
- provider-side per-project API keys
```

For stronger storage later, the same `secretspec.toml` declarations can remain while the provider changes from dotenv to another backend.

Example future provider shift:

```yaml
secretspec:
  enable: true
  provider: keyring
  profile: default
```

or another SecretSpec-supported provider.

The project should not bake in dotenv as the only possible provider. It should make dotenv the easiest local default while preserving SecretSpec provider flexibility.

---

## Avoid global environment export

Avoid this default pattern:

```nix
env.OPENAI_API_KEY = config.secretspec.secrets.OPENAI_API_KEY;
env.ANTHROPIC_API_KEY = config.secretspec.secrets.ANTHROPIC_API_KEY;
```

That exposes API keys to every process in the devenv shell.

Preferred pattern:

```text
pi wrapper
  -> secretspec run
    -> real Pi binary
```

Only the Pi runtime process receives the API keys.

---

## Doctor checks to add

`mypi doctor` should include SecretSpec checks but avoid exposing values.

Recommended checks:

```text
[required]
- repo has secretspec.toml
- repo has devenv.local.yaml or equivalent provider configuration
- SecretSpec integration is enabled
- provider resolves to a file path when using dotenv
- provider file exists
- provider file is outside repo root
- provider file is not committed
- required secrets declared in secretspec.toml are present
- pi command resolves to mypi-agent wrapper
- real Pi binary exists separately from wrapper
- wrapper uses absolute path to real Pi binary

[warning]
- provider file is inside repo root
- provider file has broad permissions
- raw node_modules/.bin appears before wrapper command path
- profiles exist but current profile is unclear
- optional secrets are missing

[forbidden]
- generated mypi state files contain values that look like API keys
- `.pi/settings.json` contains API keys
- `.agents/pi/manifest.json` contains API keys
- committed config contains `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, or similar assignments
```

---

## Test fixtures to add

Add tests around this concept so regressions are caught early.

### 1. Individual provider fixture

```text
tmp/
  repo-a/
    devenv.yaml
    devenv.local.yaml
    secretspec.toml
  secrets/
    repo-a/.env
```

Test that `pi` receives `OPENAI_API_KEY` from `repo-a/.env`.

### 2. Repo isolation fixture

```text
tmp/
  repo-a/devenv.local.yaml -> secrets/repo-a/.env
  repo-b/devenv.local.yaml -> secrets/repo-b/.env
  secrets/repo-a/.env
  secrets/repo-b/.env
```

Test that repo A does not receive repo B’s key.

### 3. No global exposure fixture

Test that setup commands do not receive API keys:

```text
mypi sync
mypi doctor
mypi paths
mypi needs-sync
```

Only `pi` should run under SecretSpec by default.

### 4. PATH shadowing fixture

Test that:

```bash
command -v pi
```

resolves to the mypi-agent wrapper, not raw `node_modules/.bin/pi`.

### 5. Leak scanning fixture

Create fake generated state files and assert they do not contain known fake API key values.

---

## Migration from flat central `.env`

Old model:

```text
~/.config/mypi-agent/secrets.env
```

Example old file:

```dotenv
REPO_A_OPENAI_API_KEY=...
REPO_A_ANTHROPIC_API_KEY=...
REPO_B_OPENAI_API_KEY=...
REPO_B_ANTHROPIC_API_KEY=...
```

New model:

```text
~/.config/mypi-agent/secrets/repo-a/.env
~/.config/mypi-agent/secrets/repo-b/.env
```

Example new `repo-a/.env`:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Example new `repo-b/.env`:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Migration steps:

```text
1. Create one folder per repo under ~/.config/mypi-agent/secrets/.
2. Move each repo’s physical API key values into its own .env file.
3. Rename keys back to canonical names such as OPENAI_API_KEY.
4. Add or update each repo’s devenv.local.yaml to point to its file.
5. Keep each repo’s secretspec.toml using canonical names.
6. Run mypi secrets check in each repo.
7. Run pi in each repo and confirm provider-side usage attribution.
8. Delete the old flat file after verification.
```

---

## Example complete repo setup

Repo:

```text
~/dev/telepi-experiments/
  devenv.yaml
  devenv.nix
  secretspec.toml
  devenv.local.yaml       # uncommitted
```

Central local secret file:

```text
~/.config/mypi-agent/secrets/telepi-experiments/.env
```

`secretspec.toml`:

```toml
[project]
name = "telepi-experiments"
revision = "1.0"

[profiles.default]
ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi in telepi-experiments", required = true }
OPENAI_API_KEY = { description = "OpenAI API key for optional Pi fallback", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for optional model routing", required = false }
```

`devenv.local.yaml`:

```yaml
secretspec:
  enable: true
  provider: dotenv:/Users/YOU/.config/mypi-agent/secrets/telepi-experiments/.env
  profile: default
```

Local `.env`:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=...
```

Runtime:

```bash
pi
```

Internal behavior:

```text
pi wrapper
  -> secretspec run -- /absolute/path/to/.agents/pi/node_modules/.bin/pi
```

---

## Implementation checklist

### `mypi-agent` module

```text
- exports a pi wrapper
- includes SecretSpec in the devenv environment when enabled
- does not export API keys globally
- avoids PATH shadowing of pi wrapper
- uses absolute path to real Pi binary
- keeps mypi setup commands secret-free by default
```

### `mypi` CLI

```text
- can initialize per-repo secret directory
- can create/update secretspec.toml
- can create/update devenv.local.yaml
- can validate provider path
- can run masked SecretSpec checks
- can detect leaked values in generated state files
- can diagnose wrapper/path problems
```

### Consumer repo

```text
- commits secretspec.toml
- does not commit devenv.local.yaml
- does not commit .env files
- uses per-repo upstream API keys
- points local SecretSpec provider to that repo’s local .env file
```

---

## Final design rule

Use this as the core invariant for the individual repo API configuration concept:

```text
One repo gets one local SecretSpec provider file.
That provider file contains canonical Pi API key names.
The repo declares those names in secretspec.toml.
The uncommitted devenv.local.yaml points to the provider file.
The pi wrapper runs through secretspec run.
The mypi CLI validates setup but does not receive secrets by default.
```

This gives per-project API usage tracking, minimal command complexity, clean repo isolation, and no variable-name mapping layer.

---

## References reviewed

- devenv SecretSpec integration: https://devenv.sh/integrations/secretspec/
- devenv YAML options for `secretspec.enable`, `secretspec.provider`, and `secretspec.profile`: https://devenv.sh/reference/yaml-options/
- devenv files and local overrides: https://devenv.sh/files-and-variables/
- SecretSpec dotenv provider: https://secretspec.dev/providers/dotenv/
- SecretSpec quick start and runtime command model: https://secretspec.dev/quick-start/
- SecretSpec CLI reference: https://secretspec.dev/reference/cli/
- SecretSpec profiles: https://secretspec.dev/concepts/profiles/
- devenv dotenv integration note recommending SecretSpec for new projects: https://devenv.sh/integrations/dotenv/
