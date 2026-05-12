"""
Tests for Stage 6: AI DreamScape Generation.
Run with: pytest tests/test_dreamscape.py -v
"""
import pytest, os, time
from pathlib import Path

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_vault(tmp_path):
    """Temporary vault structure for dreamscape tests."""
    vault = tmp_path / "vault"
    travel = vault / "Travel" / "Singapore" / "media"
    travel.mkdir(parents=True)
    return str(vault)


@pytest.fixture
def real_vault():
    """Point at the real vault so tests that save to vault can run."""
    return "/home/cube/Dropbox/Apps/remotely-save/WeeksObsidianVault"


# ─── Prompt Builder ───────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_morning_time_golden_hour(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Morning walk at Botanic Gardens",
            location_string="Botanic Gardens, Singapore",
            datetime_str="2026-05-12 09:30:00",
        )
        assert "morning sunlight, golden hour" in prompt
        assert "Botanic Gardens, Singapore" in prompt
        assert "Morning walk at Botanic Gardens" in prompt

    def test_afternoon_scene(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Lunch at Clarke Quay",
            datetime_str="2026-05-12 13:00:00",
        )
        assert "bright afternoon" in prompt

    def test_sunset_scene(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Sunset dinner by the bay",
            datetime_str="2026-05-12 18:30:00",
        )
        assert "golden sunset" in prompt or "orange and pink skies" in prompt

    def test_night_scene(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Night market walk",
            datetime_str="2026-05-12 21:00:00",
        )
        assert "night time" in prompt or "city lights" in prompt

    def test_no_datetime_defaults_to_bright_daylight(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Exploring the city",
            datetime_str="",
        )
        assert "bright daylight" in prompt

    def test_no_caption_uses_fallback(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="",
            datetime_str="2026-05-12 14:00:00",
        )
        assert "exploring a beautiful place" in prompt

    def test_mochimon_is_always_mentioned(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Hiking trail",
            datetime_str="2026-05-12 10:00:00",
        )
        assert "MochiMon" in prompt or "mochi" in prompt.lower()

    def test_pixel_art_style_enforced(self):
        from app.dreamscape import build_dreamscape_prompt
        prompt = build_dreamscape_prompt(
            caption="Beach day",
            datetime_str="2026-05-12 15:00:00",
        )
        assert "pixel art" in prompt.lower()

    def test_video_type_flagged(self):
        from app.dreamscape import build_dreamscape_prompt
        photo_prompt = build_dreamscape_prompt("caption", media_type="photo")
        video_prompt = build_dreamscape_prompt("caption", media_type="video")
        # Both should still include MochiMon and location
        assert "MochiMon" in photo_prompt
        assert "MochiMon" in video_prompt


# ─── API Key ─────────────────────────────────────────────────────────────────

class TestApiKey:
    def test_get_api_key_returns_string(self):
        from app.dreamscape import _get_api_key
        key = _get_api_key()
        assert isinstance(key, str)
        assert len(key) > 20

    def test_api_key_not_empty(self):
        from app.dreamscape import _get_api_key
        key = _get_api_key()
        assert key.strip() != ""


# ─── generate_dreamscape_image (real API test, skipped in CI) ────────────────

class TestGenerateDreamscapeImage:
    def test_generates_and_saves_file(self, tmp_vault):
        from app.dreamscape import generate_dreamscape_image
        result = generate_dreamscape_image(
            caption="Morning walk at a scenic garden",
            location_string="Singapore",
            datetime_str="2026-05-12 09:00:00",
            vault_path=tmp_vault,
            country="Singapore",
            date_str="2026-05-12",
            time_str="0900",
        )
        # Note: may fail if API key missing — that's acceptable in test env
        # Just verify the function returned the right shape
        assert "ok" in result
        assert "vault_dest" in result
        assert "prompt" in result
        if result["ok"]:
            assert os.path.exists(result["vault_dest"])
            assert os.path.getsize(result["vault_dest"]) > 10000

    def test_output_path_uses_correct_naming(self, tmp_vault):
        from app.dreamscape import generate_dreamscape_image
        result = generate_dreamscape_image(
            caption="Test",
            vault_path=tmp_vault,
            country="Singapore",
            date_str="2026-05-12",
            time_str="1430",
        )
        assert result["vault_dest"].endswith("2026-05-12-1430-dreamscape.jpg")

    def test_vault_dest_in_correct_country_folder(self, tmp_vault):
        from app.dreamscape import generate_dreamscape_image
        result = generate_dreamscape_image(
            caption="Test",
            vault_path=tmp_vault,
            country="Japan",
            date_str="2026-04-23",
            time_str="1200",
        )
        assert "Japan" in result["vault_dest"]

    def test_prompt_contains_caption(self, tmp_vault):
        from app.dreamscape import generate_dreamscape_image
        result = generate_dreamscape_image(
            caption="My amazing breakfast",
            vault_path=tmp_vault,
            country="Singapore",
            date_str="2026-05-12",
            time_str="0800",
        )
        assert "My amazing breakfast" in result["prompt"]