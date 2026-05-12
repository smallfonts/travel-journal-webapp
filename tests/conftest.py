"""Shared pytest fixtures for all travel-journal-webapp tests."""
import pytest, sys, os
from pathlib import Path

# Add project root to path so `from app.pipeline import ...` works
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def proj_dir():
    return str(Path(__file__).parent.parent)


@pytest.fixture
def client(proj_dir, monkeypatch):
    """HTTP client for the FastAPI app (TestClient)."""
    # Patch cache dirs to use temp directories so tests don't pollute real cache
    import sys, tempfile
    img_cache = tempfile.mkdtemp(prefix="img_cache_")
    vid_cache = tempfile.mkdtemp(prefix="vid_cache_")
    os.environ["TRAVEL_JOURNAL_IMAGE_CACHE"] = img_cache
    os.environ["TRAVEL_JOURNAL_VIDEO_CACHE"] = vid_cache
    os.environ["TRAVEL_JOURNAL_VAULT_PATH"] = tempfile.mkdtemp(prefix="vault_")
    os.environ["TRAVEL_JOURNAL_TRAVEL_FOLDER"] = "Travel"

    # Reset module imports to pick up patched env vars
    for mod in list(sys.modules.keys()):
        if mod.startswith("app.") or mod == "main":
            sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)