from __future__ import annotations

from dataclasses import dataclass

from .models import Paths


@dataclass(frozen=True)
class SettingsShimActor:
    exists: bool
    locally_modified: bool
    points_to_configured_root: bool


@dataclass(frozen=True)
class SurfaceContext:
    surface_name: str
    actor: object


def build_settings_shim_actor(paths: Paths) -> SettingsShimActor:
    points_to_configured_root = False
    if paths.settings_path.exists():
        text = paths.settings_path.read_text(encoding="utf-8")
        points_to_configured_root = "../.agents/pi" in text
    return SettingsShimActor(
        exists=paths.settings_path.exists(),
        locally_modified=False,
        points_to_configured_root=points_to_configured_root,
    )


def require_settings_shim_actor(surface_name: str, actor: object) -> SurfaceContext:
    if not isinstance(actor, SettingsShimActor):
        raise PermissionError(f"{surface_name} requires SettingsShim actor")
    return SurfaceContext(surface_name=surface_name, actor=actor)
