from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _allow_unmanaged_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_UNMANAGED", "1")
    monkeypatch.delenv("MYPI_PROJECT_ROOT", raising=False)


@pytest.fixture(autouse=True)
def _allow_floating_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_FLOATING_PI_VERSION", "true")


@pytest.fixture(autouse=True)
def _block_real_npm(monkeypatch):
    original_which = shutil.which

    def _guarded_which(name: str, *args, **kwargs):
        if name == "npm":
            result = original_which(name, *args, **kwargs)
            if result and "fake-bin" in str(result):
                return result
            return None
        return original_which(name, *args, **kwargs)

    monkeypatch.setattr("shutil.which", _guarded_which)


@pytest.fixture()
def fake_npm(tmp_path, monkeypatch):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    npm_script = fake_bin / "npm"
    npm_script.write_text(
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
        "if [ -z \"$prefix\" ]; then exit 1; fi\n"
        "base_name=$(echo \"$pkg_name\" | sed 's/@[^@/]*$//')\n"
        "if [ -z \"$base_name\" ]; then base_name=\"@earendil-works/pi-coding-agent\"; fi\n"
        "mkdir -p \"$prefix/node_modules/.bin\"\n"
        "mkdir -p \"$prefix/node_modules/$base_name\"\n"
        "cat > \"$prefix/node_modules/.bin/pi\" <<'PIEOF'\n"
        "#!/usr/bin/env sh\n"
        "echo pi 0.0.1-fake\n"
        "PIEOF\n"
        "chmod +x \"$prefix/node_modules/.bin/pi\"\n"
        "cat > \"$prefix/node_modules/$base_name/package.json\" <<'PKGEOF'\n"
        "{\"name\": \"@earendil-works/pi-coding-agent\", \"version\": \"0.0.1-fake\"}\n"
        "PKGEOF\n",
        encoding="utf-8",
    )
    npm_script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ.get('PATH', '')}")
    return fake_bin


@pytest.fixture()
def fake_npm_failing(tmp_path, monkeypatch):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    npm_script = fake_bin / "npm"
    npm_script.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    npm_script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ.get('PATH', '')}")
    return fake_bin
