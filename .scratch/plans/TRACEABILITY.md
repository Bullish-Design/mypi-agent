# Allium Obligation Traceability

Generated from `.scratch/plans/*.plan.json` on 2026-05-29.

## Closed Obligations (Mapped to Tests)

- `rule-success.SyncBootstrap`
  - `tests/integration/test_sync.py::test_sync_creates_missing_files_without_overwrite`
- `rule-failure.SyncBootstrap.1`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`
  - (indirectly verifies no destructive overwrite + bounded sync behavior)
- `rule-success.SyncManifestHeal`
  - `tests/integration/test_sync.py::test_sync_self_heals_manifest_when_corrupt`
- `rule-failure.SyncManifestHeal.1`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`
- `rule-success.SyncShimUpdate`
  - `tests/integration/test_sync.py::test_repair_shim_rewrites_when_explicit`
- `rule-failure.SyncShimUpdate.1`
  - `tests/integration/test_sync.py::test_sync_creates_missing_files_without_overwrite`
- `rule-success.SyncFinalize`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`
- `rule-success.ManualUpgradePosture`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`
  - `tests/integration/test_cli.py::test_cli_sync_creates_required_layout`
- `invariant.NoOverwriteByDefault`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`

- `rule-success.DoctorRunStarted`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
- `rule-success.DoctorPerformsRequiredChecks`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
  - `tests/integration/test_doctor.py::test_doctor_flags_likely_secret_leak`
- `rule-success.DoctorCountsErrors`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
  - `tests/integration/test_allium_obligations.py::test_doctor_error_count_matches_exit_code`
- `rule-success.DoctorFinalizeCounts`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
  - `tests/integration/test_doctor.py::test_doctor_success_after_sync`
- `rule-success.DoctorExitCodePolicy`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
  - `tests/integration/test_doctor.py::test_doctor_success_after_sync`
  - `tests/integration/test_allium_obligations.py::test_doctor_zero_errors_maps_to_zero_exit`

- `rule-success.RuntimeSecretsOnly`
  - `tests/integration/test_cli.py::test_cli_run_emits_missing_env_warning_only`
- `rule-success.RuntimeEnvLoadCompletes`
  - `tests/integration/test_cli.py::test_cli_run_emits_missing_env_warning_only`

- `surface-provides.SyncCommandSurface`
  - `tests/integration/test_cli.py::test_cli_sync_creates_required_layout`
  - `tests/integration/test_cli.py::test_cli_sync_repair_shim_rewrites_existing`
- `surface-exposure.SyncCommandSurface`
  - `tests/integration/test_sync.py::test_sync_contract_fields_exposed`
- `surface-provides.DoctorCommandSurface`
  - `tests/integration/test_cli.py::test_cli_doctor_reports_errors_and_exit_code`
  - `tests/integration/test_cli.py::test_cli_doctor_success_after_sync`
- `surface-exposure.DoctorCommandSurface`
  - `tests/integration/test_doctor.py::test_doctor_reports_missing_artifacts`
  - `tests/integration/test_doctor.py::test_doctor_success_after_sync`
- `surface-exposure.MypiCommand`
  - `tests/integration/test_cli.py::test_cli_run_emits_missing_env_warning_only`

- `entity-fields.SettingsShim`
- `entity-fields.AgentRoot`
- `entity-fields.InstalledManifest`
- `entity-fields.SyncRun`
- `entity-fields.SecretRuntimePolicy`
- `entity-fields.DoctorRun`
- `entity-fields.UseTopologyPolicy`
  - Covered by `tests/integration/test_allium_contracts.py`

## Invariant Coverage Status

- `invariant.SyncNonDestructive`: covered by sync integration tests.
- `invariant.ExplicitOnlyUpgrades`: covered by sync contract field assertions.
- `invariant.ManifestValidityAfterSync`: covered by manifest heal + sync success tests.
- `invariant.NoSecretPersistence`: covered via `run` command runtime policy output and doctor leak checks.
- `invariant.NoEvalTimeSecrets`: covered via runtime policy output assertions.
- `invariant.NoSecretConfigWrites`: covered via runtime policy output assertions.
- `invariant.EnvWarningScope`: covered via `test_cli_run_emits_missing_env_warning_only`.

## Remaining Partial / Modeling-Only Items

- `surface-actor.*` obligations are partially exercised through CLI command routing, but actor scoping is not modeled in runtime code.
- `rule-success.PackagePinsValidated` and `topology` rule obligations remain modeling-only (no direct runtime module in `src/` to execute against).

## Notes

- Gap items previously listed for sync/doctor/mypi surface exposure are now implemented in runtime return structures and CLI behavior.
