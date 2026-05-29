# MYPI-AGENT Completion Plan

**Date:** 2026-05-29
**Reference:** `.scratch/projects/01-mypi-agent-brainstorming/MYPI-AGENT_CONCEPT.md`
**Scope:** Everything remaining between the current implementation and the concept's full vision.

---

## 1. Current state summary

The implementation covers the concept's Phases 0–2 and part of Phase 3. A working Python CLI (`mypi`) provides `sync`, `doctor`, and `run` commands. The Nix module (`modules/pi-agent.nix`) exposes `piAgent.enable`, `piAgent.root`, and `piAgent.bootstrap.mode`. Sync creates the directory structure, writes the settings shim, installs the Pi CLI via npm, creates a launcher script, and writes a minimal manifest. Doctor checks for the shim, agent root, manifest validity, and secret leakage. Integration tests cover all implemented features including three devenv fixture scenarios.

### What works

- Directory creation: `.pi/`, `.agents/pi/`, resource subdirs, `.state/`
- Settings shim: `.pi/settings.json` with `x-mypi-agent` metadata
- Manifest: created and self-healed when corrupt
- Pi CLI: installed via npm, launcher at `.agents/pi/bin/pi-agent`
- Doctor: four checks (shim, root, manifest, secret leak)
- Nix module: three bootstrap modes, custom root, shell entry hook
- CLI: `--json` output, `--trigger`, `--repair-shim`
- Tests: ~25 integration tests across 7 test files plus 3 devenv fixtures

### Implementation choices that diverge from concept

| Area | Concept | Implementation | Assessment |
|---|---|---|---|
| Language | Shell scripts | Python + Pydantic + Typer | Better choice — keep |
| Command name | `pi-agent sync/doctor/paths` | `mypi sync/doctor/run` | Reasonable — `pi-agent` is the Pi launcher |
| Bootstrap modes | `copy-if-missing` / `manual` | `first_entry_only` / `manual_only` / `every_entry` | More expressive — keep |
| Surfaces layer | Not in concept | `surfaces_runtime.py` actor checks | Addition — evaluate if worth keeping |
| State dir | `.agents/pi/state/` | `.agents/pi/.state/` | Hidden vs visible — minor, pick one |

---

## 2. Remaining work by concept section

### 2.1 Nix option schema (Concept §14)

**Status:** Minimal. Only 3 of ~25 planned options exist.

**Missing options to add to `modules/pi-agent.nix`:**

```
piAgent.sync.mode                    # "copy-if-missing" (default)
piAgent.sync.preserveLocalChanges    # true (default)
piAgent.sync.upgradeMode             # "manual" (default)
piAgent.sync.writeGitignore          # true (default)
piAgent.sync.writeSettingsShim       # true (default)

piAgent.primitives.core.enable       # true (default)
piAgent.primitives.enable            # list of additional primitive IDs
piAgent.primitives.disable           # list of primitive IDs to exclude

piAgent.resources.extensions.enable  # true
piAgent.resources.extensions.include # []
piAgent.resources.extensions.exclude # []
piAgent.resources.skills.enable      # true
piAgent.resources.skills.include     # []
piAgent.resources.skills.exclude     # []
piAgent.resources.prompts.enable     # true
piAgent.resources.prompts.include    # []
piAgent.resources.prompts.exclude    # []
piAgent.resources.themes.enable      # true
piAgent.resources.themes.include     # []
piAgent.resources.themes.exclude     # []

piAgent.models.enable                # true
piAgent.models.file                  # "models/models.json"

piAgent.providers.enable             # true

piAgent.packages                     # list of { name, source } package declarations

piAgent.secrets.mode                 # "runtime"
piAgent.secrets.envFiles             # [ "~/.config/pi-agent/env" ]
piAgent.secrets.secretspec.enable    # false

piAgent.pi.package                   # null (default pinned Pi CLI)
piAgent.pi.executable                # "pi"
```

**Work required:**

1. Define all option types with `lib.mkOption` in `pi-agent.nix`.
2. Pass resolved option values to the Python CLI via environment variables or a generated JSON config file.
3. The Python CLI must read these values instead of using hardcoded defaults.
4. Ensure Nix evaluation never reads secret file contents — only passes paths.

**Suggested approach:** Generate a `$MYPI_CONFIG` JSON file at Nix eval time containing all non-secret option values. The Python CLI reads it at runtime. Secret env file paths are passed but never read during Nix eval.

---

### 2.2 Desired-state hash (Concept §10.3)

**Status:** Not implemented.

The concept requires a hash derived from:
- Module version
- Resolved primitive versions
- `piAgent.*` option values
- Configured root path
- Package declarations
- Resource filters

**Work required:**

1. Compute the hash in Nix from the resolved config and pass it via the generated config or environment.
2. Store the hash in `manifest.json` as `desiredStateHash`.
3. On shell entry, compare stored hash to current hash.
4. If changed, print advisory: `MYPI-AGENT: module version changed; run 'mypi sync --diff' to inspect available updates`.
5. Never auto-upgrade — only inform.

---

### 2.3 Primitive registry and versioning (Concept §11, Phase 4)

**Status:** Not implemented. This is the largest missing subsystem.

**Files to create:**

```
primitives/registry.json            # master list of available primitives
primitives/core/primitive.json      # core primitive group metadata
primitives/core/skills/doctor/SKILL.md
primitives/core/extensions/README.md
primitives/core/prompts/README.md
primitives/core/themes/README.md
primitives/core/models/models.example.json
primitives/core/providers/README.md
```

**`primitives/registry.json` schema:**

```json
{
  "schemaVersion": 1,
  "primitives": {
    "core-settings-shim": {
      "version": "0.1.0",
      "type": "shim",
      "path": "core/settings.json.tpl",
      "default": true,
      "description": "Pi settings compatibility shim."
    },
    "core-root-readme": {
      "version": "0.1.0",
      "type": "readme",
      "path": "core/README.md",
      "default": true,
      "description": "Root README explaining agent layout."
    },
    "core-doctor-skill": {
      "version": "0.1.0",
      "type": "skill",
      "path": "core/skills/doctor",
      "default": true,
      "description": "Diagnostic skill for checking setup."
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

**Work required:**

1. Create the registry file and all primitive source files listed in §24 of the concept.
2. Write a `README.md` template for the agent root (concept §25).
3. Write the doctor skill markdown (concept §26).
4. Write the example models file.
5. Write per-directory READMEs (extensions, skills, prompts, themes, packages, models, providers).
6. Update `sync.py` to:
   - Read the registry.
   - Copy primitive files to the target when missing.
   - Record installed primitives in manifest with version, source hash, install timestamp, and file list.
   - Respect `piAgent.primitives.enable` / `piAgent.primitives.disable` filters.
7. Update `manifest.json` to the concept's richer schema:

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
      "files": ["skills/doctor/SKILL.md"]
    }
  }
}
```

8. Implement file-state classification for upgrade support:
   - Missing: copy current version.
   - Unchanged (hash matches old source): safe to upgrade.
   - Locally modified (hash differs): preserve and report.
   - Unknown (not in manifest): preserve.

---

### 2.4 Sync improvements (Concept §10, §16.2)

**Status:** Basic sync works. Missing: diff, upgrade, gitignore, and local-change detection.

**Missing commands / flags:**

| Command | Purpose |
|---|---|
| `mypi sync --diff` | Show what would change without applying |
| `mypi sync --upgrade <primitive>` | Upgrade a single primitive |
| `mypi sync --upgrade all` | Upgrade all primitives |
| `mypi sync --repair-shim` | Already implemented |

**Missing behaviors:**

1. **Gitignore generation** — Sync should write `.agents/pi/.gitignore` (or append to project root `.gitignore`) with:
   ```
   .state/
   **/node_modules/
   **/.cache/
   ```
   Controlled by `piAgent.sync.writeGitignore`.

2. **Local change preservation** — Before overwriting during `--upgrade`, compare current file hash against stored `sourceHash`. If different, skip and warn. Currently `existing_files_overwritten` is hardcoded to `False` — this needs to become dynamic.

3. **Diff output** — `--diff` should print a summary of what sync would do:
   ```
   would create: skills/doctor/SKILL.md (core-doctor-skill v0.1.0)
   would upgrade: models/models.example.json (0.1.0 -> 0.2.0)
   preserved (locally modified): extensions/README.md
   ```

4. **Selective upgrade** — `--upgrade <id>` must look up the primitive in the registry, compare versions, check for local modifications, and copy the new version (recording the new hash).

---

### 2.5 Paths command (Concept §16.4)

**Status:** Not implemented.

**Work required:**

Add `mypi paths` command that prints:

```
Project root:        /home/andrew/src/example
Pi settings shim:    /home/andrew/src/example/.pi/settings.json
Agent root:          /home/andrew/src/example/.agents/pi
Manifest:            /home/andrew/src/example/.agents/pi/manifest.json
Pi executable:       .agents/pi/bin/pi-agent
State dir:           /home/andrew/src/example/.agents/pi/.state
```

Should also support `--json` for machine consumption.

---

### 2.6 Doctor improvements (Concept §16.3, Phase 3)

**Status:** Partially implemented. Four checks exist. Several concept checks are missing.

**Missing checks:**

| Check | Description |
|---|---|
| Resource directories exist | Verify `extensions/`, `skills/`, `prompts/`, `themes/` all present |
| Settings shim points to configured root | Currently only checks for `../.agents/pi` hardcoded string in `surfaces_runtime.py`; should use the actual configured root |
| Pi executable found | Verify the launcher at `bin/pi-agent` exists and is executable |
| Runtime env files readable | If `piAgent.secrets.envFiles` configured, warn if files don't exist (not an error — they're optional) |
| Package sources pinned | Warn about unpinned git branches or floating npm ranges in `piAgent.packages` |
| Required directories from manifest | Cross-reference manifest `resources` against actual directories |
| State dir exists | Verify `.state/` exists |
| Manifest has expected primitives | Cross-reference registry defaults against installed manifest |

**Current bugs / issues:**

- `surfaces_runtime.py:22` hardcodes `"../.agents/pi"` instead of using the dynamic root. This means custom-root configurations will fail the actor check.
- Doctor doesn't check resource subdirectories.
- Doctor doesn't check the Pi launcher exists.

---

### 2.7 Template files (Concept §6.3, §24, §25, §26)

**Status:** Not implemented. Sync creates empty directories but no template content.

**Files the concept says should be materialized:**

| File | Location in agent root | Content |
|---|---|---|
| Root README | `README.md` | Concept §25 — explains layout, commands, secrets policy |
| Doctor skill | `skills/doctor/SKILL.md` | Concept §26 — Pi-readable diagnostic skill |
| Example models | `models/models.example.json` | Concept §19.1 — shape example with `env:` references, no secrets |
| Extensions README | `extensions/README.md` | Brief explanation of the extensions directory |
| Skills README | `skills/README.md` | Brief explanation of the skills directory |
| Prompts README | `prompts/README.md` | Brief explanation of the prompts directory |
| Themes README | `themes/README.md` | Brief explanation of the themes directory |
| Packages README | `packages/README.md` | Brief explanation of the packages directory |
| Models README | `models/README.md` | Brief explanation of the models directory |
| Providers README | `providers/README.md` | Brief explanation of the providers directory |

These files should be stored in `primitives/core/` in the library repo and copied by sync.

---

### 2.8 Settings shim improvements (Concept §8)

**Status:** Partially implemented. Shim is generated but missing some fields.

**Current shim output:**

```json
{
  "packages": [],
  "extensions": ["../.agents/pi/extensions"],
  "skills": ["../.agents/pi/skills"],
  "prompts": ["../.agents/pi/prompts"],
  "themes": ["../.agents/pi/themes"],
  "enableSkillCommands": true,
  "x-mypi-agent": {
    "agentRoot": "../.agents/pi"
  }
}
```

**Concept says it should also include:**

```json
{
  "models": "../.agents/pi/models/models.json",
  "sessionDir": "../.agents/pi/state/sessions"
}
```

**Work required:**

1. Add `models` field pointing to configured models file.
2. Add `sessionDir` pointing to state/sessions.
3. Verify these field names against actual Pi documentation — the concept flags this as needing verification.
4. Add glob patterns for extensions as concept shows: `"../.agents/pi/extensions/**/*.ts"` with node_modules exclusion.

---

### 2.9 Package source model (Concept §15, Phase 5)

**Status:** Not implemented.

**Work required:**

1. Add `piAgent.packages` Nix option accepting list of `{ name, source }` attrsets.
2. Validate source format at Nix eval time:
   - `git:` sources must have `?rev=` or `?tag=`.
   - `npm:` sources must have exact version (`@0.1.0` not `@^0.1.0`).
   - Local paths are allowed.
3. Pass package declarations to the Python CLI via generated config.
4. Sync should record declared packages in the manifest.
5. Doctor should warn about unpinned sources.
6. Actual package installation can be delegated to Pi initially — `mypi-agent` only needs to declare and validate.

---

### 2.10 Secrets integration (Concept §18, Phase 6)

**Status:** Stub. `runtime.py` returns hardcoded values. No actual env file loading.

**Work required:**

1. **Env file wrapper** — The `pi-agent` shell wrapper in `pi-agent.nix` should load configured env files before exec:
   ```bash
   set -a
   [ -f "$HOME/.config/pi-agent/env" ] && . "$HOME/.config/pi-agent/env"
   set +a
   exec "$launcher" "$@"
   ```
   The env file paths should come from `piAgent.secrets.envFiles`.

2. **Runtime policy evaluation** — Replace the hardcoded `evaluate_runtime_policy()` with actual logic:
   - Check if configured env files exist.
   - Report which are missing.
   - Never read env file contents — only check existence.
   - Never write env values into any generated file.

3. **SecretSpec stub** — If `piAgent.secrets.secretspec.enable = true`, generate a `secretspec.toml` declaring expected secret names (without values). This is a future integration point — the initial work is just the declaration file.

4. **Doctor integration** — Doctor should report:
   - Whether runtime env files are configured.
   - Whether configured env files exist on disk (warning, not error).
   - Whether any generated config files contain likely secret values (already done).

---

### 2.11 Pi CLI packaging (Concept §6.2)

**Status:** Partially implemented. Pi is installed via npm at sync time. The concept also describes a Nix-level package.

**Current approach:** `sync.py` runs `npm install @earendil-works/pi-coding-agent` into the agent root's `node_modules/`. A shell launcher wraps it.

**Concept's preferred approach:** A pinned Nix derivation (`packages/pi-agent-wrapper.nix`) that builds Pi from npm or a GitHub release, so Pi is available immediately in the devenv shell without requiring a sync first.

**Work required:**

1. Create `packages/pi-agent-wrapper.nix` that builds the Pi CLI from the npm package using `buildNpmPackage` or `mkDerivation` + npm.
2. Make `piAgent.pi.package` default to this derivation.
3. The `pi-agent` shell script should prefer the Nix-provided binary, falling back to the sync-installed one.
4. Remove or make optional the npm install step in `sync.py` — it should only be needed when the Nix package isn't available.

This is medium priority. The current npm-at-sync-time approach works but is less reproducible.

---

### 2.12 Shell entry messages (Concept §17)

**Status:** Not implemented. The Nix module runs sync silently (`>/dev/null 2>&1`).

**Concept expects:**

```
MYPI-AGENT: initialized .agents/pi and .pi/settings.json
```

```
MYPI-AGENT: ready (.agents/pi)
```

```
MYPI-AGENT: module version changed; run `mypi sync --diff` to inspect available updates
```

**Work required:**

1. Remove the output suppression in the shell entry hook.
2. Have sync output a one-line status message to stderr (not stdout, to avoid polluting pipes).
3. Implement desired-state hash comparison (§2.2) to detect version changes.

---

### 2.13 Git strategy (Concept §20)

**Status:** Not implemented. No `.gitignore` is generated.

**Work required:**

1. Sync should create `.agents/pi/.gitignore` containing:
   ```
   .state/
   **/node_modules/
   **/.cache/
   ```
2. Controlled by `piAgent.sync.writeGitignore` option.

---

### 2.14 Testing gaps (Concept §22)

**Status:** Good coverage for implemented features. Missing tests for unimplemented features, plus some gaps in existing coverage.

**Tests to add for existing features:**

| Test | Description |
|---|---|
| Custom root via `MYPI_AGENT_ROOT` | Verify sync and doctor honor the env var for a non-default root |
| Settings shim path accuracy | Verify shim paths match the configured root, not just `.agents/pi` |
| Sync idempotency | Run sync twice, verify second run creates nothing new |
| Manifest not overwritten | Write custom manifest, run sync, verify it's preserved |

**Tests to add for new features (as they're implemented):**

| Test | Maps to concept §22.2 |
|---|---|
| Primitive files materialized | Sync copies doctor skill, README, etc. into agent root |
| Primitive not overwritten | Edit a primitive file, re-sync, verify edit preserved |
| Upgrade replaces unchanged file | Install v0.1.0, update registry to v0.2.0, upgrade, verify new content |
| Upgrade preserves modified file | Modify file, attempt upgrade, verify preserved + warning |
| Diff output accuracy | `--diff` reports correct would-create/would-upgrade/preserved |
| Desired-state hash changes | Change Nix options, verify hash differs |
| Gitignore created | Verify `.gitignore` in agent root after sync |
| Paths command output | Verify all paths printed correctly |
| Env file existence check | Configure env file path, verify doctor reports missing |
| Secret leak in manifest | Put a secret in manifest.json, verify doctor catches it |
| Package source validation | Declare unpinned package, verify doctor warns |
| Resource directory check | Delete a resource dir after sync, verify doctor reports it |

**Devenv fixture improvements:**

The existing 3 fixtures (`basic`, `custom-root`, `preserve-local-edits`) are structurally correct but their `fixture:verify` tasks only run `mypi sync && mypi doctor`. They should add assertions for:

- Specific files exist after sync.
- Custom root is actually at the configured path.
- Local edits are preserved when `bootstrap.mode = "manual_only"`.

**Missing fixture scenarios from concept §22.1:**

| Fixture | Purpose |
|---|---|
| `fixture-upgrade-available` | Module version changed, verify advisory shown |
| `fixture-private-package-declared` | Package source declared, verify manifest records it |

---

## 3. Bugs and issues in current implementation

### 3.1 Hardcoded root in surfaces_runtime.py

`surfaces_runtime.py:22` checks for `"../.agents/pi"` literally:

```python
points_to_configured_root = "../.agents/pi" in text
```

This breaks when `piAgent.root` is anything other than `.agents/pi`. Should derive the expected string from `paths.agent_root`.

### 3.2 State directory naming

The implementation uses `.state/` (hidden). The concept uses `state/` (visible). Pick one and document it. The hidden form is arguably better since it's runtime-only and shouldn't be browsed, but it should be consistent with documentation.

### 3.3 Bootstrap state files always overwritten

`sync.py:102` unconditionally writes `bootstrap.json` on every sync, and `sync.py:106-107` unconditionally overwrites `drift-report.json` and `installed-packages.json`. The concept says existing files should not be overwritten. State files may be an exception, but this should be a deliberate choice, not accidental.

### 3.4 `existing_files_overwritten` always False

`sync.py:156` hardcodes `existing_files_overwritten=False`. Once upgrade support is added, this must become dynamic.

### 3.5 npm install runs on every sync

`sync.py:109-147` runs `npm install` every time sync runs, even if Pi is already installed. Should check if `node_modules/.bin/pi` exists and skip if present (unless `--upgrade` is requested).

### 3.6 `run` command purpose unclear

`cli.py:49-55` exposes `mypi run` which evaluates a hardcoded runtime policy. The concept has no `run` command — it has `pi-agent` (the wrapper), `pi-agent sync`, `pi-agent doctor`, and `pi-agent paths`. Decide whether `run` should become `paths`, be removed, or serve a different purpose.

---

## 4. Priority ordering

### High priority (core functionality gaps)

1. **Fix hardcoded root in surfaces_runtime.py** — Bug, breaks custom roots.
2. **Primitive registry and template files** — The main missing feature. Without this, sync creates empty directories with no useful content.
3. **Rich manifest schema** — Needed before primitives can be versioned and upgraded.
4. **Gitignore generation** — Prevents accidental commits of state and node_modules.
5. **Skip npm install when already present** — Performance issue on every sync.

### Medium priority (concept completeness)

6. **Desired-state hash** — Enables upgrade advisories.
7. **Paths command** — Small, useful, quick to add.
8. **Sync diff and upgrade commands** — Core lifecycle management.
9. **Doctor improvements** — More checks, dynamic root validation.
10. **Shell entry messages** — User feedback on bootstrap status.
11. **Settings shim improvements** — Add `models` and `sessionDir` fields.
12. **Expanded Nix option schema** — Full `piAgent.*` surface.

### Lower priority (future phases)

13. **Package source model** — Concept Phase 5.
14. **Env file wrapper in pi-agent script** — Concept Phase 6.
15. **Runtime policy evaluation** — Replace hardcoded stub.
16. **SecretSpec integration** — Concept Phase 6.
17. **Nix-level Pi CLI packaging** — Replace npm-at-sync with Nix derivation.
18. **CI/headless support** — Concept Phase 7.
19. **Resource filters** — Include/exclude in Nix options.

---

## 5. Estimated scope

| Category | Items | Rough size |
|---|---|---|
| Bug fixes | 3.1, 3.5 | Small |
| Primitive system | Registry, templates, manifest, copy logic, hash tracking | Large |
| Sync improvements | Diff, upgrade, gitignore, idempotent npm | Medium |
| New commands | `paths` | Small |
| Doctor improvements | 6+ new checks, dynamic root | Medium |
| Nix options | ~20 new options + config passing | Medium |
| Secrets | Env file wrapper, runtime policy, existence checks | Medium |
| Package sources | Nix option, validation, manifest recording | Medium |
| Testing | ~15 new test cases, fixture improvements | Medium |
| Shell UX | Entry messages, desired-state hash | Small |

The primitive registry and versioning system (item 2 in §4) is the single largest piece of remaining work and the foundation that most other improvements depend on.
