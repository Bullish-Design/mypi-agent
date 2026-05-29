from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


SCENARIOS = ("basic", "custom-root", "preserve-local-edits", "yaml-import-only")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepare_fixture(tmp_path: Path, scenario: str) -> Path:
    src = _repo_root() / "tests" / "fixtures" / "devenv" / scenario
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
    if shutil.which("devenv") is None:
        pytest.skip("devenv is not installed")

    module_path = _repo_root() / "modules" / "pi-agent.nix"
    if not module_path.exists():
        pytest.skip(f"module not available yet: {module_path}")

    project_dir = _prepare_fixture(tmp_path, scenario)

    result = _run_in_fixture("fixture:verify", cwd=project_dir)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_tmp_repo_fixture_sync_and_doctor(tmp_path: Path) -> None:
    if shutil.which("devenv") is None:
        pytest.skip("devenv is not installed")

    project_dir = tmp_path / "tmp-repo"
    project_dir.mkdir(parents=True)
    (project_dir / "devenv.yaml").write_text(
        "inputs:\n"
        "  mypi-agent:\n"
        f"    url: path:{_repo_root()}\n"
        "    flake: false\n"
        "imports:\n"
        "  - mypi-agent\n",
        encoding="utf-8",
    )
    (project_dir / "devenv.nix").write_text("{ ... }: { }\n", encoding="utf-8")

    sync_result = subprocess.run(
        ["devenv", "shell", "--", "mypi", "sync", "--trigger", "shell"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert sync_result.returncode == 0, sync_result.stdout + "\n" + sync_result.stderr

    for command in ("mypi", "node", "npm"):
        check_result = subprocess.run(
            ["devenv", "shell", "--", "which", command],
            cwd=project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        assert check_result.returncode == 0, check_result.stdout + "\n" + check_result.stderr

    doctor_result = subprocess.run(
        ["devenv", "shell", "--", "mypi", "doctor"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert doctor_result.returncode == 0, doctor_result.stdout + "\n" + doctor_result.stderr
