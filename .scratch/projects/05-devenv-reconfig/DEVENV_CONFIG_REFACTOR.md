# Devenv Config Refactor: Step-by-Step Guide

## Goal

Move the active development environment from `dev/` to the repository root so that:

1. `devenv shell` runs from repo root (fixing `$DEVENV_ROOT`)
2. Allium is available for MYPI-Agent development
3. Downstream consumers importing MYPI-Agent never receive Allium
4. Relative paths in Allium config (`../.scratch/specs`) become normal paths (`.scratch/specs`)

## Background

Read `DEVENV_CONFIG_CONCEPT.md` in this directory for the full rationale. The short version:

- **`devenv.yaml`** is a local composition file. When a downstream project imports MYPI-Agent as a remote input, the imported project's `devenv.yaml` is **not evaluated** — only `devenv.nix` is.
- Therefore, anything imported only through `devenv.yaml` (like allium-env) is invisible to consumers.
- The root `devenv.nix` is the public downstream import surface.

## Pre-conditions

- You are on the `main` branch with a clean working tree
- You have `devenv` >= 2.1 installed
- You can run `devenv shell` from the current `dev/` directory successfully

## File inventory

### Files that will be modified

| File | Change |
|---|---|
| `devenv.yaml` (root) | Add allium-env input, add imports, add version constraint |
| `.gitignore` | Add root-level `.devenv`, `.direnv`, runtime state entries |

### Files that will be created

| File | Purpose |
|---|---|
| `dev/allium/devenv.nix` | Allium option config (extracted from `dev/devenv.nix`) |

### Files that will be deleted

| File | Reason |
|---|---|
| `dev/devenv.yaml` | Replaced by root `devenv.yaml` |
| `dev/devenv.nix` | Split into root `devenv.yaml` imports + `dev/allium/devenv.nix` |
| `dev/devenv.lock` | Lock file moves to root (already gitignored) |
| `dev/.devenv/` | Runtime state directory, will regenerate at root |
| `dev/.agents/` | Runtime state, will regenerate at root |
| `dev/.pi/` | Runtime state, will regenerate at root |

### Files that will NOT change

| File | Reason |
|---|---|
| `devenv.nix` (root) | Already correct — imports `pi-agent.nix`, sets `mkDefault true` |
| `modules/pi-agent.nix` | No changes needed |
| `packages/mypi-agent-cli.nix` | No changes needed |
| `tests/fixtures/devenv/*` | Fixture updates are a separate step (Step 7) |

---

## Steps

### Step 1: Create a working branch

```sh
git checkout -b refactor/devenv-root-shell
```

---

### Step 2: Create `dev/allium/devenv.nix`

Extract the Allium-specific configuration from `dev/devenv.nix` into a new local module.

Create `dev/allium/devenv.nix`:

```nix
# dev/allium/devenv.nix
# Allium configuration for MYPI-Agent development only.
# This file is imported by root devenv.yaml and is NOT part of
# the public downstream import surface (root devenv.nix).
{ pkgs, ... }:

{
  allium.enable = true;
  allium.specsDir = ".scratch/specs";
  allium.codexSkills = {
    enable = true;
    autoInstall = true;
    targetDir = ".agents/skills";
  };
}
```

Note the path changes from the old `dev/devenv.nix`:
- `../.scratch/specs` → `.scratch/specs` (no more parent traversal)
- `../.agents/skills` → `.agents/skills` (no more parent traversal)

---

### Step 3: Update root `devenv.yaml`

Replace the current root `devenv.yaml` with:

```yaml
# devenv.yaml
# yaml-language-server: $schema=https://devenv.sh/devenv.schema.json

require_version: ">=2.1"

inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling
  nixpkgs-python:
    url: github:cachix/nixpkgs-python
  allium-env:
    url: github:Bullish-Design/allium-env?ref=v0.1.0
    flake: false

imports:
  - allium-env
  - ./dev/allium
```

What changed vs. the old root `devenv.yaml`:
- Added `require_version: ">=2.1"`
- Added `allium-env` input (moved from `dev/devenv.yaml`)
- Added `imports:` block importing `allium-env` and `./dev/allium`
- Removed commented-out `nix2container` / `mk-shell-bin` inputs (clean up)

What this does NOT do:
- It does not touch root `devenv.nix` — that file is the public surface and stays as-is

---

### Step 4: Decide what to do with non-Allium config from `dev/devenv.nix`

The old `dev/devenv.nix` contains both Allium config (handled in Step 2) and general dev tooling. Review each piece and decide where it goes:

| Config from `dev/devenv.nix` | Action | Destination |
|---|---|---|
| `allium.*` options | Moved to `dev/allium/devenv.nix` | Done in Step 2 |
| `packages = [ pkgs.git pkgs.uv ]` | Move to root if needed for dev | See below |
| `languages.python.*` | Move to root if needed for dev | See below |
| `env.GREET = "devenv"` | Drop (demo cruft) | N/A |
| `scripts.hello.exec` | Drop (demo cruft) | N/A |
| `enterShell` (hello + git version) | Drop or simplify | N/A |
| `enterTest` | Drop or move if useful | N/A |

For the Python/uv/git config, you have two choices:

**Dev Tooling** Add a `dev/devenv.nix` that contains only the non-Allium dev tooling (if needed) and import it from root `devenv.yaml`:

```yaml
# In root devenv.yaml imports:
imports:
  - allium-env
  - ./dev/allium
  - ./dev            # picks up dev/devenv.nix for Python/uv config
```

Then create a minimal `dev/devenv.nix`:

```nix
# dev/devenv.nix
# Non-Allium development tooling for MYPI-Agent.
{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.uv
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
  };
}
```

---

### Step 5: Update `.gitignore`

The root `.gitignore` already has most of the needed entries. Verify these lines exist (they should):

```gitignore
.devenv/**
.direnv/**
devenv.lock
.devenv.flake.nix
**/.devenv/**
**/.agents/**
**/.pi/**
```

These already cover the root-level runtime state that `devenv shell` will create. No changes should be needed, but double-check.

If you previously had entries specifically scoping `dev/.devenv` or similar, those are covered by the `**/.devenv/**` glob.

---

### Step 6: Delete old `dev/` environment files

Remove the files that are no longer needed:

```sh
# Remove the old standalone dev environment config
rm dev/devenv.yaml
rm dev/devenv.lock

# Remove runtime state (these are gitignored, but clean up local copies)
rm -rf dev/.devenv
rm -rf dev/.agents
rm -rf dev/.pi
```

**Do NOT delete:**
- `dev/allium/devenv.nix` (just created in Step 2)
- `dev/devenv.nix` (if you implemented one in Step 4)
- `dev/.coverage` or other non-devenv files in `dev/`

After this step, the `dev/` directory should contain:

```
dev/
  allium/
    devenv.nix          # Allium config (new)
  devenv.nix            # Python/uv dev tooling (Option A) or deleted (Option B)
  .coverage             # existing, unrelated
```

---

### Step 7: Test the new root environment

From the **repository root**:

```sh
devenv shell
```

Verify:
- [ ] Shell enters successfully
- [ ] `echo $DEVENV_ROOT` prints the repo root (not `dev/`)
- [ ] `which mypi` resolves (piAgent module is active)
- [ ] `mypi doctor` runs without errors
- [ ] `python --version` shows 3.13 (if Option A)
- [ ] `which uv` resolves (if Option A)
- [ ] Allium commands are available (check whatever allium-env provides)
- [ ] `.scratch/specs` is accessible without `../` prefix

If the shell fails:
- Run `devenv info` for diagnostics
- Check that `allium-env` input resolved correctly in the generated lock
- Check that `dev/allium/devenv.nix` has no syntax errors: `nix-instantiate --parse dev/allium/devenv.nix`

---

### Step 8: Update test fixtures to use `git+file:` inputs

The current fixtures use `path:__REPO_ROOT__` as a placeholder. The `path:` input type copies the entire directory (including gitignored files) into the Nix store, which doesn't faithfully simulate a remote `github:` import. The `git+file:` input type respects `.gitignore` and better mirrors production behavior.

Update fixture `devenv.yaml` files to document this. If `__REPO_ROOT__` is a test-time substitution (replaced by a test harness), keep the substitution pattern but change the URI scheme:

```yaml
# Before
inputs:
  mypi-agent:
    url: path:__REPO_ROOT__
    flake: false

# After
inputs:
  mypi-agent:
    url: git+file:__REPO_ROOT__
    flake: false
```

Apply this change to:
- `tests/fixtures/devenv/basic/devenv.yaml`
- `tests/fixtures/devenv/custom-root/devenv.yaml`
- `tests/fixtures/devenv/preserve-local-edits/devenv.yaml`
- `tests/fixtures/devenv/yaml-import-only/devenv.yaml`

**Important:** If the test harness substitutes `__REPO_ROOT__` at runtime, verify that `git+file:` works with the substituted path. `git+file:` requires the target to be a git repository and uses `git archive` semantics. If this causes issues in CI (e.g., shallow clones), you can keep `path:` as a fallback — document the trade-off in a comment.

---

### Step 9: Add a no-Allium-leak fixture (optional but recommended)

Create `tests/fixtures/devenv/no-allium-leak/`:

`tests/fixtures/devenv/no-allium-leak/devenv.yaml`:
```yaml
inputs:
  mypi-agent:
    url: git+file:__REPO_ROOT__
    flake: false
imports:
  - mypi-agent
```

`tests/fixtures/devenv/no-allium-leak/devenv.nix`:
```nix
{ ... }:

{
  tasks."fixture:verify".exec = ''
    set -euxo pipefail

    # piAgent should be enabled (default from root devenv.nix)
    command -v mypi

    # Allium should NOT be present
    if command -v allium 2>/dev/null; then
      echo "FAIL: allium binary found in downstream consumer environment"
      exit 1
    fi

    echo "PASS: no allium leak"
  '';
}
```

Adjust the `command -v allium` check to whatever binary or env var allium-env actually provides. The point is to assert that importing MYPI-Agent does not bring Allium along.

---

### Step 10: Commit

Stage the changes:

```sh
git add devenv.yaml
git add dev/allium/devenv.nix
git add dev/devenv.nix                      # if Option A
git add tests/fixtures/devenv/              # if fixtures changed
git add .gitignore                          # if changed
```

Verify nothing unexpected is staged:

```sh
git diff --cached --stat
```

Confirm that these files are NOT staged (they should be gitignored):
- `devenv.lock`
- `.devenv.flake.nix`
- `.devenv/`

Verify that the old `dev/devenv.yaml` deletion is staged:

```sh
git status
```

You should see `deleted: dev/devenv.yaml` in the staged changes. The old `dev/devenv.lock` was already gitignored so its deletion won't appear.

Commit:

```sh
git commit -m "Refactor: move devenv shell to repo root, isolate Allium in dev/"
```

---

## Final directory structure

```
mypi-agent/
  devenv.yaml               # Self-dev composition: imports allium-env + dev modules
  devenv.nix                # Public downstream surface: piAgent only, no Allium
  devenv.lock               # (gitignored) auto-generated lock

  dev/
    allium/
      devenv.nix            # Allium options for MYPI-Agent development
    devenv.nix              # Python/uv/git dev tooling (Option A)

  modules/
    pi-agent.nix            # Reusable piAgent devenv module

  packages/
    mypi-agent-cli.nix      # MYPI CLI package derivation

  tests/
    fixtures/
      devenv/
        basic/
        custom-root/
        preserve-local-edits/
        yaml-import-only/
        no-allium-leak/     # New: asserts Allium doesn't leak downstream
```

---

## Invariants to verify after merge

1. `devenv shell` from repo root → Allium available, `$DEVENV_ROOT` = repo root
2. `devenv shell` from repo root → `mypi doctor` passes
3. Root `devenv.nix` → grep confirms no mention of `allium`
4. Fixture `yaml-import-only` → `mypi` available, Allium absent
5. Fixture `no-allium-leak` → explicitly asserts no Allium binary/env

---

## Rollback

If something goes wrong:

```sh
git revert HEAD    # if already committed
# or
git checkout main  # if not committed, discard branch
```

The old `dev/` environment will continue to work as before since its `.devenv` state is local and gitignored.
