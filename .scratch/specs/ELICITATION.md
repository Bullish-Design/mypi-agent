# MYPI-AGENT Elicitation Log

Status: Draft for closure
Last updated: 2026-05-29
Source: `.scratch/projects/01-mypi-agent-brainstorming/MYPI-AGENT_CONCEPT.md`

This document captures implementation-critical decisions, defaults, and unresolved questions for `MYPI-AGENT`.

How to use:
- Mark each row as `Accepted`, `Changed`, or `Open` in the `Status` column.
- If changed, update `Decision` and `Rationale`.
- Resolve all `Priority: High` items before Phase 2 implementation.

## 1) Scope and Actors

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| SA-1 | High | v1 interaction mode is interactive developer shell via `devenv shell`. | Interactive only | Matches concept goals and phased rollout. | Accepted |
| SA-2 | Medium | CI/headless behavior is out of scope in v1 but command semantics should not preclude it. | Deferred | Prevents over-design while preserving forward path. | Accepted |
| SA-3 | Medium | Primary actors: `Developer`, `DevenvShell`, `SyncCommand`, `DoctorCommand`, `PiCLI`. | Use these actors in specs/docs | Keeps behavior modeling concrete. | Open |
| SA-4 | Low | Multi-user concurrent edits are not explicitly coordinated in v1. | Best-effort file safety only | Local-dev target; avoid lock complexity initially. | Accepted |

## 2) Bootstrap and Sync Semantics

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| SY-1 | High | Auto-bootstrap runs on shell entry only when required files are missing. | Enabled (`autoBootstrap=true`) | Fast first-run UX without mutating existing projects. | Accepted |
| SY-2 | High | Sync mode is missing-only materialization. | `copy-if-missing` | Preserves local edits by construction. | Accepted |
| SY-3 | High | Existing files are never overwritten in default sync path. | Preserve | Core trust and safety principle. | Accepted |
| SY-4 | High | If shim missing and root exists, create shim only. | Partial repair | Minimizes unnecessary writes. | Accepted |
| SY-5 | High | If root exists but subdirs/files missing, backfill missing only. | Partial repair | Keeps repo healthy without destructive changes. | Accepted |
| SY-6 | High | Desired-state hash mismatch should produce advisory output, no auto-upgrade. | Warn only | Explicit upgrades are required by concept. | Accepted |
| SY-7 | High | Define `--repair-shim` as explicit opt-in to rewrite generated shim. | Manual repair command | Separates safe default from corrective action. | Accepted |
| SY-8 | Medium | Manifest missing/corrupt behavior. | Recreate with warning (proposed) | Self-heals common failure while surfacing issue. | Accepted |

## 3) Settings Shim Contract (`.pi/settings.json`)

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| SH-1 | High | Maintain minimal shim that points to configured root resources. | Minimal key set only | Reduces drift and user confusion. | Accepted |
| SH-2 | High | Relative paths resolve from `.pi/settings.json` location. | `../.agents/pi/...` style | Matches concept examples and expected Pi behavior. | Accepted |
| SH-3 | High | Shim rewrite policy when user-edited. | Preserve unless explicit repair | Protect local intent. | Accepted |
| SH-4 | High | Root path change handling. | Update on explicit sync (proposed) | Avoid hidden mutation on shell start. | Accepted |
| SH-5 | High | Validate exact Pi-supported fields for models/packages/path globs. | Verify against upstream docs | Avoid schema mismatch bugs. | Accepted |

## 4) Manifest and Primitive Versioning

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| MV-1 | High | Manifest is required and stored in configured location. | Required | Needed for upgrades and drift reasoning. | Changed |
| MV-2 | High | Manifest tracks per-primitive version + source hash + installed files. | Include all three | Supports safe upgrade classification. | Accepted |
| MV-3 | High | Hash algorithms and timestamp format must be fixed. | `sha256` + RFC3339 UTC (proposed) | Deterministic tooling and tests. | Accepted |
| MV-4 | Medium | Module version source in manifest. | Semver + commit (proposed) | Better traceability during debugging. | Accepted |
| MV-5 | Medium | Schema migration strategy for manifest upgrades. | Versioned schema + upgrader later | Avoid hard lock-in. | Accepted |

## 5) Secrets and Runtime Env Policy

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| SE-1 | High | No secret values written under `.pi/` or agent root. | Strict no-write | Core safety requirement. | Accepted |
| SE-2 | High | Secrets are loaded only at runtime, never at Nix eval. | Runtime only | Prevents Nix store leakage. | Accepted |
| SE-3 | High | Runtime env file loading order and override behavior. | First-to-last, later wins (proposed) | Predictable resolution needed. | Accepted |
| SE-4 | High | Missing env file behavior for wrapper. | Warn, continue (proposed) | Avoid hard break for optional files. | Accepted |
| SE-5 | High | SecretSpec + envFiles precedence rule. | SecretSpec first, env fallback (proposed) | Needed to avoid ambiguity. | Accepted |
| SE-6 | Medium | Doctor secret leak severity. | Error on likely leaks (proposed) | Safer default for committed config. | Accepted |

## 6) Package Source Policy

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| PK-1 | High | Git sources must be pinned. | Require rev/tag/commit | Supply-chain safety and reproducibility. | Accepted |
| PK-2 | High | npm sources must be exact versions. | No ranges | Reproducibility. | Accepted |
| PK-3 | Medium | Local paths allowed and validated for existence. | Allow | Useful for repo-local workflows. | Accepted |
| PK-4 | Medium | Accessibility checks timing. | Doctor check + sync warning (proposed) | Practical for private deps. | Accepted |
| PK-5 | Medium | Installation ownership. | Pi handles install in v1 | Keeps module minimal. | Accepted |

## 7) Doctor Command Contract

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| DR-1 | High | Define required checks and failure conditions. | Minimum checks from concept | Prevents ambiguous health results. | Accepted |
| DR-2 | High | Exit code policy. | `0` healthy, `1` errors, warnings non-zero? (open) | Needed for future CI/headless use. | Accepted |
| DR-3 | Medium | Output modes. | Human-readable only in v1 (proposed) | Faster to ship; JSON later. | Accepted |
| DR-4 | Medium | Validate desired-state vs filesystem drift. | Yes (proposed) | Useful diagnostics with low complexity. | Accepted |

## 8) CLI Surface and UX

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| CL-1 | High | Wrapper command naming. | `mypi` | Matches concept recommendation. | Changed |
| CL-2 | Medium | Keep native `pi` untouched if present. | Yes | Avoid surprising global behavior. | Accepted |
| CL-3 | Medium | `mypi` passthrough behavior and exit code fidelity. | Exact passthrough | Keeps user mental model simple. | Changed |
| CL-4 | Medium | Standard shell entry messages and quiet mode. | Brief status line | Improves discoverability without noise. | Accepted |

## 9) Git and File Lifecycle

| ID | Priority | Decision | Default | Rationale | Status |
|---|---|---|---|---|---|
| GF-1 | High | Commit generated config and primitives by default. | Commit | Reviewability and portability. | Accepted |
| GF-2 | Medium | Ignore runtime state and caches. | Ignore patterns from concept | Keep repo clean. | Accepted |
| GF-3 | Medium | `.gitignore` write strategy. | Missing-only append-safe (proposed) | Avoid clobbering existing ignore policy. | Accepted |

## 10) Test Invariants to Lock Before Build

| ID | Priority | Invariant | Status |
|---|---|---|---|
| TI-1 | High | Local user edits are never overwritten by default sync. | Accepted |
| TI-2 | High | Sync creates missing required files for initialized configuration. | Accepted |
| TI-3 | High | Desired-state hash changes when relevant config/module inputs change. | Accepted |
| TI-4 | High | No secret values are written to generated files. | Accepted |
| TI-5 | High | Shim points to configured root correctly. | Accepted |
| TI-6 | High | Manifest remains valid JSON after sync and upgrade operations. | Accepted |

## 11) Immediate Open Questions (Close First)

| ID | Priority | Question | Proposed Initial Answer | Status |
|---|---|---|---|---|
| OQ-1 | High | Exact Pi CLI executable packaging method for current version? | Use wrapper `mypi`; leave `pi` untouched | Changed |
| OQ-2 | High | Exact accepted Pi settings schema for models and path fields? | Verify against current Pi docs before coding | Accepted |
| OQ-3 | High | Should shim auto-repair when stale and unedited? | No auto-repair; explicit `--repair-shim` | Accepted |
| OQ-4 | High | Should package installation be delegated to Pi or pre-resolved by module? | Delegate to Pi in v1 | Accepted |
| OQ-5 | High | Should doctor warnings cause non-zero exit in v1? | Keep warnings non-fatal (proposed) | Accepted |

## 12) Closure Checklist

Mark complete only when all items are true:

- [ ] All `Priority: High` rows in Sections 1-9 are `Accepted` or `Changed`.
- [ ] All `Open` rows in Section 11 are resolved.
- [ ] Section 10 invariants are accepted and mapped to tests.
- [ ] Any `Changed` defaults are reflected back into implementation docs and option schema.
