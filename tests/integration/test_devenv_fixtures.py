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

    fake_npm_setup = (
        "mkdir -p .fake-bin && "
        "cat > .fake-bin/npm <<'SH'\n"
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "prefix=\n"
        "pkg_name=\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --prefix) shift; prefix=\"$1\" ;;\n"
        "    @*) pkg_name=\"$1\" ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "[ -n \"$prefix\" ] || exit 1\n"
        "base_name=$(echo \"$pkg_name\" | sed 's/@[^@/]*$//')\n"
        "[ -n \"$base_name\" ] || base_name='@earendil-works/pi-coding-agent'\n"
        "mkdir -p \"$prefix/node_modules/.bin\" \"$prefix/node_modules/$base_name\"\n"
        "cat > \"$prefix/node_modules/.bin/pi\" <<'PI'\n"
        "#!/usr/bin/env sh\n"
        "echo pi 0.0.1-fixture\n"
        "PI\n"
        "chmod +x \"$prefix/node_modules/.bin/pi\"\n"
        "cat > \"$prefix/node_modules/$base_name/package.json\" <<'PKG'\n"
        "{\"name\":\"@earendil-works/pi-coding-agent\",\"version\":\"0.0.1-fixture\"}\n"
        "PKG\n"
        "SH\n"
        "chmod +x .fake-bin/npm"
    )

    setup_result = subprocess.run(
        ["devenv", "shell", "--", "sh", "-lc", fake_npm_setup],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert setup_result.returncode == 0, setup_result.stdout + "\n" + setup_result.stderr

    sync_result = subprocess.run(
        ["devenv", "shell", "--", "sh", "-lc", "export PATH=\"$PWD/.fake-bin:$PATH\" && mypi sync --trigger shell"],
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
        ["devenv", "shell", "--", "sh", "-lc", "export PATH=\"$PWD/.fake-bin:$PATH\" && mypi doctor"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert doctor_result.returncode == 0, doctor_result.stdout + "\n" + doctor_result.stderr
