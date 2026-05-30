from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .base_model import AlliumBase
from .models import Manifest, Paths

RESOURCE_DIRS = ("extensions", "skills", "prompts", "themes")
MANAGED_SETTINGS_KEYS = ["extensions", "skills", "prompts", "themes", "enableSkillCommands"]
SETTINGS_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1


class WriteAction(AlliumBase):
    path: str
    existed_before: bool
    content_changed: bool
    managed: bool


class SyncResult(AlliumBase):
    created: list[Path]
    warnings: list[str]
    explicit: bool
    repair_shim: bool
    completed: bool
    existing_files_overwritten: bool
    advisory_shown: bool
    upgrade_requires_explicit_sync: bool
    bootstrap_performed: bool
    manifest_healed: bool
    shim_updated: bool
    trigger: str
    pi_installed: bool
    hash_inputs_changed: bool
    diff_requested: bool
    upgrade_target: str
    would_create_count: int
    would_upgrade_count: int
    preserved_locally_modified_count: int
    primitive_file_classifications: dict[str, str]
    write_actions: list[WriteAction]


@dataclass
class SyncPlan:
    agent_root_relative: str
    settings_payload: dict[str, object]
    merged_settings_payload: dict[str, object]
    manifest_payload: dict[str, object]
    registry_payload: dict[str, object]
    file_payloads: dict[Path, object]
    primitive_file_classifications: dict[str, str]
    would_create_count: int
    would_upgrade_count: int
    preserved_locally_modified_count: int
    pi_installed: bool
    warnings: list[str]
    manifest_healed: bool
    shim_updated: bool
    bootstrap_performed: bool


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _read_json_or_none(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return _read_json(path)
    except json.JSONDecodeError:
        return None


def _settings_payload(agent_root_relative: str) -> dict[str, object]:
    return {
        "packages": [],
        "extensions": [f"../{agent_root_relative}/extensions"],
        "skills": [f"../{agent_root_relative}/skills"],
        "prompts": [f"../{agent_root_relative}/prompts"],
        "themes": [f"../{agent_root_relative}/themes"],
        "enableSkillCommands": True,
        "x-mypi-agent": {
            "managed": True,
            "schemaVersion": SETTINGS_SCHEMA_VERSION,
            "agentRoot": f"../{agent_root_relative}",
            "managedKeys": MANAGED_SETTINGS_KEYS,
        },
    }


def _utc_now_rfc3339() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_json(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _manifest_payload(pi_package_name: str, pi_version: str | None, node_version: str | None) -> dict[str, object]:
    return Manifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        resources=list(RESOURCE_DIRS),
        pi_package=pi_package_name,
        pi_version=pi_version,
        node_version=node_version,
        generated_by="mypi-agent",
    ).model_dump()


def _load_npm_install_flags() -> list[str]:
    raw = os.environ.get("MYPI_NPM_INSTALL_FLAGS", "")
    if not raw:
        return ["--ignore-scripts", "--no-audit", "--no-fund"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ["--ignore-scripts", "--no-audit", "--no-fund"]
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        return ["--ignore-scripts", "--no-audit", "--no-fund"]
    return parsed


def _load_lockfile_package_metadata(paths: Paths, pi_package_name: str) -> tuple[str | None, str | None]:
    lockfile_path = paths.agent_root / "package-lock.json"
    payload = _read_json_or_none(lockfile_path)
    if not isinstance(payload, dict):
        return (None, None)
    packages = payload.get("packages")
    if not isinstance(packages, dict):
        return (None, None)
    package_entry = packages.get(f"node_modules/{pi_package_name}")
    if not isinstance(package_entry, dict):
        return (None, None)
    resolved = package_entry.get("resolved")
    integrity = package_entry.get("integrity")
    return (
        resolved if isinstance(resolved, str) and resolved else None,
        integrity if isinstance(integrity, str) and integrity else None,
    )


def _classify_file(path: Path, expected_payload: object, managed_keys: list[str] | None = None) -> str:
    if not path.exists():
        return "missing"
    try:
        current = _read_json(path)
    except json.JSONDecodeError:
        return "invalid_json"
    if not isinstance(current, dict):
        return "user_owned"
    marker = current.get("x-mypi-agent")
    has_marker = isinstance(marker, dict) and marker.get("managed") is True
    if not has_marker:
        return "user_owned"
    if managed_keys:
        extra_keys = [k for k in current.keys() if k not in set(managed_keys + ["packages", "x-mypi-agent"])]
        if extra_keys:
            return "user_modified"
    if current == expected_payload:
        return "managed_unchanged"
    return "managed_changed"


def _merge_settings(existing_payload: object | None, generated_payload: dict[str, object]) -> dict[str, object]:
    if not isinstance(existing_payload, dict):
        return generated_payload
    merged = dict(existing_payload)
    for key in MANAGED_SETTINGS_KEYS:
        merged[key] = generated_payload[key]
    merged["x-mypi-agent"] = generated_payload["x-mypi-agent"]
    if "packages" not in merged:
        merged["packages"] = []
    return merged


def build_config_hash_inputs(paths: Paths) -> dict[str, object]:
    return {
        "pi_agent_root": os.environ.get("MYPI_AGENT_ROOT", ".agents/pi"),
        "pi_package_name": os.environ.get("MYPI_PI_PACKAGE_NAME", "@earendil-works/pi-coding-agent"),
        "pi_package_version": os.environ.get("MYPI_PI_PACKAGE_VERSION", "") or None,
        "npm_install_flags": _load_npm_install_flags(),
        "settings_schema_version": SETTINGS_SCHEMA_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "mypi_agent_version": os.environ.get("MYPI_AGENT_VERSION", "0"),
    }


def _config_hash(paths: Paths) -> str:
    return _sha256_json(build_config_hash_inputs(paths))


def needs_sync(paths: Paths) -> bool:
    if not paths.agent_root.exists() or not paths.settings_path.exists() or not paths.manifest_path.exists():
        return True
    bootstrap = _read_json_or_none(paths.bootstrap_state_path)
    if not isinstance(bootstrap, dict):
        return True
    return bootstrap.get("config_hash") != _config_hash(paths)


def _build_sync_plan(paths: Paths, repair_shim: bool, trigger: str, diff_requested: bool) -> SyncPlan:
    warnings: list[str] = []
    bootstrap_performed = not paths.agent_root.exists()
    pi_package_name = os.environ.get("MYPI_PI_PACKAGE_NAME", "@earendil-works/pi-coding-agent")

    node_version: str | None = None
    node_bin = shutil.which("node")
    if node_bin is not None:
        node_version_result = subprocess.run([node_bin, "--version"], text=True, capture_output=True, check=False)
        if node_version_result.returncode == 0:
            node_version = node_version_result.stdout.strip()

    existing_manifest = _read_json_or_none(paths.manifest_path)
    pre_manifest_valid = isinstance(existing_manifest, dict)
    manifest_healed = not pre_manifest_valid

    installed_version: str | None = None
    npm_resolved_url: str | None = None
    npm_integrity_hash: str | None = None
    pi_installed = False

    if not diff_requested:
        npm = shutil.which("npm")
        pi_package_version = os.environ.get("MYPI_PI_PACKAGE_VERSION", "").strip() or None
        npm_install_flags = _load_npm_install_flags()
        if npm is None:
            warnings.append("pi_agent_install_skipped_no_npm")
        else:
            install_target = pi_package_name if pi_package_version is None else f"{pi_package_name}@{pi_package_version}"
            if pi_package_version is None:
                warnings.append("pi_package_version_unset_for_pinned_npm")
            install = subprocess.run(
                [npm, "install", "--prefix", str(paths.agent_root), *npm_install_flags, install_target],
                text=True,
                capture_output=True,
                check=False,
            )
            if install.returncode == 0:
                pi_installed = True
                package_json_path = paths.agent_root / "node_modules" / pi_package_name / "package.json"
                payload = _read_json_or_none(package_json_path)
                if isinstance(payload, dict) and isinstance(payload.get("version"), str):
                    installed_version = payload["version"]
                npm_resolved_url, npm_integrity_hash = _load_lockfile_package_metadata(paths, pi_package_name)
            else:
                warnings.append("pi_agent_install_failed")

    agent_root_relative = paths.agent_root.relative_to(paths.project_root).as_posix()
    settings_payload = _settings_payload(agent_root_relative)
    existing_settings = _read_json_or_none(paths.settings_path)
    merged_settings_payload = _merge_settings(existing_settings, settings_payload)
    shim_updated = repair_shim or not paths.settings_path.exists() or existing_settings != merged_settings_payload

    manifest_payload = _manifest_payload(pi_package_name, installed_version, node_version)
    if not paths.manifest_path.exists() or not pre_manifest_valid:
        warnings.append("manifest_recreated")

    settings_hash = _sha256_json(merged_settings_payload)
    manifest_hash = _sha256_json(manifest_payload)
    source_identity = {
        "package_name": pi_package_name,
        "package_version": installed_version,
        "npm_integrity_hash": npm_integrity_hash,
        "npm_resolved_url": npm_resolved_url,
    }
    registry_payload = {
        "schema_version": 1,
        "groups": {"core": {"resources": list(RESOURCE_DIRS)}},
        "installs": [
            {
                "package_name": pi_package_name,
                "package_version": installed_version or "",
                "npm_resolved_url": npm_resolved_url,
                "npm_integrity_hash": npm_integrity_hash,
                "settings_hash": settings_hash,
                "manifest_hash": manifest_hash,
                "source_hash": _sha256_json(source_identity)[:16],
                "installed_at_rfc3339_utc": _utc_now_rfc3339(),
            }
        ],
    }

    file_payloads: dict[Path, object] = {
        paths.settings_path: merged_settings_payload,
        paths.manifest_path: manifest_payload,
        paths.bootstrap_state_path: {"status": "completed", "trigger": trigger, "config_hash": _config_hash(paths)},
        paths.drift_report_path: {"has_drift": False, "reason": "none"},
        paths.installed_packages_state_path: {"packages": [{"name": pi_package_name, "version": installed_version}]},
        paths.primitive_registry_state_path: registry_payload,
    }

    primitive_file_classifications = {
        "settings_shim": _classify_file(paths.settings_path, merged_settings_payload, MANAGED_SETTINGS_KEYS),
        "manifest": _classify_file(paths.manifest_path, manifest_payload),
    }
    would_create_count = sum(1 for v in primitive_file_classifications.values() if v == "missing")
    preserved_locally_modified_count = sum(1 for v in primitive_file_classifications.values() if v in {"managed_changed", "user_modified"})
    would_upgrade_count = sum(1 for v in primitive_file_classifications.values() if v == "managed_changed")

    return SyncPlan(
        agent_root_relative=agent_root_relative,
        settings_payload=settings_payload,
        merged_settings_payload=merged_settings_payload,
        manifest_payload=manifest_payload,
        registry_payload=registry_payload,
        file_payloads=file_payloads,
        primitive_file_classifications=primitive_file_classifications,
        would_create_count=would_create_count,
        would_upgrade_count=would_upgrade_count,
        preserved_locally_modified_count=preserved_locally_modified_count,
        pi_installed=pi_installed,
        warnings=warnings,
        manifest_healed=manifest_healed,
        shim_updated=shim_updated,
        bootstrap_performed=bootstrap_performed,
    )


def _apply_sync_plan(paths: Paths, plan: SyncPlan) -> tuple[list[Path], list[WriteAction]]:
    created: list[Path] = []
    write_actions: list[WriteAction] = []

    for d in [paths.pi_dir, paths.agent_root, paths.state_dir, *(paths.agent_root / d for d in RESOURCE_DIRS)]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)

    for path, payload in plan.file_payloads.items():
        existed_before = path.exists()
        before = path.read_text(encoding="utf-8") if existed_before else None
        rendered = json.dumps(payload, indent=2) + "\n"
        content_changed = before != rendered
        if not existed_before:
            created.append(path)
        atomic_write_json(path, payload)
        write_actions.append(
            WriteAction(
                path=str(path),
                existed_before=existed_before,
                content_changed=content_changed,
                managed=True,
            )
        )

    if not paths.diagnostics_path.exists():
        paths.diagnostics_path.write_text("", encoding="utf-8")
        created.append(paths.diagnostics_path)
    return created, write_actions


def run_sync(
    paths: Paths,
    explicit: bool,
    repair_shim: bool,
    trigger: str = "manual",
    diff_requested: bool = False,
    upgrade_target: str = "all",
) -> SyncResult:
    plan = _build_sync_plan(paths, repair_shim=repair_shim, trigger=trigger, diff_requested=diff_requested)
    created: list[Path] = []
    write_actions: list[WriteAction] = []
    if not diff_requested:
        created, write_actions = _apply_sync_plan(paths, plan)

    hash_inputs_changed = plan.bootstrap_performed or plan.shim_updated or plan.manifest_healed
    existing_files_overwritten = any(a.existed_before and a.content_changed for a in write_actions)
    return SyncResult(
        created=created,
        warnings=plan.warnings,
        explicit=explicit,
        repair_shim=repair_shim,
        completed=True,
        existing_files_overwritten=existing_files_overwritten,
        advisory_shown=hash_inputs_changed,
        upgrade_requires_explicit_sync=True,
        bootstrap_performed=plan.bootstrap_performed,
        manifest_healed=plan.manifest_healed,
        shim_updated=plan.shim_updated,
        trigger=trigger,
        pi_installed=plan.pi_installed,
        hash_inputs_changed=hash_inputs_changed,
        diff_requested=diff_requested,
        upgrade_target=upgrade_target,
        would_create_count=plan.would_create_count,
        would_upgrade_count=plan.would_upgrade_count,
        preserved_locally_modified_count=plan.preserved_locally_modified_count,
        primitive_file_classifications=plan.primitive_file_classifications,
        write_actions=write_actions,
    )
