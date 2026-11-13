import os
from pathlib import Path

import pytest


@pytest.fixture
def release_dir() -> Path:
    """The real TCGA-BRCA release folder, from SO_RELEASE_DIR."""
    value = os.environ.get("SO_RELEASE_DIR")
    if not value:
        pytest.skip("SO_RELEASE_DIR is not set (needs the real TCGA-BRCA release folder)")
    path = Path(value)
    if not path.exists():
        pytest.skip(f"SO_RELEASE_DIR does not exist: {path}")
    return path


@pytest.fixture
def mini_release(tmp_path: Path) -> Path:
    """A tiny generated release (see tests/helpers.py)."""
    from tests.helpers import make_mini_release

    return make_mini_release(tmp_path / "mini_release")


@pytest.fixture(autouse=True)
def _ai_off_by_default(monkeypatch):
    """No test reaches a real AI service, even if the developer has a key in the environment or .env.

    Tests that want the layer on pass a ScriptedClient or set the SO_AI_* variables themselves.
    """
    monkeypatch.setenv("SO_AI", "off")
