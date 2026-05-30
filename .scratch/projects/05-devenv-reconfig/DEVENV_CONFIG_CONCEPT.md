# DEVENV Config Concept for MYPI-Agent

## Decision

Use the repository root as the MYPI-Agent development environment, including Allium, but keep the root `devenv.nix` public-safe and Allium-free.

The core boundary is:

```text
mypi-agent/devenv.yaml  = self-development composition; may import allium-env
mypi-agent/devenv.nix   = downstream import surface; must not import or configure Allium
```

This lets MYPI-Agent developers run `devenv shell` from the repository root and get Allium, while downstream projects can import MYPI-Agent without inheriting Allium.

---

## Why this works with current devenv behavior

Current devenv documentation supports this model:

1. `devenv.nix` is the only required file for specifying a developer environment.
2. `devenv.yaml` is for inputs and imports: it defines how dependencies and composed environments are wired together.
3. `$DEVENV_ROOT` points to the project root where `devenv.nix` is located. Keeping the active environment at repo root avoids the current `dev/` directory problem.
4. For remote/input imports, the imported repository must use `devenv.nix`; the imported repository's `devenv.yaml` is not evaluated.
5. Local filesystem imports can merge both `devenv.nix` and `devenv.yaml`, so direct local root imports are not the safest downstream testing pattern.
6. `devenv.yaml` supports `inputs`, `imports`, and `require_version`, including explicit version constraints such as `>=2.1`.

Practical result: if Allium is only imported through this repository's root `devenv.yaml`, it is available while developing MYPI-Agent itself, but it is not part of the reusable downstream import surface exposed by root `devenv.nix`.

---

## Recommended repository structure

```text
mypi-agent/
  devenv.yaml                  # self-dev composition; imports allium-env
  devenv.nix                   # public downstream import surface; no Allium
  devenv.lock                  # pins this repo's self-dev inputs

  dev/
    allium/
      devenv.nix               # MYPI-Agent-only Allium option configuration

  modules/
    pi-agent.nix               # reusable MYPI/Pi devenv module

  packages/
    mypi-agent-cli.nix         # MYPI CLI package derivation

  src/
    mypi_agent/

  tests/
    fixtures/
      devenv/
```

The `dev/allium` directory is not a standalone devenv project. It is only a local configuration module imported by the root `devenv.yaml` when developing this repository.

---

## Root `devenv.yaml`

```yaml
# devenv.yaml
# yaml-language-server: $schema=https://devenv.sh/devenv.schema.json

require_version: ">=2.1"

inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling

  allium-env:
    url: github:Bullish-Design/allium-env
    flake: false

imports:
  - allium-env
  - ./dev/allium
```

Purpose:

- Imports Allium for MYPI-Agent development.
- Imports the local `./dev/allium` configuration module.
- Keeps Allium out of the public `devenv.nix` import surface.
- Keeps active development at repository root, so `$DEVENV_ROOT` remains the real repo root.

---

## Root `devenv.nix`

```nix
# devenv.nix
{ lib, ... }:

{
  imports = [
    ./modules/pi-agent.nix
  ];

  piAgent.enable = lib.mkDefault true;
}
```

Rules for this file:

- It is the downstream public import contract.
- It may import only MYPI-Agent public modules.
- It must not import `allium-env`.
- It must not set `allium.*` options.
- It should use `lib.mkDefault` for defaults that downstream projects may override.

This file is what downstream projects get when they import MYPI-Agent as a devenv input.

---

## Dev-only Allium configuration

```nix
# dev/allium/devenv.nix
{ pkgs, ... }:

{
  # Exact option names should match allium-env's current module API.
  allium.enable = true;

  allium.specsDir = ".scratch/specs";

  allium.codexSkills = {
    enable = true;
    autoInstall = true;
    targetDir = ".agents/skills";
  };

  packages = [
    pkgs.git
  ];

  enterShell = ''
    echo "MYPI-Agent development shell with Allium enabled"
  '';
}
```

Purpose:

- Keeps Allium option configuration outside the public downstream import surface.
- Allows root `devenv shell` to include Allium for this repository.
- Makes the dev-only Allium configuration easy to find and remove if needed.

---

## Downstream consumer usage

Remote/GitHub consumer:

```yaml
# consumer-project/devenv.yaml
# yaml-language-server: $schema=https://devenv.sh/devenv.schema.json

inputs:
  mypi-agent:
    url: github:Bullish-Design/mypi-agent?ref=v0.3.0
    flake: false

imports:
  - mypi-agent
```

Downstream override example:

```nix
# consumer-project/devenv.nix
{ ... }:

{
  piAgent = {
    enable = true;
    root = ".agents/pi";
  };
}
```

This consumer receives the MYPI-Agent root `devenv.nix`, so it gets the `piAgent` module and defaults. It does not evaluate MYPI-Agent's root `devenv.yaml`, so it does not receive Allium.

---

## Local fixture/testing usage

For local testing, prefer a path input instead of a direct local filesystem import:

```yaml
# tests/fixtures/devenv/basic/devenv.yaml
inputs:
  mypi-agent:
    url: path:../../..
    flake: false

imports:
  - mypi-agent
```

Avoid using direct relative root imports for normal consumer fixtures:

```yaml
# Avoid for supported consumer-path tests
imports:
  - ../../..
```

Reason: current devenv local filesystem imports can merge both `devenv.nix` and `devenv.yaml`. A direct local import of the MYPI-Agent root can therefore pull in root `devenv.yaml`, including Allium. A `path:` input exercises the same import style as the intended remote consumer path.

Recommended fixtures:

```text
tests/fixtures/devenv/
  path-input-basic/
    devenv.yaml
    devenv.nix

  path-input-custom-root/
    devenv.yaml
    devenv.nix

  path-input-no-allium-leak/
    devenv.yaml
    devenv.nix

  direct-local-root-import-unsupported/
    devenv.yaml
    README.md
```

The unsupported fixture should document the failure mode rather than treating it as the recommended path.

---

## Invariants to enforce

1. `devenv shell` from the MYPI-Agent repository root includes Allium.
2. Downstream `imports: - mypi-agent` includes MYPI-Agent/Pi bootstrap behavior.
3. Downstream `imports: - mypi-agent` does not include Allium.
4. Root `devenv.nix` never mentions `allium-env` or `allium.*`.
5. Root `devenv.yaml` may import `allium-env` because it is only part of this repository's self-development composition.
6. Local downstream tests use `inputs.<name>.url = path:...` plus `imports: - <name>`, not direct `imports: - ../../..`.
7. The README documents `inputs + imports` as the only supported downstream contract.

---

## README wording

Add a short import-contract section:

```md
## Import contract

MYPI-Agent is imported as a devenv input:

```yaml
inputs:
  mypi-agent:
    url: github:Bullish-Design/mypi-agent?ref=v0.3.0
    flake: false

imports:
  - mypi-agent
```

The repository root `devenv.yaml` is for developing MYPI-Agent itself and may include maintainer-only tools such as Allium. Downstream projects should not directly import the repository path as a local filesystem import. For local testing, use a `path:` input so the behavior matches remote input imports.
```

---

## Migration plan from the current `dev/` split

1. Move the current `dev/devenv.yaml` Allium input/import content to root `devenv.yaml`.
2. Move Allium option settings into `dev/allium/devenv.nix`.
3. Keep root `devenv.nix` as the public MYPI-Agent import surface.
4. Remove the standalone `dev/devenv.nix` environment.
5. Update `.gitignore` to keep `dev/.devenv`, `.devenv`, `.agents`, `.pi`, npm caches, and runtime state out of git.
6. Update test fixtures to use `path:` input imports.
7. Add a test that checks Allium is absent from downstream config.

---

## Validation commands

For MYPI-Agent self-development:

```sh
devenv shell
```

Expected:

- `$DEVENV_ROOT` is the MYPI-Agent repository root.
- Allium commands/config are available.
- MYPI-Agent source, tests, modules, and packages are addressed relative to the real repo root.

For downstream fixture testing:

```sh
cd tests/fixtures/devenv/path-input-basic
devenv shell -- mypi doctor
```

Expected:

- `mypi` is available.
- Pi bootstrap behavior is available.
- Allium is not available unless the fixture explicitly imports Allium itself.

Optional config check:

```sh
devenv eval piAgent.enable
```

Expected result in a consumer fixture:

```json
true
```

---

## Conclusion

The concept is sound for MYPI-Agent.

Use root `devenv.yaml` for MYPI-Agent's own development composition, including Allium. Use root `devenv.nix` as the Allium-free public import surface that downstream devenv projects receive. Test downstream behavior through `path:` inputs rather than direct local filesystem root imports.

This gives MYPI-Agent the desired development ergonomics without passing Allium into consuming projects.

---

## Documentation sources checked

- devenv Polyrepo guide: https://devenv.sh/guides/polyrepo/
- devenv Composing using imports: https://devenv.sh/composing-using-imports/
- devenv Files and variables: https://devenv.sh/files-and-variables/
- devenv YAML options reference: https://devenv.sh/reference/yaml-options/
- devenv Inputs: https://devenv.sh/inputs/
- devenv 1.10 monorepo import behavior: https://devenv.sh/blog/2025/10/07/devenv-110-monorepo-nix-support-with-devenvyaml-imports/
- devenv 2.0 update notes: https://devenv.sh/blog/2026/03/05/devenv-20-a-fresh-interface-to-nix/
