# AGENTS

## Project contract

This repository provides a repo-scoped MYPI/Pi bootstrap module for devenv/Nix consumers.

The public import surface must stay minimal and free of development-only dependencies.

## Public vs development environment

- Public consumer surface: root `devenv.nix` + `modules/pi-agent.nix`
- Development-only environment: `dev/` (including `allium-env`)

Do not re-introduce `allium-env` or other development-only wiring into the public root import path.

## Runtime command surface

Use `mypi` as the runtime control plane:

- `mypi sync`
- `mypi doctor`
- `mypi agent` / `mypi pi`
- `mypi needs-sync`
- `mypi paths`

## Test contract

Nix/devenv fixtures under `tests/fixtures/devenv/` are contract tests for consumer integration and module behavior.

Treat fixture behavior changes as API/contract changes, not local implementation details.

## Generated file policy

Commit:

- `.pi/settings.json`

Optional to commit:

- `.agents/pi/manifest.json`

Ignore runtime/install artifacts:

- `.agents/pi/node_modules/`
- `.agents/pi/.npm-cache/`
- `.agents/pi/bin/`
- `.agents/pi/.state/`
- `.agents/pi/npm-global/`

## Running repository commands

Run project commands inside devenv via:

```bash
./agent-devboot.sh <command>
```
