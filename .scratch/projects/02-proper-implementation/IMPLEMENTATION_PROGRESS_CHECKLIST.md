# Implementation Progress Checklist

Derived from current spec/code drift assessment in `.scratch/specs/allium` and `src/mypi_agent`.

## Priority Work Items

- [x] 1. Implement missing `paths` command end-to-end
  - [x] Add CLI command in `src/mypi_agent/cli.py`
  - [x] Add path resolution/reporting runtime support (models/runtime as needed)
  - [x] Add integration tests for command output contract
  - [x] Verify behavior against `.scratch/specs/allium/paths.allium`

- [x] 2. Implement `upgrade` planning behavior (diff mode + advisory semantics)
  - [x] Add sync planning model/state for `SyncPlan` and `PrimitiveFileState`
  - [x] Implement `--diff`-style reporting of create/upgrade/preserved-modified counts
  - [x] Gate advisory emission on real desired-state/hash-input change signal
  - [x] Ensure local modifications are preserved and classified
  - [x] Add integration tests mapped to `.scratch/specs/allium/upgrade.allium`

- [x] 3. Implement primitive registry persistence and install metadata
  - [x] Add registry state model (`PrimitiveRegistry`) and schema version pinning
  - [x] Persist install metadata records (`source_hash`, `installed_at_rfc3339_utc`)
  - [x] Enforce/validate core group presence in registry
  - [x] Add integration tests mapped to `.scratch/specs/allium/registry.allium`

- [x] 4. Wire topology policy to real checks (or explicitly narrow/de-scope spec)
  - [x] If not implemented, record explicit spec de-scope decision and update specs accordingly
  - [x] De-scoped per-file use-graph and provider/consumer co-evaluation requirements from `.scratch/specs/allium/topology.allium`

- [x] 5. Expand integration tests for new spec modules
  - [x] Add tests for `paths` surface behavior
  - [x] Add tests for `upgrade` planning behavior
  - [x] Add tests for `registry` behavior
  - [x] Add tests for topology policy behavior
  - [x] Extend contract tests if new entity fields are introduced

## Validation / Tooling Status

- [x] Allium spec check passes across all files:
  - Command: `devenv shell -- allium check .scratch/specs/allium/*.allium`
- [x] Python integration test execution verified in devenv
  - Command: `devenv shell -- pytest tests/integration -q`

## Suggested Execution Order

- [x] Phase A: `paths` command + tests
- [x] Phase B: `upgrade` planning core + tests
- [x] Phase C: primitive registry + install metadata + tests
- [x] Phase D: topology enforcement (or spec narrowing) + tests
- [x] Phase E: full regression pass (allium checks + integration tests)
