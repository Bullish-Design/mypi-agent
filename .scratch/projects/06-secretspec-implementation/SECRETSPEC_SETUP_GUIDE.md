# SecretSpec Integration Guide for mypi-agent

## Purpose

This guide specifies how `mypi-agent` integrates with devenv's built-in SecretSpec support to manage LLM API keys. SecretSpec is the sole API-key management mechanism for Pi.

The desired end state:

```text
user runs: pi
          |
mypi-agent `scripts.pi` wrapper (Nix module)
          |
secretspec run -- <real Pi binary at absolute path>
          |
Pi receives API keys as process-scoped env vars
```

Setup and validation commands (`mypi sync`, `mypi doctor`, `mypi paths`, `mypi needs-sync`) never receive API keys.

## Executive summary

SecretSpec creates an architectural boundary: secrets are injected only into the `pi` process at runtime. The library does not need to build its own secret-management CLI, provider configuration, or leak-scanning infrastructure. It delegates all of that to SecretSpec and devenv's built-in integration.

Commit to each consumer repo:

- `secretspec.toml` — declares which API-key names the repo needs.
- `devenv.yaml` / `devenv.nix` — imports `mypi-agent` as usual.

Keep local and uncommitted:

- `devenv.local.yaml` — points SecretSpec at the developer's local provider.

Do not put API-key values in:

- `devenv.nix` or committed `devenv.yaml`
- `.pi/settings.json`
- `.agents/pi/manifest.json`
- `.agents/pi/.state/*.json`
- the global shell environment

## What SecretSpec is

SecretSpec is a declarative secret-management tool built into devenv (>= 2.0). Its central idea is separation of responsibilities:

| Responsibility | File/tool | Committed? | Contains secret values? |
|---|---|:---:|:---:|
| Declare which secrets the project needs | `secretspec.toml` | Yes | No |
| Choose where values come from on this machine | `devenv.local.yaml` or `secretspec config` | No | No |
| Store actual values | keyring, 1Password, Vault/OpenBao, AWS/GCP SM, Bitwarden, dotenv, etc. | No | Yes |
| Inject values into the process that needs them | `secretspec run -- <command>` | N/A | Runtime only |

### Devenv's built-in SecretSpec module

Devenv exposes three read-only Nix options, populated automatically when secretspec is configured in `devenv.local.yaml`:

```nix
config.secretspec.enable   # bool — true when secrets are loaded
config.secretspec.provider # string|null — provider used (e.g. "dotenv", "keyring")
config.secretspec.profile  # string|null — profile used (e.g. "default")
config.secretspec.secrets  # attrset — loaded secret values (DO NOT USE for Pi keys)
```

All options are read-only. The devenv CLI loads secrets before Nix evaluation and injects them via the `SECRETSPEC_SECRETS` environment variable.

**Important**: SecretSpec integration is not supported when using devenv with Nix Flakes. The `mypi-agent` import uses `flake: false` in `devenv.yaml`, so this is not a concern.

## Why this fits mypi-agent

`mypi-agent` solves these problems:

1. Install/sync the Pi package into a repo-local location.
2. Expose a stable `pi` command.
3. Keep npm state project-local.
4. Create/repair Pi settings shims.
5. Validate the environment with `mypi doctor`.
6. Pass LLM provider API keys to Pi at runtime only.

SecretSpec solves #6 architecturally: the `pi` wrapper uses `secretspec run`, so keys exist only in the Pi process. The library does not need to implement its own secret handling, leak scanning, or provider configuration.

## Current repo state

The relevant files are:

```text
modules/pi-agent.nix          # Nix module (piAgent options, scripts.mypi, enterShell)
packages/mypi-agent-cli.nix   # Python package build
src/mypi_agent/cli.py          # CLI commands: sync, doctor, agent, pi, paths, needs-sync
src/mypi_agent/doctor.py       # Health checks including _secret_leak_likely()
src/mypi_agent/models.py       # Paths model, Manifest model
src/mypi_agent/sync.py         # Sync workflow
src/mypi_agent/surfaces_runtime.py  # Settings shim actor
tests/fixtures/devenv/         # 4 test fixtures (basic, custom-root, preserve-local-edits, yaml-import-only)
.scratch/specs/allium/         # Domain specs (core.allium defines SecretRuntimePolicy invariants)
```

The current module:

- Defines `piAgent` options (enable, root, nodePackage, piPackageName, piPackageVersion, npmInstallFlags, allowFloatingPiVersion, bootstrap.mode).
- Sets repo-local npm prefix/cache environment variables.
- Exposes `scripts.mypi` as a devenv script.
- **Prepends** `$DEVENV_ROOT/$MYPI_AGENT_ROOT/node_modules/.bin` to `PATH` in `enterShell` (this must change).
- Has no `scripts.pi` wrapper — users currently reach Pi via `mypi pi`, `mypi agent`, or the raw PATH entry.

## The command-boundary rule

```text
mypi configures and validates.
pi runs the agent.
Only pi receives LLM API keys.
```

| Command | Receives API keys? | Reason |
|---|:---:|---|
| `pi` | Yes | Agent runtime, wrapped by SecretSpec |
| `mypi sync` | No | Installs files and npm state |
| `mypi doctor` | No | Validates environment |
| `mypi paths` | No | Prints paths only |
| `mypi needs-sync` | No | Checks local state only |

## SecretSpec files and where they belong

### `secretspec.toml` -- committed

Every consumer repo commits a `secretspec.toml` declaring expected keys:

```toml
[project]
name = "example-project"
revision = "1.0"

[profiles.default]
ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi", required = false }
OPENAI_API_KEY = { description = "OpenAI API key for Pi", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for Pi", required = false }
```

Use the exact environment-variable names expected by Pi and its supported LLM providers. For a strict repo, mark the primary key as `required = true`.

Profiles inherit from `default` automatically, so a `production` profile only needs to override what differs.

### `devenv.local.yaml` -- local, uncommitted

Machine-specific provider configuration:

```yaml
secretspec:
  enable: true
  provider: keyring
  profile: default
```

Or with the dotenv provider:

```yaml
secretspec:
  enable: true
  provider: dotenv:/home/YOU/.config/mypi-agent/secrets.env
  profile: default
```

`devenv.local.yaml` is intended for local overrides and must not be committed. Devenv excludes it by default, but add it to `.gitignore` defensively.

Provider can also be configured via the SecretSpec CLI (`secretspec config init`) or the `SECRETSPEC_PROVIDER` environment variable, but `devenv.local.yaml` is the recommended approach for devenv projects.

### Local secret storage (dotenv example)

```dotenv
# ~/.config/mypi-agent/secrets.env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
```

Recommended permissions:

```bash
mkdir -p ~/.config/mypi-agent
chmod 700 ~/.config/mypi-agent
chmod 600 ~/.config/mypi-agent/secrets.env
```

The dotenv provider stores values in plaintext. For shared/team usage, prefer keyring, 1Password, Vault/OpenBao, or another encrypted provider. The `secretspec.toml` does not change when the provider changes.

## Consumer repo layout

```text
consumer-repo/
  devenv.nix               # committed
  devenv.yaml              # committed
  devenv.lock              # committed
  secretspec.toml          # committed
  .gitignore               # committed
  .pi/                     # generated by mypi sync
  .agents/pi/              # generated/managed by mypi sync
  devenv.local.yaml        # local only, not committed
```

Committed `devenv.yaml`:

```yaml
require_version: ">=2.1"

inputs:
  mypi-agent:
    url: github:Bullish-Design/mypi-agent
    flake: false

imports:
  - mypi-agent
```

Committed `devenv.nix`:

```nix
{ ... }:
{
  piAgent.enable = true;
}
```

Committed `secretspec.toml`:

```toml
[project]
name = "consumer-repo"
revision = "1.0"

[profiles.default]
ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi", required = false }
OPENAI_API_KEY = { description = "OpenAI API key for Pi", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for Pi", required = false }
```

Local `devenv.local.yaml`:

```yaml
secretspec:
  enable: true
  provider: keyring
  profile: default
```

Normal workflow:

```bash
devenv shell
mypi sync
mypi doctor
pi
```

## Why we do not use `config.secretspec.secrets`

Devenv's SecretSpec module loads secret values into `config.secretspec.secrets`. This is useful for wiring secrets into devenv services from Nix, but `mypi-agent` must not use it for Pi API keys.

Do not add this to the module:

```nix
# WRONG: exports keys into the entire shell environment
env.ANTHROPIC_API_KEY = config.secretspec.secrets.ANTHROPIC_API_KEY;
```

The `pi` wrapper reads only `config.secretspec.provider` and `config.secretspec.profile` (safe metadata), then delegates to `secretspec run` for runtime injection.

## Implementation plan

### Nix module changes

#### Add one option: `piAgent.secrets.enable`

```nix
options.piAgent.secrets.enable = lib.mkOption {
  type = lib.types.bool;
  default = true;
  description = "Run the pi command through SecretSpec for runtime secret injection.";
};
```

This is the only secret-related option needed. No `mode`, no `requireSecretSpecFile`. When `true`, the `pi` wrapper uses `secretspec run`. When `false`, it execs the raw binary directly.

#### Add `scripts.pi` wrapper

```nix
let
  cfg = config.piAgent;
  mypiPkg = pkgs.callPackage ../packages/mypi-agent-cli.nix { };

  secretspecProviderArgs =
    lib.optionalString (config.secretspec.provider or null != null)
      "--provider ${lib.escapeShellArg config.secretspec.provider} "
    + lib.optionalString (config.secretspec.profile or null != null)
      "--profile ${lib.escapeShellArg config.secretspec.profile} ";
in
{
  config = lib.mkIf cfg.enable {
    packages = [ cfg.nodePackage ];

    scripts.pi = {
      description = "Run Pi with SecretSpec runtime secrets";
      exec = ''
        set -euo pipefail

        if [ -n "''${DEVENV_ROOT:-}" ]; then
          cd "$DEVENV_ROOT"
        fi

        project_root="''${DEVENV_ROOT:-$PWD}"
        agent_root="''${MYPI_AGENT_ROOT:-.agents/pi}"
        real_pi="$project_root/$agent_root/node_modules/.bin/pi"

        if [ ! -x "$real_pi" ]; then
          echo "error: Pi is not installed. Run: mypi sync" >&2
          exit 127
        fi

        ${if cfg.secrets.enable then ''
        exec secretspec run ${secretspecProviderArgs}-- "$real_pi" "$@"
        '' else ''
        exec "$real_pi" "$@"
        ''}
      '';
    };

    scripts.mypi = {
      description = "MYPI setup, sync, and doctor CLI";
      exec = ''
        set -euo pipefail
        export MYPI_NPM_INSTALL_FLAGS=${lib.escapeShellArg (builtins.toJSON cfg.npmInstallFlags)}
        if [ -n "''${DEVENV_ROOT:-}" ]; then
          cd "$DEVENV_ROOT"
        fi
        exec ${mypiPkg}/bin/mypi "$@"
      '';
    };
  };
}
```

Key design points:

- The wrapper calls Pi by **absolute path**, not via PATH.
- The wrapper forwards all args unchanged.
- Provider/profile metadata comes from devenv's read-only `config.secretspec.*` options.
- The wrapper never reads `config.secretspec.secrets.*`.
- `secretspec` is available in devenv shells automatically when the integration is enabled.

#### Remove `node_modules/.bin` from PATH

The current `enterShell` prepends `node_modules/.bin` to PATH:

```nix
# CURRENT — remove this:
enterShell = lib.mkAfter ''
  export PATH="''${DEVENV_ROOT:-$PWD}/$MYPI_AGENT_ROOT/node_modules/.bin:$PATH"
  ${bootstrapCmd}
'';
```

Replace with:

```nix
# NEW — no PATH manipulation:
enterShell = lib.mkAfter ''
  ${bootstrapCmd}
'';
```

The `pi` wrapper calls the binary by absolute path. There is no need for `node_modules/.bin` on PATH, and having it there would let the raw binary shadow the wrapper.

### Python CLI changes

#### Remove `mypi pi` and `mypi agent` commands

These commands exec the raw Pi binary directly, bypassing the SecretSpec wrapper. With `scripts.pi` as the user-facing command, they are a secret-bypass hole.

Remove from `src/mypi_agent/cli.py`:

- `agent_command` (lines 82-97)
- `pi_command` (lines 100-115)

Users who need to run Pi without SecretSpec can use the raw binary path directly (available via `mypi paths`).

#### Do not add a `mypi secrets` command group

SecretSpec already provides a complete CLI:

```bash
secretspec check                    # verify required secrets exist
secretspec config show              # show provider/profile config
secretspec config init              # interactive provider setup
secretspec run -- <command>         # inject secrets into a process
secretspec get <NAME>               # retrieve a single secret
secretspec set <NAME> [VALUE]       # store a secret
secretspec init                     # create secretspec.toml
```

Building `mypi secrets check/env/doctor/init-spec` would duplicate SecretSpec's own interface. Users should use `secretspec` directly for all secret management tasks.

### Doctor changes

#### Keep `_secret_leak_likely()` as defense-in-depth

With SecretSpec as the architectural boundary, secrets cannot enter the `mypi` process environment and therefore cannot be written to generated config by mypi's own code. The existing `_secret_leak_likely()` check catches leaks from Pi or other external processes writing to mypi-managed paths.

Keep the current check as-is:

```python
def _secret_leak_likely(paths: Paths) -> bool:
    candidates = [paths.settings_path, paths.manifest_path]
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    for path in candidates:
        if path.exists() and any(marker in path.read_text(encoding="utf-8") for marker in markers):
            return True
    return False
```

Do not expand the file list or add more markers. The architecture prevents the problem; this check is a safety net, not a primary defence.

#### Add one new doctor check: `secretspec_available`

Add a warning (not error) when `secretspec` binary is not found:

```python
if shutil.which("secretspec") is None:
    warnings.append("secretspec_not_available")
    diagnostics.append({"code": "secretspec_not_available", "severity": "warning"})
```

This is a warning because SecretSpec availability depends on the devenv configuration, and some users may intentionally disable it (`piAgent.secrets.enable = false`).

### Allium spec changes

The current `core.allium` defines `SecretRuntimePolicy` with three fields and three invariants:

```
entity SecretRuntimePolicy {
    secrets_written_to_generated_config: Boolean
    secrets_available_at_evaluation_time: Boolean
    config_write_blocked: Boolean
}

invariant NoSecretPersistence { ... }
invariant NoEvalTimeSecrets { ... }
invariant SecretConfigWritesBlocked { ... }
```

With SecretSpec as the architectural boundary, these properties are enforced by the wrapper design, not by runtime state tracking. Simplify to a single architectural invariant:

```
invariant SecretsOnlyViaSecretSpec {
    -- Pi receives API keys only through the scripts.pi wrapper,
    -- which uses `secretspec run`. No mypi command or generated
    -- config file contains secret values.
}
```

Remove the `SecretRuntimePolicy` entity — its fields are not observable domain state.

## `.gitignore` additions

Add to consumer repo `.gitignore`:

```gitignore
# local devenv overrides
devenv.local.yaml
devenv.local.nix
```

Devenv already excludes `devenv.local.yaml` from evaluation, but the `.gitignore` entry prevents accidental commits.

The existing mypi-agent `.gitignore` already covers `.env` and related patterns.

## Testing strategy

### Test: `pi` wrapper receives secrets

Create a fake Pi binary and a temp dotenv file. Verify the wrapper injects keys.

Fake binary at `.agents/pi/node_modules/.bin/pi`:

```bash
#!/usr/bin/env bash
set -euo pipefail
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY_PRESENT=1"
else
  echo "ANTHROPIC_API_KEY_PRESENT=0"
fi
```

Expectation: `pi` outputs `ANTHROPIC_API_KEY_PRESENT=1`. Do not print the actual value.

### Test: `mypi` commands do not receive secrets

Verify that `ANTHROPIC_API_KEY` is not in the process environment when running `mypi doctor` or `mypi sync`.

### Test: `command -v pi` resolves to wrapper

```bash
command -v pi
```

Expected: devenv script wrapper path, not `$DEVENV_ROOT/.agents/pi/node_modules/.bin/pi`.

### Test: generated files do not contain test secret value

Set a canary value:

```
ANTHROPIC_API_KEY=mypi_test_secret_value_do_not_leak
```

Run `mypi sync`, `mypi doctor`, `pi --version`. Scan mypi-managed files:

```text
.pi/settings.json
.agents/pi/manifest.json
.agents/pi/.state/bootstrap.json
.agents/pi/.state/drift-report.json
.agents/pi/.state/installed-packages.json
.agents/pi/.state/primitive-registry.json
.agents/pi/.state/diagnostics.jsonl
```

Expectation: `mypi_test_secret_value_do_not_leak` appears in none of these files.

### Test fixture

Add `tests/fixtures/devenv/secretspec-runtime/`:

```text
tests/fixtures/devenv/secretspec-runtime/
  devenv.nix                    # piAgent.enable = true;
  devenv.yaml                   # imports mypi-agent
  secretspec.toml               # declares ANTHROPIC_API_KEY
  devenv.local.yaml.example     # example provider config (not used in test)
```

Do not commit real dotenv files. Generate temp dotenv files during test setup.

## Local setup guide

### 1. Configure your SecretSpec provider

The recommended approach is the system keyring (encrypted):

```bash
secretspec config init
```

Or for a simple dotenv setup:

```bash
mkdir -p ~/.config/mypi-agent
chmod 700 ~/.config/mypi-agent
cat > ~/.config/mypi-agent/secrets.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
EOF
chmod 600 ~/.config/mypi-agent/secrets.env
```

### 2. Add `secretspec.toml` to the repo

```bash
secretspec init
```

Or create manually:

```toml
[project]
name = "my-project"
revision = "1.0"

[profiles.default]
ANTHROPIC_API_KEY = { description = "Anthropic API key for Pi", required = false }
OPENAI_API_KEY = { description = "OpenAI API key for Pi", required = false }
OPENROUTER_API_KEY = { description = "OpenRouter API key for Pi", required = false }
```

### 3. Add local provider config

Create `devenv.local.yaml`:

```yaml
secretspec:
  enable: true
  provider: keyring
  profile: default
```

### 4. Verify and run

```bash
devenv shell
secretspec check       # verify secrets are available
mypi sync              # install/sync Pi
mypi doctor            # validate environment
pi                     # run Pi with injected secrets
```

## Security model

### What this protects against

- API keys committed to Git.
- Keys written into generated mypi config/state files.
- Keys exposed to every command in the devenv shell.
- Keys mixed into npm install state.
- Keys copied into the Nix store (the old `dotenv.enable` problem).

### What it does not protect against

- If using the dotenv provider, the central `.env` file is plaintext.
- If Pi itself logs its environment or writes keys to its own files, SecretSpec cannot prevent that.
- If a shell session exports API keys globally outside SecretSpec, any process in that shell may read them.

### Avoid the old devenv `.env` integration

Do not use this for API keys:

```nix
{ dotenv.enable = true; }
```

The devenv docs warn that the old `.env` integration copies values into the Nix store.

## Implementation checklist

### Nix module

- [ ] Add `piAgent.secrets.enable` option (default `true`).
- [ ] Add `scripts.pi` wrapper that calls the real binary by absolute path via `secretspec run`.
- [ ] Pass `--provider` / `--profile` from `config.secretspec.provider` / `config.secretspec.profile` when present.
- [ ] Do not read or export `config.secretspec.secrets.*`.
- [ ] Remove `node_modules/.bin` PATH prepending from `enterShell`.

### Python CLI

- [ ] Remove `mypi pi` command.
- [ ] Remove `mypi agent` command.

### Doctor

- [ ] Add `secretspec_not_available` warning check.
- [ ] Keep existing `_secret_leak_likely()` unchanged as defense-in-depth.

### Allium specs

- [ ] Replace `SecretRuntimePolicy` entity with single `SecretsOnlyViaSecretSpec` invariant.
- [ ] Update `doctor.allium` to reference the simplified invariant.

### Tests

- [ ] Add `secretspec-runtime` fixture.
- [ ] Assert `pi` wrapper injects secrets.
- [ ] Assert `mypi` commands do not receive secrets.
- [ ] Assert `command -v pi` resolves to wrapper, not raw binary.
- [ ] Assert generated files do not contain canary secret value.

### Docs

- [ ] Add README SecretSpec section.
- [ ] Add consumer setup example.
- [ ] Explain `devenv.local.yaml` provider config.
- [ ] Explain why not to use `dotenv.enable`.

## Troubleshooting

### `pi` says Pi is not installed

```bash
mypi sync
mypi doctor
mypi paths    # check pi_executable_path
```

### `pi` runs but no keys are available

```bash
secretspec check           # are secrets configured?
secretspec config show     # what provider is active?
```

Verify `devenv.local.yaml` has the correct provider. Verify secret names in `secretspec.toml` match what's stored in the provider.

### `secretspec check` fails

```bash
secretspec config init     # interactive provider setup
secretspec set ANTHROPIC_API_KEY    # set a missing secret
```

### Secret values appear in generated files

```bash
mypi doctor                # should report secret_leak_likely
rm -rf .agents/pi/.state
mypi sync                  # regenerate clean state
```

If the leak came from Pi itself rather than mypi-managed files, that is outside mypi-agent's control.

## References

- [Devenv SecretSpec integration](https://devenv.sh/integrations/secretspec/)
- [Devenv YAML options](https://devenv.sh/reference/yaml-options/)
- [Devenv dotenv warning](https://devenv.sh/integrations/dotenv/)
- [Devenv SecretSpec module source](https://github.com/cachix/devenv/blob/main/src/modules/integrations/secretspec.nix)
- [SecretSpec quick start](https://secretspec.dev/quick-start/)
- [SecretSpec CLI reference](https://secretspec.dev/reference/cli/)
- [SecretSpec providers](https://secretspec.dev/concepts/providers/)
- [SecretSpec profiles](https://secretspec.dev/concepts/profiles/)
