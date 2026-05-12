"""
Tests for Stage 5: Journal Entry Integration.
Run with: pytest tests/test_journal.py -v
"""
import pytest, os, tempfile
from pathlib import Path

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary vault with Travel/ folder."""
    vault = tmp_path / "vault"
    travel = vault / "Travel"
    travel.mkdir(parents=True)
    # Create Singapore country folder with media dir
    sg = travel / "Singapore"
    sg.mkdir()
    (sg / "media").mkdir()
    return str(vault)


@pytest.fixture
def template_vault(tmp_vault):
    """Create a vault with the daily template."""
    template_dir = Path(tmp_vault) / "Travel"
    template = template_dir / "Travel Journal Entry Daily Template (YYYY-MM-DD).md"
    template.write_text("""# ☁️Mochi's Dreamscape
<!--Insert ai generated image based on today's events -->
```cards-album
@card [color-blue,waterfall-3]
images:

![[placeholder.jpg]]
```
> [!SUMMARY] 🍡 MochiMon says...

# Travel Timeline

### ⏰ Morning

### 🌤️ Afternoon

### 🌙 Evening
""")
    return tmp_vault


# ─── get_journal_path ─────────────────────────────────────────────────────────

class TestGetJournalPath:
    def test_simple_country(self, tmp_vault):
        from app.journal import get_journal_path
        path = get_journal_path(tmp_vault, "Singapore", "2026-05-12")
        assert path.endswith("Travel/Singapore/2026-05-12 Singapore.md")

    def test_country_with_spaces(self, tmp_vault):
        from app.journal import get_journal_path
        path = get_journal_path(tmp_vault, "South Korea", "2026-05-12")
        assert path.endswith("Travel/South-Korea/2026-05-12 South-Korea.md")

    def test_country_with_hyphen(self, tmp_vault):
        from app.journal import get_journal_path
        path = get_journal_path(tmp_vault, "New Zealand", "2026-05-12")
        assert path.endswith("Travel/New-Zealand/2026-05-12 New-Zealand.md")


# ─── get_media_dir ───────────────────────────────────────────────────────────

class TestGetMediaDir:
    def test_returns_media_subdir(self, tmp_vault):
        from app.journal import get_media_dir
        path = get_media_dir(tmp_vault, "Singapore")
        assert path.endswith("Travel/Singapore/media")


# ─── read_journal / write_journal ────────────────────────────────────────────

class TestJournalReadWrite:
    def test_write_then_read(self, tmp_vault):
        from app.journal import write_journal, read_journal
        path = os.path.join(tmp_vault, "Travel", "Singapore", "test.md")
        write_journal(path, "# Test\nContent here")
        content = read_journal(path)
        assert content == "# Test\nContent here"

    def test_read_nonexistent_returns_none(self, tmp_vault):
        from app.journal import read_journal
        result = read_journal("/nonexistent/file.md")
        assert result is None

    def test_write_creates_parent_dirs(self, tmp_vault):
        from app.journal import write_journal
        path = os.path.join(tmp_vault, "Travel", "Japan", "deep", "test.md")
        write_journal(path, "Hello")
        assert os.path.exists(path)


# ─── create_journal_entry ─────────────────────────────────────────────────────

class TestCreateJournalEntry:
    def test_creates_file_from_template(self, template_vault):
        from app.journal import create_journal_entry, read_journal
        result = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                      lat=1.35, lon=103.8, day_num=3)
        assert os.path.exists(result)
        content = read_journal(result)
        assert "2026-05-12" in content
        assert "Singapore" in content
        assert "1.35" in content
        assert "103.8" in content

    def test_uses_fallback_template(self, tmp_vault):
        from app.journal import create_journal_entry, read_journal
        # No template available — uses fallback
        result = create_journal_entry(tmp_vault, "Japan", "2026-04-23",
                                      lat=35.67, lon=139.65, day_num=1)
        assert os.path.exists(result)
        content = read_journal(result)
        assert "Travel Timeline" in content
        assert "Mochi's Dreamscape" in content

    def test_day_number_in_content(self, template_vault):
        from app.journal import create_journal_entry, read_journal
        result = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                      lat=1.35, lon=103.8, day_num=7)
        content = read_journal(result)
        assert "Day 7" in content


# ─── insert_media_into_journal ────────────────────────────────────────────────

class TestInsertMedia:
    def test_insert_creates_hour_section_if_missing(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        # Create journal with no events
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        # Insert a 9:30 AM event
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "photo.jpg")
        insert_media_into_journal(jpath, "09:30", "Morning walk at Botanic Gardens", media_path)
        content = read_journal(jpath)
        assert "# 9:30 AM" in content
        assert "Morning walk" in content
        assert "![[photo.jpg]]" in content

    def test_insert_with_video(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "video.mov")
        insert_media_into_journal(jpath, "14:00", " Afternoon hike", media_path, is_video=True)
        content = read_journal(jpath)
        assert "# 2:00 PM" in content
        assert "![[video.mov]]" in content

    def test_insert_after_existing_section(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        # Insert into morning section (already has ### Morning heading)
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "photo.jpg")
        insert_media_into_journal(jpath, "08:00", "Breakfast at Toast Box", media_path)
        content = read_journal(jpath)
        assert "# 8:00 AM" in content
        assert "Breakfast at Toast Box" in content

    def test_preserves_existing_content(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "photo.jpg")
        insert_media_into_journal(jpath, "09:30", "Morning walk", media_path)
        content = read_journal(jpath)
        # Template sections still intact
        assert "Mochi's Dreamscape" in content
        assert "Travel Timeline" in content

    def test_original_input_comment_added(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "photo.jpg")
        insert_media_into_journal(jpath, "10:00", "Lunch at Clark Quay", media_path)
        content = read_journal(jpath)
        assert "<!--Original Input from Me: Lunch at Clark Quay-->" in content
        assert "> [!NOTE] Lunch at Clark Quay" in content

    def test_time_conversion(self, template_vault):
        from app.journal import insert_media_into_journal, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        media_path = os.path.join(template_vault, "Travel", "Singapore", "media", "photo.jpg")
        # 14:30 → 2:30 PM
        insert_media_into_journal(jpath, "14:30", "Afternoon snack", media_path)
        content = read_journal(jpath)
        assert "# 2:30 PM" in content


# ─── insert_ai_image_into_dreamscape ─────────────────────────────────────────

class TestInsertDreamscape:
    def test_insert_into_existing_dreamscape(self, template_vault):
        from app.journal import insert_ai_image_into_dreamscape, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        insert_ai_image_into_dreamscape(jpath, "2026-05-12-0930-walk.jpg")
        content = read_journal(jpath)
        assert "![[2026-05-12-0930-walk.jpg]]" in content

    def test_multiple_ai_images_all_present(self, template_vault):
        from app.journal import insert_ai_image_into_dreamscape, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        insert_ai_image_into_dreamscape(jpath, "2026-05-12-0930-walk.jpg")
        insert_ai_image_into_dreamscape(jpath, "2026-05-12-1230-lunch.jpg")
        content = read_journal(jpath)
        assert "![[2026-05-12-0930-walk.jpg]]" in content
        assert "![[2026-05-12-1230-lunch.jpg]]" in content


# ─── update_mochimon_summary ─────────────────────────────────────────────────

class TestMochiMonSummary:
    def test_updates_existing_summary(self, template_vault):
        from app.journal import update_mochimon_summary, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        update_mochimon_summary(jpath, "A wonderful day exploring Gardens by the Bay! 🌺")
        content = read_journal(jpath)
        assert "A wonderful day exploring Gardens by the Bay! 🌺" in content

    def test_preserves_others_content(self, template_vault):
        from app.journal import update_mochimon_summary, read_journal, create_journal_entry
        jpath = create_journal_entry(template_vault, "Singapore", "2026-05-12",
                                     lat=1.35, lon=103.8, day_num=1)
        update_mochimon_summary(jpath, "New summary text")
        content = read_journal(jpath)
        assert "Travel Timeline" in content
        assert "Mochi's Dreamscape" in content


# ─── Integration: full pipeline in memory ───────────────────────────────────

class TestJournalPipeline:
    def test_create_journal_then_insert_media(self, template_vault):
        from app.journal import (
            create_journal_entry, insert_media_into_journal,
            insert_ai_image_into_dreamscape, update_mochimon_summary,
            read_journal, get_journal_path,
        )
        date_str = "2026-05-12"
        safe_country = "Singapore"

        # Create journal
        jpath = create_journal_entry(template_vault, safe_country, date_str,
                                     lat=1.35, lon=103.8, day_num=1)
        assert os.path.exists(jpath)

        # Insert morning event
        media1 = os.path.join(template_vault, "Travel", safe_country, "media", "morning.jpg")
        insert_media_into_journal(jpath, "09:30", "Morning walk at Botanic Gardens", media1)
        # Insert afternoon event
        media2 = os.path.join(template_vault, "Travel", safe_country, "media", "afternoon.jpg")
        insert_media_into_journal(jpath, "14:00", "Lunch at Clarke Quay", media2)

        # Add AI images
        insert_ai_image_into_dreamscape(jpath, "2026-05-12-0930-walk.jpg")
        insert_ai_image_into_dreamscape(jpath, "2026-05-12-1400-lunch.jpg")

        # Update summary
        update_mochimon_summary(jpath, "A lovely day in Singapore! 🌴")

        content = read_journal(jpath)
        assert "# 9:30 AM" in content
        assert "# 2:00 PM" in content
        assert "![[morning.jpg]]" in content
        assert "![[afternoon.jpg]]" in content
        assert "![[2026-05-12-0930-walk.jpg]]" in content
        assert "A lovely day in Singapore!" in content