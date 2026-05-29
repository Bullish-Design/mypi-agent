from __future__ import annotations

import json
import os

from .base_model import AlliumBase
from .models import Paths

MANAGED_SETTINGS_KEYS = ["extensions", "skills", "prompts", "themes", "enableSkillCommands"]


class SettingsShimActor(AlliumBase):
    exists: bool
    classification: str
    marker_present: bool
    managed_keys: list[str]
    locally_modified: bool
    points_to_configured_root: bool


class SurfaceContext(AlliumBase):
    surface_name: str
    actor: object


def build_settings_shim_actor(paths: Paths) -> SettingsShimActor:
    managed_keys: list[str] = []
    marker_present = False
    points_to_configured_root = False
    classification = "missing"
    expected_root = f"../{paths.agent_root.relative_to(paths.project_root).as_posix()}"

    if paths.settings_path.exists():
        try:
            payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            classification = "invalid_json"
        else:
            if not isinstance(payload, dict):
                classification = "user_owned"
            else:
                marker = payload.get("x-mypi-agent")
                marker_present = isinstance(marker, dict) and marker.get("managed") is True
                if marker_present:
                    marker_agent_root = marker.get("agentRoot")
                    points_to_configured_root = marker_agent_root == expected_root
                    marker_managed_keys = marker.get("managedKeys")
                    if isinstance(marker_managed_keys, list):
                        managed_keys = [item for item in marker_managed_keys if isinstance(item, str)]

                    user_added_keys = [
                        key
                        for key in payload
                        if key not in {"packages", "x-mypi-agent", *MANAGED_SETTINGS_KEYS}
                    ]
                    if user_added_keys:
                        classification = "user_modified"
                    elif points_to_configured_root and set(managed_keys) == set(MANAGED_SETTINGS_KEYS):
                        classification = "managed_unchanged"
                    else:
                        classification = "managed_changed"
                else:
                    classification = "user_owned"
    else:
        configured = os.environ.get("MYPI_AGENT_ROOT")
        points_to_configured_root = configured in (None, "", ".agents/pi")

    locally_modified = classification in {"managed_changed", "user_modified"}
    return SettingsShimActor(
        exists=paths.settings_path.exists(),
        classification=classification,
        marker_present=marker_present,
        managed_keys=managed_keys,
        locally_modified=locally_modified,
        points_to_configured_root=points_to_configured_root,
    )


def require_settings_shim_actor(surface_name: str, actor: object) -> SurfaceContext:
    if not isinstance(actor, SettingsShimActor):
        raise PermissionError(f"{surface_name} requires SettingsShim actor")
    return SurfaceContext(surface_name=surface_name, actor=actor)
