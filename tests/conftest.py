from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _allow_unmanaged_for_tests(monkeypatch):
    monkeypatch.setenv("MYPI_ALLOW_UNMANAGED", "1")
    monkeypatch.delenv("MYPI_PROJECT_ROOT", raising=False)
