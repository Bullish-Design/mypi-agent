from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / ".scratch" / "models"


def _load_entity(name: str) -> dict:
    return json.loads((MODELS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _field_names(entity_doc: dict) -> set[str]:
    return {field["name"] for field in entity_doc.get("fields", [])}


def test_allium_entity_models_exist():
    expected = {
        "AgentRoot",
        "DoctorRun",
        "InstalledManifest",
        "SecretRuntimePolicy",
        "SettingsShim",
        "SyncRun",
        "UseTopologyPolicy",
    }
    found = {p.stem for p in MODELS_DIR.glob("*.json")}
    assert expected <= found


def test_syncrun_contract_fields_present():
    fields = _field_names(_load_entity("SyncRun"))
    assert {
        "explicit",
        "repair_shim",
        "completed",
        "existing_files_overwritten",
        "advisory_shown",
        "upgrade_requires_explicit_sync",
        "bootstrap_performed",
        "manifest_healed",
        "shim_updated",
    } <= fields


def test_doctorrun_contract_fields_present():
    fields = _field_names(_load_entity("DoctorRun"))
    assert {"requested", "checks_completed", "error_count", "computed_error_count", "exit_code"} <= fields


def test_secretruntimepolicy_contract_fields_present():
    fields = _field_names(_load_entity("SecretRuntimePolicy"))
    assert {
        "runtime_env_load_attempted",
        "runtime_env_load_completed",
        "missing_env_files_warning",
        "secrets_written_to_generated_config",
        "secrets_available_at_evaluation_time",
        "config_write_attempted",
        "config_write_blocked",
        "warning_reason_missing_env_files_only",
    } <= fields
