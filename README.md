# mypi-agent

`mypi-agent` is a devenv/Nix module that bootstraps Pi in a project-local, reproducible way.

## Consumer setup

Add to `devenv.yaml`:

```yaml
inputs:
  mypi-agent:
    url: path:/path/to/mypi-agent
    flake: false
imports:
  - mypi-agent
```

The module auto-enables itself by default from the root public surface (`devenv.nix` imports `./modules/pi-agent.nix` and sets `piAgent.enable = mkDefault true`).

## What this provides

- `mypi` on `PATH`
- Node/npm/npx on `PATH` (default `pkgs.nodejs_22`)
- Repo-scoped npm prefix/cache under `piAgent.root` (no global npm state required)
- Optional shell bootstrap sync on shell entry (`piAgent.bootstrap.mode`)

## Commands

- `mypi sync [--trigger manual|shell] [--repair-shim] [--diff] [--json]`
- `mypi doctor [--json]`
- `mypi agent [args...]` (or alias: `mypi pi`)
- `mypi needs-sync [--trigger manual|shell]`
- `mypi paths [--json]`

## Configuration

Module options (in `piAgent`):

- `root` (default `.agents/pi`)
- `nodePackage` (default `pkgs.nodejs_22`)
- `piPackageName` (default `@earendil-works/pi-coding-agent`)
- `piPackageVersion` (default `null`; set for deterministic pinned installs)
- `npmInstallFlags` (default `["--ignore-scripts","--no-audit","--no-fund"]`)
- `bootstrap.mode` (`first_entry_only` | `manual_only` | `every_entry`)
- `exposePiAgentShim` (`false` by default)

## Generated files

Primary generated files:

- `.pi/settings.json`
- `.agents/pi/manifest.json`
- `.agents/pi/.state/` (bootstrap/registry/state files)
- `.agents/pi/bin/pi-agent` (launcher when installed)

## Commit / ignore policy

Commit:

- `.pi/settings.json`

Optional to commit:

- `.agents/pi/manifest.json`

Ignore:

- `.agents/pi/node_modules/`
- `.agents/pi/.npm-cache/`
- `.agents/pi/bin/`
- `.agents/pi/.state/`
- `.agents/pi/npm-global/`

## Pinning and reproducibility

For deterministic Pi installs, set `piAgent.piPackageVersion`. `mypi sync` records installed Pi metadata in manifest and registry state.

## Root override

Set `piAgent.root` to move the managed agent directory (for example, `.agents/custom-pi`). The settings shim and runtime paths follow this value.

## Disable shell bootstrap

Set:

```nix
piAgent.bootstrap.mode = "manual_only";
```

Then run sync explicitly as needed.

## Troubleshooting

- `mypi doctor` reports actionable runtime/config errors.
- If Pi is missing or not executable, run `mypi sync` and re-run `mypi doctor`.
- If project-root discovery fails outside a devenv-managed tree, use `--allow-unmanaged` only for controlled cases (tests/sandboxes).
