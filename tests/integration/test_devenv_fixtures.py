from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


FIXTURE_ROOT = Path("tests/fixtures/devenv")
SCENARIOS = ("basic", "custom-root", "preserve-local-edits")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepare_fixture(tmp_path: Path, scenario: str) -> Path:
    src = FIXTURE_ROOT / scenario
    dst = tmp_path / scenario
    shutil.copytree(src, dst)
    devenv_yaml = dst / "devenv.yaml"
    devenv_yaml.write_text(
        devenv_yaml.read_text(encoding="utf-8").replace("__REPO_ROOT__", str(_repo_root())),
        encoding="utf-8",
    )
    return dst


def _run_in_fixture(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["devenv", "tasks", "run", command],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_devenv_fixture_verify_task(tmp_path: Path, scenario: str) -> None:
    module_path = _repo_root() / "modules" / "pi-agent.nix"
    if not module_path.exists():
        pytest.skip(f"module not available yet: {module_path}")

    project_dir = _prepare_fixture(tmp_path, scenario)

    result = _run_in_fixture("fixture:verify", cwd=project_dir)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
