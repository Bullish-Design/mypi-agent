from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .base_model import AlliumBase
from .models import Paths


RESOURCE_DIRS = ("extensions", "skills", "prompts", "themes")


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
    pi_agent_installed: bool
    hash_inputs_changed: bool
    diff_requested: bool
    upgrade_target: str
    would_create_count: int
    would_upgrade_count: int
    preserved_locally_modified_count: int
    primitive_file_classifications: dict[str, str]


def _ensure_dir(path: Path, created: list[Path]) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object, created: list[Path]) -> None:
    if not path.exists():
        created.append(path)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _settings_payload(agent_root_relative: str) -> dict[str, object]:
    return {
        "packages": [],
        "extensions": [f"../{agent_root_relative}/extensions"],
        "skills": [f"../{agent_root_relative}/skills"],
        "prompts": [f"../{agent_root_relative}/prompts"],
        "themes": [f"../{agent_root_relative}/themes"],
        "enableSkillCommands": True,
        "x-mypi-agent": {
            "agentRoot": f"../{agent_root_relative}",
        },
    }


def _utc_now_rfc3339() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _sha256_json(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _manifest_payload(pi_package_name: str, pi_version: str | None, node_version: str | None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "resources": list(RESOURCE_DIRS),
        "pi_package": pi_package_name,
        "pi_version": pi_version,
        "node_version": node_version,
        "generated_by": "mypi-agent",
    }


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
    if not lockfile_path.exists():
        return (None, None)
    payload = _read_json(lockfile_path)
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


def run_sync(
    paths: Paths,
    explicit: bool,
    repair_shim: bool,
    trigger: str = "manual",
    diff_requested: bool = False,
    upgrade_target: str = "all",
) -> SyncResult:
    created: list[Path] = []
    warnings: list[str] = []

    bootstrap_performed = False
    manifest_healed = False
    shim_updated = False
    pi_agent_installed = False

    if not paths.agent_root.exists():
        bootstrap_performed = True
    pre_settings_exists = paths.settings_path.exists()
    pre_manifest_exists = paths.manifest_path.exists()
    pre_manifest_valid = False
    if pre_manifest_exists:
        try:
            pre_manifest_valid = isinstance(_read_json(paths.manifest_path), dict)
        except json.JSONDecodeError:
            pre_manifest_valid = False

    _ensure_dir(paths.pi_dir, created)
    _ensure_dir(paths.agent_root, created)
    for dirname in RESOURCE_DIRS:
        _ensure_dir(paths.agent_root / dirname, created)
    _ensure_dir(paths.state_dir, created)

    agent_root_relative = paths.agent_root.relative_to(paths.project_root).as_posix()
    settings_payload = _settings_payload(agent_root_relative)

    if repair_shim:
        _write_json(paths.settings_path, settings_payload, created)
        shim_updated = True
    elif not paths.settings_path.exists():
        _write_json(paths.settings_path, settings_payload, created)
        bootstrap_performed = True

    _write_json(paths.bootstrap_state_path, {"status": "completed", "trigger": trigger}, created)
    if not paths.diagnostics_path.exists():
        paths.diagnostics_path.write_text("", encoding="utf-8")
        created.append(paths.diagnostics_path)
    _write_json(paths.drift_report_path, {"has_drift": False, "reason": "none"}, created)
    _write_json(paths.installed_packages_state_path, {"packages": []}, created)
    registry_payload: dict[str, object] = {
        "schema_version": 1,
        "groups": {"core": {"resources": list(RESOURCE_DIRS)}},
        "installs": [],
    }

    npm = shutil.which("npm")
    pi_package_name = os.environ.get("MYPI_PI_PACKAGE_NAME", "@earendil-works/pi-coding-agent")
    pi_package_version = os.environ.get("MYPI_PI_PACKAGE_VERSION", "").strip() or None
    npm_install_flags = _load_npm_install_flags()
    node_version: str | None = None
    node_bin = shutil.which("node")
    if node_bin is not None:
        node_version_result = subprocess.run([node_bin, "--version"], text=True, capture_output=True, check=False)
        if node_version_result.returncode == 0:
            node_version = node_version_result.stdout.strip()

    installed_version: str | None = None
    npm_resolved_url: str | None = None
    npm_integrity_hash: str | None = None
    if npm is None:
        warnings.append("pi_agent_install_skipped_no_npm")
    else:
        install_target = pi_package_name if pi_package_version is None else f"{pi_package_name}@{pi_package_version}"
        if pi_package_version is None:
            warnings.append("pi_package_version_unset_for_pinned_npm")
        install = subprocess.run(
            [
                npm,
                "install",
                "--prefix",
                str(paths.agent_root),
                *npm_install_flags,
                install_target,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if install.returncode == 0:
            pi_agent_installed = True
            package_json_path = paths.agent_root / "node_modules" / pi_package_name / "package.json"
            if package_json_path.exists():
                payload = _read_json(package_json_path)
                if isinstance(payload, dict):
                    version_value = payload.get("version")
                    if isinstance(version_value, str) and version_value:
                        installed_version = version_value
            npm_resolved_url, npm_integrity_hash = _load_lockfile_package_metadata(paths, pi_package_name)
            launcher = paths.agent_root / "bin" / "pi-agent"
            _ensure_dir(launcher.parent, created)
            launcher.write_text(
                "#!/usr/bin/env sh\n"
                "set -eu\n"
                "exec \"$(dirname \"$0\")/../node_modules/.bin/pi\" \"$@\"\n",
                encoding="utf-8",
            )
            launcher.chmod(0o755)
            if launcher not in created:
                created.append(launcher)
            _write_json(
                paths.installed_packages_state_path,
                {
                    "packages": [
                        {"name": pi_package_name, "version": installed_version},
                    ]
                },
                created,
            )
        else:
            warnings.append("pi_agent_install_failed")

    manifest_payload = _manifest_payload(pi_package_name, installed_version, node_version)
    _write_json(paths.manifest_path, manifest_payload, created)
    if not pre_manifest_exists or not pre_manifest_valid:
        warnings.append("manifest_recreated")
        manifest_healed = True

    settings_hash = _sha256_json(settings_payload)
    manifest_hash = _sha256_json(manifest_payload)
    source_identity = {
        "package_name": pi_package_name,
        "package_version": installed_version,
        "npm_integrity_hash": npm_integrity_hash,
        "npm_resolved_url": npm_resolved_url,
    }
    registry_payload["installs"] = [
        {
            "package_name": pi_package_name,
            "package_version": installed_version or "",
            "npm_resolved_url": npm_resolved_url,
            "npm_integrity_hash": npm_integrity_hash,
            "settings_hash": settings_hash,
            "manifest_hash": manifest_hash,
            "source_hash": _source_hash(json.dumps(source_identity, sort_keys=True)),
            "installed_at_rfc3339_utc": _utc_now_rfc3339(),
        }
    ]

    if "core" not in (registry_payload.get("groups") or {}):
        raise RuntimeError("primitive registry missing required core group")
    _write_json(paths.primitive_registry_state_path, registry_payload, created)

    primitive_file_classifications: dict[str, str] = {
        "settings_shim": "unchanged" if pre_settings_exists and not shim_updated else "missing",
        "manifest": "unchanged" if pre_manifest_exists and pre_manifest_valid and not manifest_healed else "missing",
    }
    if pre_settings_exists and not shim_updated:
        primitive_file_classifications["settings_shim"] = "locally_modified"

    would_create_count = sum(1 for p in primitive_file_classifications.values() if p == "missing")
    preserved_locally_modified_count = sum(
        1 for p in primitive_file_classifications.values() if p == "locally_modified"
    )
    would_upgrade_count = 1 if manifest_healed or shim_updated else 0
    hash_inputs_changed = shim_updated or manifest_healed or bootstrap_performed
    advisory_shown = hash_inputs_changed

    return SyncResult(
        created=created,
        warnings=warnings,
        explicit=explicit,
        repair_shim=repair_shim,
        completed=True,
        existing_files_overwritten=False,
        advisory_shown=advisory_shown,
        upgrade_requires_explicit_sync=True,
        bootstrap_performed=bootstrap_performed,
        manifest_healed=manifest_healed,
        shim_updated=shim_updated,
        trigger=trigger,
        pi_agent_installed=pi_agent_installed,
        hash_inputs_changed=hash_inputs_changed,
        diff_requested=diff_requested,
        upgrade_target=upgrade_target,
        would_create_count=would_create_count,
        would_upgrade_count=would_upgrade_count,
        preserved_locally_modified_count=preserved_locally_modified_count,
        primitive_file_classifications=primitive_file_classifications,
    )
    settings_hash = _sha256_json(settings_payload)
    manifest_hash = _sha256_json(manifest_payload)
    source_identity = {
        "package_name": pi_package_name,
        "package_version": installed_version,
        "npm_integrity_hash": npm_integrity_hash,
        "npm_resolved_url": npm_resolved_url,
    }
    registry_payload["installs"] = [
        {
            "package_name": pi_package_name,
            "package_version": installed_version or "",
            "npm_resolved_url": npm_resolved_url,
            "npm_integrity_hash": npm_integrity_hash,
            "settings_hash": settings_hash,
            "manifest_hash": manifest_hash,
            "source_hash": _source_hash(json.dumps(source_identity, sort_keys=True)),
            "installed_at_rfc3339_utc": _utc_now_rfc3339(),
        }
    ]
