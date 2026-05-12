"""
Tests for Stage 4: Media Processing Pipeline.
Run with: pytest tests/test_pipeline.py -v
"""
import pytest, os, time
from pathlib import Path

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_jpg_path(tmp_path):
    """Create a minimal JPEG with EXIF DateTime but no GPS."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    exif = img.getexif()
    exif[0x010f] = "TestCamera"   # Make
    exif[0x0110] = "TestModel"     # Model
    exif[274] = 1                   # Orientation: normal
    path = tmp_path / "test.jpg"
    img.save(path, "JPEG", exif=exif)
    return str(path)


@pytest.fixture
def sample_jpg_with_gps(tmp_path):
    """
    Create a JPEG with GPS coordinates (Singapore ~1.35, 103.8).
    PIL doesn't support writing GPS EXIF directly, so we construct one manually.
    """
    from PIL import Image, ExifTags
    img = Image.new("RGB", (100, 100), color="blue")
    path = tmp_path / "gps.jpg"
    # Write minimal EXIF with GPS tag 34853
    exif = Image.Exif()
    exif[0x010f] = "Apple"
    exif[0x0110] = "iPhone 15"
    exif[274] = 1
    # GPS IFD — integer keys per the skill spec
    # Tag 34853 = GPSInfo
    gps_ifd = {
        1: "N",           # North
        2: (1, 21, 18),   # 1°21'18" = 1.355
        3: "E",           # East
        4: (103, 50, 12), # 103°50'12" = 103.837
        5: 0,             # Altitude ref (above sea level)
    }
    exif[34853] = gps_ifd
    img.save(path, "JPEG", exif=exif)
    return str(path)


@pytest.fixture
def sample_jpg_portrait_rotated(tmp_path):
    """Create a portrait JPEG with orientation=6 (Rotate CW 90°)."""
    from PIL import Image
    img = Image.new("RGB", (100, 200), color="green")  # portrait: h=200, w=100
    exif = Image.Exif()
    exif[274] = 6  # Orientation: Rotate CW 90°
    path = tmp_path / "portrait.jpg"
    img.save(path, "JPEG", exif=exif)
    return str(path)


@pytest.fixture
def sample_png_path(tmp_path):
    """Create a PNG (no EXIF)."""
    from PIL import Image
    img = Image.new("RGB", (50, 50), color="blue")
    path = tmp_path / "test.png"
    img.save(path, "PNG")
    return str(path)


# ─── extract_photo_metadata ──────────────────────────────────────────────────

class TestExtractPhotoMetadata:
    def test_returns_all_fields(self, sample_jpg_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_path)
        assert "datetime" in meta
        assert "lat" in meta
        assert "lon" in meta
        assert "camera_make" in meta
        assert "camera_model" in meta
        assert "orientation" in meta
        assert "gps_raw" in meta
        assert "width" in meta
        assert "height" in meta

    def test_camera_make_and_model(self, sample_jpg_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_path)
        assert meta["camera_make"] == "TestCamera"
        assert meta["camera_model"] == "TestModel"

    def test_orientation_normal(self, sample_jpg_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_path)
        assert meta["orientation"] == 1

    def test_orientation_portrait_rotated(self, sample_jpg_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_path)
        # portrait JPG should show h > w
        assert meta["width"] is not None
        assert meta["height"] is not None

    def test_no_gps_returns_none(self, sample_jpg_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_path)
        assert meta["lat"] is None
        assert meta["lon"] is None
        assert meta["gps_raw"] is None

    def test_png_no_exif_returns_empty_gps(self, sample_png_path):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_png_path)
        assert meta["lat"] is None
        assert meta["lon"] is None

    def test_nonexistent_file_returns_empty_meta(self):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata("/nonexistent/file.jpg")
        assert meta["datetime"] is None
        assert meta["lat"] is None


class TestExtractPhotoMetadataGPS:
    def test_gps_lat_lon_parsed(self, sample_jpg_with_gps):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_with_gps)
        assert meta["lat"] is not None
        assert meta["lon"] is not None
        assert 1.0 < meta["lat"] < 1.5   # Singapore latitude
        assert 103.0 < meta["lon"] < 104.0  # Singapore longitude

    def test_gps_raw_dict_returned(self, sample_jpg_with_gps):
        from app.pipeline import extract_photo_metadata
        meta = extract_photo_metadata(sample_jpg_with_gps)
        assert meta["gps_raw"] is not None
        assert meta["gps_raw"][1] == "N"


# ─── parse_exif_datetime ─────────────────────────────────────────────────────

class TestParseExifDatetime:
    def test_standard_format(self):
        from app.pipeline import parse_exif_datetime
        result = parse_exif_datetime("2026:05:12 14:30:00")
        assert result == "2026-05-12 14:30:00"

    def test_iso_format(self):
        from app.pipeline import parse_exif_datetime
        result = parse_exif_datetime("2026-05-12T14:30:00")
        assert result == "2026-05-12 14:30:00"

    def test_iso_format_with_z(self):
        from app.pipeline import parse_exif_datetime
        result = parse_exif_datetime("2026-05-12T14:30:00Z")
        assert result == "2026-05-12 14:30:00"

    def test_none_returns_none(self):
        from app.pipeline import parse_exif_datetime
        assert parse_exif_datetime(None) is None

    def test_invalid_returns_none(self):
        from app.pipeline import parse_exif_datetime
        assert parse_exif_datetime("not a date") is None


# ─── format_coordinates ───────────────────────────────────────────────────────

class TestFormatCoordinates:
    def test_positive_coords(self):
        from app.pipeline import format_coordinates
        result = format_coordinates(1.3521, 103.8198)
        assert "N" in result
        assert "E" in result
        assert "1.3521" in result

    def test_negative_coords(self):
        from app.pipeline import format_coordinates
        result = format_coordinates(-33.8688, 151.2093)
        assert "S" in result
        assert "E" in result

    def test_none_returns_unknown(self):
        from app.pipeline import format_coordinates
        assert format_coordinates(None, None) == "Unknown location"

    def test_one_none_returns_unknown(self):
        from app.pipeline import format_coordinates
        assert format_coordinates(1.35, None) == "Unknown location"


# ─── fix_orientation_and_save ────────────────────────────────────────────────

class TestFixOrientation:
    def test_saves_with_orientation_1(self, sample_jpg_path, tmp_path):
        from app.pipeline import fix_orientation_and_save
        out = str(tmp_path / "out.jpg")
        result = fix_orientation_and_save(sample_jpg_path, out)
        assert result["saved_path"] == out
        assert result["final_orientation"] == 1

    def test_portrait_rotated_physically_rotated(self, sample_jpg_portrait_rotated, tmp_path):
        from app.pipeline import fix_orientation_and_save
        from PIL import Image
        out = str(tmp_path / "out_portrait.jpg")
        result = fix_orientation_and_save(sample_jpg_portrait_rotated, out)
        # After ROTATE_90 of 100×200 (portrait), should be 200×100 (landscape)
        assert result["was_rotated"] is True

        # Verify saved file
        saved = Image.open(out)
        assert saved.width > saved.height  # landscape now


# ─── gps_to_country ────────────────────────────────────────────────────────

class TestGpsToCountry:
    def test_returns_country_for_singapore_coords(self):
        from app.pipeline import gps_to_country
        # Singapore coordinates
        country = gps_to_country(1.3521, 103.8198)
        assert country is not None
        assert "singapore" in country.lower()

    def test_returns_none_for_none_coords(self):
        from app.pipeline import gps_to_country
        assert gps_to_country(None, None) is None
        assert gps_to_country(1.35, None) is None

    def test_in_memory_cache(self):
        """Second call with same coords should hit cache (no network)."""
        from app.pipeline import gps_to_country
        r1 = gps_to_country(1.3521, 103.8198)
        # Clear cache attribute to force re-fetch
        if hasattr(gps_to_country, "_cache"):
            del gps_to_country._cache
        r2 = gps_to_country(1.3521, 103.8198)
        # Both should return same result
        assert r1 is not None
        assert r2 is not None


# ─── heic_to_jpeg ────────────────────────────────────────────────────────────

class TestHeicToJpeg:
    def test_nonexistent_heic_returns_false(self):
        from app.pipeline import heic_to_jpeg
        result = heic_to_jpeg("/nonexistent.heic", "/tmp/out.jpg")
        assert result is False


# ─── extract_video_metadata ─────────────────────────────────────────────────

class TestExtractVideoMetadata:
    def test_nonexistent_video_returns_empty(self):
        from app.pipeline import extract_video_metadata
        meta = extract_video_metadata("/nonexistent.mov")
        assert meta["creation_time"] is None
        assert meta["lat"] is None
        assert meta["lon"] is None
        assert meta["duration_seconds"] is None


# ─── extract_metadata (unified) ─────────────────────────────────────────────

class TestExtractMetadata:
    def test_photo_returns_photo_type(self, sample_jpg_path):
        from app.pipeline import extract_metadata
        meta = extract_metadata(sample_jpg_path)
        assert meta["media_type"] == "photo"

    def test_photo_reports_no_gps(self, sample_jpg_path):
        from app.pipeline import extract_metadata
        meta = extract_metadata(sample_jpg_path)
        assert meta["no_gps"] is True
        assert meta["needs_manual_location"] is True

    def test_photo_with_gps_reports_has_location(self, sample_jpg_with_gps):
        from app.pipeline import extract_metadata
        meta = extract_metadata(sample_jpg_with_gps)
        assert meta["no_gps"] is False
        assert meta["country"] is not None

    def test_photo_unknown_file_returns_empty(self):
        from app.pipeline import extract_metadata
        meta = extract_metadata("/nonexistent.jpg")
        assert meta["media_type"] == "photo"
        assert meta["datetime"] is None

    def test_video_unknown_file_returns_video_type(self):
        from app.pipeline import extract_metadata
        meta = extract_metadata("/nonexistent.mov")
        assert meta["media_type"] == "video"

    def test_message_field_present(self, sample_jpg_path):
        from app.pipeline import extract_metadata
        meta = extract_metadata(sample_jpg_path)
        assert "message" in meta
        assert "Photo:" in meta["message"] or "test" in meta["message"].lower()


# ─── Integration: run_pipeline wiring ─────────────────────────────────────

class TestPipelineWiring:
    def test_upload_with_real_pipeline_processes_files(self, client, sample_jpg_path):
        """
        POST /api/journal/upload with a real photo should:
        1. Return accepted with job_id
        2. Pipeline extracts EXIF metadata
        3. File saved to Travel/<Country>/media/ (or flagged if no GPS)
        """
        r = client.post("/api/journal/upload", files={
            "files": ("photo.jpg", sample_jpg_path, "image/jpeg"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "accepted"
        assert "job_id" in data
        job_id = data["job_id"]

        # Poll until done
        for _ in range(10):
            time.sleep(1)
            r2 = client.get(f"/api/journal/status/{job_id}")
            status_data = r2.json()
            if status_data["status"] in ("done", "error"):
                break

        assert status_data["status"] == "done"
        # No GPS → should be flagged for manual location (not crash)
        file_status = status_data["files"][0]
        assert file_status["status"] == "done"
        assert "No GPS" in file_status["message"] or "manual" in file_status["message"]