from __future__ import annotations

from mypi_agent.doctor import run_doctor
from mypi_agent.models import Paths
from mypi_agent.sync import run_sync


def test_doctor_error_count_matches_exit_code(tmp_path):
    paths = Paths(project_root=tmp_path)
    result = run_doctor(paths)

    assert len(result.errors) > 0
    assert result.exit_code == 1


def test_doctor_zero_errors_maps_to_zero_exit(tmp_path):
    paths = Paths(project_root=tmp_path)
    run_sync(paths, explicit=True, repair_shim=False)

    result = run_doctor(paths)
    assert result.errors == []
    assert result.exit_code == 0
