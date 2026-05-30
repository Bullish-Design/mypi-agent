# mypi-agent

`mypi-agent` is a devenv/Nix module that bootstraps Pi into a project-local agent root with a minimal public import surface.

## Public consumer surface

- `devenv.nix`
- `modules/pi-agent.nix`

Development-only wiring lives under `dev/` and is not part of the consumer import path.

## Runtime command surface

- `mypi sync [--trigger manual|shell] [--repair-shim] [--diff] [--json]`
- `mypi doctor [--json]`
- `mypi agent [args...]`
- `mypi pi [args...]`
- `mypi needs-sync [--trigger manual|shell]`
- `mypi paths [--json]`

## Module options

- `piAgent.root` (default `.agents/pi`)
- `piAgent.nodePackage` (default `pkgs.nodejs_22`)
- `piAgent.piPackageName` (default `@earendil-works/pi-coding-agent`)
- `piAgent.piPackageVersion` (default `"1.2.3"`)
- `piAgent.allowFloatingPiVersion` (default `false`)
- `piAgent.npmInstallFlags` (default `["--ignore-scripts","--no-audit","--no-fund"]`)
- `piAgent.bootstrap.mode` (`first_entry_only` | `manual_only` | `every_entry`)

## Generated files

Committed:

- `.pi/settings.json`

Optional to commit:

- `.agents/pi/manifest.json`

Runtime/install artifacts to ignore:

- `.agents/pi/node_modules/`
- `.agents/pi/.npm-cache/`
- `.agents/pi/bin/`
- `.agents/pi/.state/`
- `.agents/pi/npm-global/`

## Behavior notes

- Pi is exposed directly via `.agents/pi/node_modules/.bin/pi`.
- Pinned package version is enforced by default; floating requires explicit opt-in.
- `mypi sync` refuses user-owned/invalid `.pi/settings.json` unless `--repair-shim` is passed.

## Running repository commands

Use:

```bash
devenv shell -- <command>
```
