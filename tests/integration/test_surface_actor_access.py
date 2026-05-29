from __future__ import annotations

import pytest

from mypi_agent.models import Paths
from mypi_agent.surfaces_runtime import (
    SettingsShimActor,
    build_settings_shim_actor,
    require_settings_shim_actor,
)


def test_surface_actor_allows_settings_shim_actor(tmp_path):
    paths = Paths(project_root=tmp_path)
    actor = build_settings_shim_actor(paths)
    ctx = require_settings_shim_actor("SyncCommandSurface", actor)
    assert ctx.surface_name == "SyncCommandSurface"
    assert isinstance(ctx.actor, SettingsShimActor)


def test_surface_actor_rejects_non_settings_shim_actor():
    with pytest.raises(PermissionError):
        require_settings_shim_actor("DoctorCommandSurface", actor=object())
