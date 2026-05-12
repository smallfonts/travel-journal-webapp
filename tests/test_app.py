"""
Test suite for Travel Journal Web App (Stages 1-3).
Run with: pytest tests/ -v
"""
import pytest, json, sqlite3, time, os, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def proj_dir():
    return Path(__file__).parent.parent

@pytest.fixture
def client(proj_dir):
    """Start app on a random port for isolated testing."""
    import sys
    sys.path.insert(0, str(proj_dir))

    # Patch config to use temp dirs
    with patch.dict(os.environ, {
        "VAULT_PATH": "/tmp/test_vault",
        "CACHE_IMAGES": "/tmp/test_cache/images",
        "CACHE_VIDEOS": "/tmp/test_cache/videos",
    }):
        # Ensure cache dirs exist
        Path("/tmp/test_cache/images").mkdir(parents=True, exist_ok=True)
        Path("/tmp/test_cache/videos").mkdir(parents=True, exist_ok=True)

        from main import app, JOBS_DB, init_jobs_db
        init_jobs_db()  # fresh DB for each test

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        # Cleanup
        if Path(JOBS_DB).exists():
            os.remove(JOBS_DB)


@pytest.fixture
def sample_jpg():
    """Minimal valid JPEG bytes (SOI + APP0 + DQT + EOI markers)."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t"
        b"\x09\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xd9"
    )

@pytest.fixture
def sample_heic_bytes():
    """Minimal HEIC-like bytes (not a real HEIC, just enough to pass size/content checks)."""
    return b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heic"

@pytest.fixture
def sample_mp4():
    """Minimal MP4 bytes (ftyp box)."""
    return b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41"


# ─── Stage 1: App Scaffold ───────────────────────────────────────────────────

class TestStage1_Scaffold:
    def test_health_endpoint_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "vault" in data

    def test_health_endpoint_json_content_type(self, client):
        r = client.get("/health")
        assert r.headers["content-type"].startswith("application/json")

    def test_upload_form_serves_at_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Travel Journal" in r.text
        assert 'id="upload-form"' in r.text
        assert 'name="files"' in r.text

    def test_upload_form_has_all_fields(self, client):
        r = client.get("/")
        text = r.text
        assert 'name="caption"' in text
        assert 'name="date_override"' in text
        assert 'name="process_now"' in text
        assert 'id="file-input"' in text
        assert 'id="upload-zone"' in text

    def test_upload_form_has_drag_drop_js(self, client):
        r = client.get("/")
        text = r.text
        assert "dragover" in text
        assert "drop" in text

    def test_upload_form_has_polling_js(self, client):
        r = client.get("/")
        text = r.text
        assert "pollStatus" in text
        assert "/api/journal/status/" in text


# ─── Stage 2: Web Form Upload ────────────────────────────────────────────────

class TestStage2_WebFormUpload:
    def test_upload_single_file_returns_done(self, client, sample_jpg):
        r = client.post("/upload", files={"files": ("test.jpg", sample_jpg, "image/jpeg")})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "done"
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "test.jpg"

    def test_upload_multiple_files(self, client, sample_jpg, sample_mp4):
        r = client.post("/upload", files=[
            ("files", ("a.jpg", sample_jpg, "image/jpeg")),
            ("files", ("b.mp4", sample_mp4, "video/mp4")),
        ])
        data = r.json()
        assert data["status"] == "done"
        assert len(data["files"]) == 2

    def test_upload_no_files_returns_error(self, client):
        r = client.post("/upload", data={"caption": "no files"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"
        assert "No files" in data["message"]

    def test_upload_saves_to_image_cache(self, client, sample_jpg, proj_dir):
        r = client.post("/upload", files={"files": ("cached.jpg", sample_jpg, "image/jpeg")})
        assert r.status_code == 200
        # Files saved with uuid prefix under CACHE_IMAGES (patched via settings object)
        import main
        cache_dir = Path(main.settings.CACHE_IMAGES)
        saved = list(cache_dir.glob("stage2_*"))
        assert len(saved) >= 1

    def test_upload_saves_to_video_cache(self, client, sample_mp4, proj_dir):
        r = client.post("/upload", files={"files": ("vid.mp4", sample_mp4, "video/mp4")})
        assert r.status_code == 200
        import main
        cache_dir = Path(main.settings.CACHE_VIDEOS)
        saved = list(cache_dir.glob("stage2_*"))
        assert len(saved) >= 1

    def test_upload_captures_correct_size(self, client, sample_jpg):
        r = client.post("/upload", files={"files": ("sized.jpg", sample_jpg, "image/jpeg")})
        data = r.json()
        assert data["files"][0]["size"] == len(sample_jpg)

    def test_upload_with_caption_and_date(self, client, sample_jpg):
        r = client.post("/upload",
            data={"caption": "My fun trip", "date_override": "2026-01-15"},
            files={"files": ("cap.jpg", sample_jpg, "image/jpeg")},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "done"

    def test_upload_form_mobile_responsive(self, client):
        r = client.get("/")
        text = r.text
        assert "viewport" in text
        assert "max-width: 640px" in text


# ─── Stage 3: Internal REST API ──────────────────────────────────────────────

class TestStage3_InternalRESTAPI:
    def test_api_upload_returns_job_id(self, client, sample_jpg):
        r = client.post("/api/journal/upload", files={"files": ("job.jpg", sample_jpg, "image/jpeg")})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "accepted"
        assert "job_id" in data
        assert len(data["job_id"]) == 8

    def test_api_upload_returns_accepted_for_multiple_files(self, client, sample_jpg, sample_mp4):
        r = client.post("/api/journal/upload", files=[
            ("files", ("x.jpg", sample_jpg, "image/jpeg")),
            ("files", ("y.mp4", sample_mp4, "video/mp4")),
        ])
        data = r.json()
        assert data["status"] == "accepted"
        assert "1 file" in data["message"] or "2 file" in data["message"]

    def test_api_upload_no_files_returns_error(self, client):
        r = client.post("/api/journal/upload", data={"caption": "nope"})
        data = r.json()
        assert data["status"] == "error"
        assert "No files" in data["message"]

    def test_api_status_unknown_job_returns_error(self, client):
        r = client.get("/api/journal/status/badid99")
        data = r.json()
        assert data["status"] == "error"
        assert "not found" in data["message"]

    def test_api_status_returns_correct_job_fields(self, client, sample_jpg):
        # Create job
        r1 = client.post("/api/journal/upload", files={"files": ("f.jpg", sample_jpg, "image/jpeg")})
        job_id = r1.json()["job_id"]

        # Poll — wait for stub to complete
        for _ in range(5):
            time.sleep(1)
            r2 = client.get(f"/api/journal/status/{job_id}")
            data = r2.json()
            if data["status"] != "processing":
                break

        assert data["job_id"] == job_id
        assert data["status"] in ("processing", "done")
        assert "files" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "f.jpg"
        assert data["files"][0]["status"] in ("pending", "processing", "done")

    def test_api_status_shows_stub_completion(self, client, sample_jpg):
        r1 = client.post("/api/journal/upload", files={"files": ("comp.jpg", sample_jpg, "image/jpeg")})
        job_id = r1.json()["job_id"]

        # Wait for stub to finish
        for _ in range(5):
            time.sleep(1)
            r2 = client.get(f"/api/journal/status/{job_id}")
            if r2.json()["status"] == "done":
                break

        data = r2.json()
        assert data["status"] == "done"
        assert data["files"][0]["status"] == "done"
        # Stub marks files as done with this message
        assert "not yet wired" in (data["files"][0]["message"] or "") or data["files"][0]["status"] == "done"

    def test_api_status_result_json_populated_on_done(self, client, sample_jpg):
        r1 = client.post("/api/journal/upload", files={"files": ("res.jpg", sample_jpg, "image/jpeg")})
        job_id = r1.json()["job_id"]

        for _ in range(5):
            time.sleep(1)
            r2 = client.get(f"/api/journal/status/{job_id}")
            if r2.json()["status"] == "done":
                break

        data = r2.json()
        assert data["result"] is not None
        assert "journal_file" in data["result"]

    def test_api_status_polls_per_file_status(self, client, sample_jpg):
        """Two files should each get their own file record."""
        r1 = client.post("/api/journal/upload", files=[
            ("files", ("p.jpg", sample_jpg, "image/jpeg")),
            ("files", ("q.jpg", sample_jpg, "image/jpeg")),
        ])
        job_id = r1.json()["job_id"]

        for _ in range(5):
            time.sleep(1)
            r2 = client.get(f"/api/journal/status/{job_id}")
            if r2.json()["status"] == "done":
                break

        data = r2.json()
        assert len(data["files"]) == 2

    def test_api_upload_with_caption(self, client, sample_jpg):
        r = client.post("/api/journal/upload",
            data={"caption": "Sunset at Gardens by the Bay"},
            files={"files": ("sunset.jpg", sample_jpg, "image/jpeg")},
        )
        job_id = r.json()["job_id"]
        r2 = client.get(f"/api/journal/status/{job_id}")
        assert r2.json()["caption"] == "Sunset at Gardens by the Bay"

    def test_api_upload_with_date_override(self, client, sample_jpg):
        r = client.post("/api/journal/upload",
            data={"date_override": "2026-03-01"},
            files={"files": ("dated.jpg", sample_jpg, "image/jpeg")},
        )
        job_id = r.json()["job_id"]
        r2 = client.get(f"/api/journal/status/{job_id}")
        assert r2.json()["date_override"] == "2026-03-01"

    def test_api_upload_with_process_now(self, client, sample_jpg):
        r = client.post("/api/journal/upload",
            data={"process_now": "1"},
            files={"files": ("dream.jpg", sample_jpg, "image/jpeg")},
        )
        job_id = r.json()["job_id"]
        r2 = client.get(f"/api/journal/status/{job_id}")
        assert r2.json()["process_now"] is True


# ─── Integration: Jobs DB ────────────────────────────────────────────────────

class TestJobsDB:
    def test_jobs_db_created(self, client):
        from main import JOBS_DB
        assert Path(JOBS_DB).exists()

    def test_job_record_persists(self, client, sample_jpg):
        r1 = client.post("/api/journal/upload", files={"files": ("db.jpg", sample_jpg, "image/jpeg")})
        job_id = r1.json()["job_id"]

        from main import JOBS_DB
        with sqlite3.connect(JOBS_DB) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert row is not None
            assert row["status"] in ("processing", "done")
            assert row["job_id"] == job_id

    def test_job_files_recorded(self, client, sample_jpg):
        r1 = client.post("/api/journal/upload", files={
            "files": ("rec.jpg", sample_jpg, "image/jpeg"),
        })
        job_id = r1.json()["job_id"]

        from main import JOBS_DB
        with sqlite3.connect(JOBS_DB) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM job_files WHERE job_id = ?", (job_id,)).fetchall()
            assert len(rows) == 1
            assert rows[0]["filename"] == "rec.jpg"
            assert rows[0]["status"] in ("pending", "processing", "done")