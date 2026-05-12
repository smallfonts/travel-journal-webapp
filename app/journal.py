"""
Stage 5: Journal Entry Integration.

Functions for:
- Reading the daily template from vault
- Finding or creating Travel/<Country>/YYYY-MM-DD <Country>.md
- Inserting media into correct hourly section with cards-album block
- Vision enrichment via MiniMax (placeholder — called externally)
- Updating MochiMon summary callout
"""
import re, os, json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# ─── Template ────────────────────────────────────────────────────────────────

DAILY_TEMPLATE = """*<[[{date}]] {day_cap}, {date_readable}> — Day {day_num} in {country}>*

**🗺️ Map**
```leaflet
id: {leaflet_id}
zoom: 13
coordinate: [{lat}, {lon}]
height: 300px
```

# ☁️Mochi's Dreamscape

<!--Insert ai generated image based on today's events -->
```cards-album
@card [color-blue,waterfall-3]
images:

![[placeholder.jpg]]
```

# Travel Timeline

### ⏰ Morning

### 🌤️ Afternoon

### 🌙 Evening

> [!SUMMARY] 🍡 MochiMon says...
> Summary of the day updated as events are written
"""


def get_template_path(vault_path: str) -> str:
    """Path to the daily journal entry template."""
    return os.path.join(vault_path, "Travel",
        "Travel Journal Entry Daily Template (YYYY-MM-DD).md")


def get_journal_path(vault_path: str, country: str, date_str: str) -> str:
    """Path to a specific day's journal entry."""
    safe = country.replace(" ", "-")
    return os.path.join(vault_path, "Travel", safe,
        f"{date_str} {safe}.md")


def get_media_dir(vault_path: str, country: str) -> str:
    """Media directory for a country."""
    safe = country.replace(" ", "-")
    return os.path.join(vault_path, "Travel", safe, "media")


# ─── Read / Write journal entries ─────────────────────────────────────────────

def read_journal(path: str) -> Optional[str]:
    """Read a journal file, return content or None if doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_journal(path: str, content: str):
    """Write journal content, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ─── Parse existing journal structure ────────────────────────────────────────

def parse_journal_sections(content: str) -> dict:
    """
    Parse a journal entry and return info about existing structure.
    Returns dict with:
      - has_dreamscape (bool)
      - has_timeline (bool)
      - existing_sections (list of hour headers, e.g. ["# 9:00 AM", "# 12:00 PM"])
      - dreamscape_insert_point (int) — line index after which to insert in Dreamscape
      - timeline_insert_points (dict) — {section_header: line_index} for each hour section
    """
    lines = content.split("\n")
    sections = {}   # header → line index
    in_timeline = False
    in_dreamscape = False

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,3})\s+(\d{1,2}:\d{2}\s*[AP]M)\s*(.*)$", line, re.IGNORECASE)
        if m and "Travel Timeline" not in line:
            sections[line.strip()] = i
        if "# ☁️Mochi's Dreamscape" in line:
            in_dreamscape = True
            in_timeline = False
        elif "# Travel Timeline" in line:
            in_timeline = True
            in_dreamscape = False

    return {
        "sections": sections,
        "in_dreamscape": in_dreamscape,
        "in_timeline": in_timeline,
    }


def find_section_for_time(content: str, time_str: str) -> Optional[str]:
    """
    Given a time string like "14:30", find which hourly section it belongs to.
    Returns the section header line, e.g. "# 2:00 PM", or None if no match.
    Matches against "# HH:MM AM/PM" section headers.
    """
    hour_min = time_str.split(":")[0]
    hour_12 = int(hour_min)
    ampm = "AM" if hour_12 < 12 else "PM"
    if hour_12 == 0:
        hour_12 = 12
    elif hour_12 > 12:
        hour_12 -= 12

    candidates = [
        f"# {hour_12}:00 {ampm}",
        f"# {hour_12}:30 {ampm}",
        f"## {hour_12}:00 {ampm}",
        f"## {hour_12}:30 {ampm}",
        f"### {hour_12}:00 {ampm}",
        f"### {hour_12}:30 {ampm}",
        f"# {hour_12}:00 PM" if ampm == "PM" else f"# {hour_12}:00 AM",
        f"# {hour_12}:30 PM" if ampm == "PM" else f"# {hour_12}:30 AM",
    ]
    for c in candidates:
        if c in content:
            return c

    # No match — look for nearest hour
    for delta in [1, -1]:
        for d in range(1, 4):
            check_h = hour_12 + (delta * d)
            check_ampm = ampm
            if check_h <= 0:
                check_h += 12
                check_ampm = "PM" if ampm == "AM" else "AM"
            elif check_h > 12:
                check_h -= 12
            for suffix in ["00", "30"]:
                for prefix in ["# ", "## ", "### "]:
                    cand = f"{prefix}{check_h}:{suffix} {check_ampm}"
                    if cand in content:
                        return cand
    return None


def insert_after(content: str, marker: str, insert_text: str) -> str:
    """Insert text after the first occurrence of marker."""
    idx = content.find(marker)
    if idx == -1:
        return content + "\n" + insert_text
    return content[:idx] + marker + "\n" + insert_text + content[idx + len(marker):]


def insert_before(content: str, marker: str, insert_text: str) -> str:
    """Insert text before the first occurrence of marker."""
    idx = content.find(marker)
    if idx == -1:
        return content + "\n" + insert_text
    return content[:idx] + insert_text + "\n" + content[idx:]


# ─── Build event block ────────────────────────────────────────────────────────

def build_event_block(
    time_str: str,
    caption: str,
    vault_media_path: str,
    is_video: bool = False,
) -> str:
    """
    Build a complete event block for the timeline.

    Args:
        time_str: "HH:MM" e.g. "14:30" (24-hour)
        caption: user-provided caption text
        vault_media_path: absolute path to the saved media file
        is_video: True for videos
    Returns: markdown string for the event block
    """
    # Convert "14:30" → "2:30 PM"
    h, m = map(int, time_str.split(":"))
    ampm = "AM" if h < 12 else "PM"
    h12 = h if h <= 12 else h - 12
    if h12 == 0:
        h12 = 12
    time_display = f"{h12}:{m:02d} {ampm}"

    # Filename for obsidian link
    filename = os.path.basename(vault_media_path)

    # Determine media type for cards-album
    # For videos, Obsidian can embed MOV/MP4 directly in cards-album
    media_embed = f"![[{filename}]]"

    block = f"""# {time_display}

<!--Original Input from Me: {caption}-->
> [!NOTE] {caption}
>

```cards-album
@card [color-blue,waterfall-3]
images:

{media_embed}
```
"""
    return block.strip()


def build_dreamscape_block(ai_image_filename: str) -> str:
    """Build a cards-album block for the Dreamscape section."""
    return f"""```cards-album
@card [color-blue,waterfall-3]
images:

![[{ai_image_filename}]]
```"""


# ─── Create new journal entry from template ──────────────────────────────────

def create_journal_entry(
    vault_path: str,
    country: str,
    date_str: str,  # "YYYY-MM-DD"
    lat: float,
    lon: float,
    day_num: int = 1,
) -> str:
    """
    Create a new journal entry file from the daily template.
    Returns the path to the created file.

    The vault's template file (Travel Journal Entry Daily Template) is an AI
    instruction file, NOT a blank entry template. Use DAILY_TEMPLATE as base.
    Only use vault template if it contains {date} placeholders.
    """
    template_path = get_template_path(vault_path)
    target_path = get_journal_path(vault_path, country, date_str)

    # Read vault template only if it has {date} placeholders (blank entry template)
    content = None
    if os.path.exists(template_path):
        vault_content = read_journal(template_path)
        if vault_content and "{date}" in vault_content:
            content = vault_content

    # Fall back to built-in DAILY_TEMPLATE
    if content is None:
        content = DAILY_TEMPLATE

    # Parse date for readable format
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

    date_readable = f"{dt.day} {month_names[dt.month - 1]} {dt.year}"
    day_cap = day_names[dt.weekday()]

    # Substitute into template
    content = content.replace("{date}", date_str)
    content = content.replace("{date_readable}", date_readable)
    content = content.replace("{day_cap}", day_cap)
    content = content.replace("{day_num}", str(day_num))
    content = content.replace("{country}", country)
    content = content.replace("{lat}", str(lat))
    content = content.replace("{lon}", str(lon))
    content = content.replace("{leaflet_id}", f"trip-{date_str}")

    # Ensure Travel/<Country>/ directory exists
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    write_journal(target_path, content)
    return target_path


# ─── Insert media into journal ───────────────────────────────────────────────

def insert_media_into_journal(
    journal_path: str,
    time_str: str,
    caption: str,
    vault_media_path: str,
    is_video: bool = False,
) -> str:
    """
    Insert a media event into the journal at the correct hourly section.

    Args:
        journal_path: path to the .md journal file
        time_str: "HH:MM" from EXIF
        caption: description from form
        vault_media_path: absolute path where media was saved
        is_video: whether this is a video

    Returns: updated journal content
    """
    content = read_journal(journal_path)
    if content is None:
        raise FileNotFoundError(f"Journal not found: {journal_path}")

    section = find_section_for_time(content, time_str)

    if section:
        # Find section end and insert after it (before next section or HR)
        section_idx = content.find(section)
        # Find next section or --- or end of file
        remaining = content[section_idx + len(section):]
        # Find next # heading or --- or end
        next_section_match = re.search(r"\n(?=#+\s+\d+:\d+\s)", remaining)
        next_hr_match = re.search(r"\n---", remaining)
        end_idx = len(remaining)
        if next_section_match:
            end_idx = min(end_idx, next_section_match.start())
        if next_hr_match:
            end_idx = min(end_idx, next_hr_match.start())

        insert_pos = section_idx + len(section) + end_idx
        event_block = "\n\n" + build_event_block(time_str, caption, vault_media_path, is_video) + "\n\n"
        content = content[:insert_pos] + event_block + content[insert_pos:]
    else:
        # No matching section — append at end before MochiMon summary or at end
        summary_marker = "> [!SUMMARY] 🍡 MochiMon says..."
        if summary_marker in content:
            content = insert_before(content, summary_marker,
                "\n\n" + build_event_block(time_str, caption, vault_media_path, is_video))
        else:
            content += "\n\n" + build_event_block(time_str, caption, vault_media_path, is_video)

    write_journal(journal_path, content)
    return content


def insert_ai_image_into_dreamscape(
    journal_path: str,
    ai_image_filename: str,
) -> str:
    """
    Insert an AI-generated image into the Dreamscape section.
    Creates the Dreamscape section if it doesn't exist.
    Returns updated journal content.
    """
    content = read_journal(journal_path)
    if content is None:
        raise FileNotFoundError(f"Journal not found: {journal_path}")

    marker = "<!--Insert ai generated image based on today's events -->"
    if marker in content:
        # Insert right after the comment line
        content = insert_after(content, marker,
            build_dreamscape_block(ai_image_filename))
    else:
        # Marker replaced by first cards-album — find the last cards-album
        # inside the Dreamscape section and insert after it
        dreamscape_head = "# ☁️Mochi's Dreamscape"
        timeline_head = "# Travel Timeline"
        ds_start = content.find(dreamscape_head)
        tl_start = content.find(timeline_head)
        if ds_start == -1:
            # No Dreamscape at all — create it before Travel Timeline
            if tl_start != -1:
                dreamscape = "# ☁️Mochi's Dreamscape\n\n" + build_dreamscape_block(ai_image_filename) + "\n\n"
                content = insert_before(content, timeline_head, dreamscape)
            else:
                content += "\n\n" + build_dreamscape_block(ai_image_filename)
        else:
            # Dreamscape exists — find search window (up to Travel Timeline or end)
            search_from = ds_start + len(dreamscape_head)
            search_to = tl_start if tl_start != -1 else len(content)
            ds_region = content[search_from:search_to]
            # Find all cards-album blocks in Dreamscape
            last_album_end = -1
            pos = 0
            while True:
                blk = ds_region.find("```cards-album", pos)
                if blk == -1:
                    break
                end = ds_region.find("```", blk + 14)
                if end == -1:
                    break
                last_album_end = search_from + end + 3
                pos = end + 3
            if last_album_end != -1:
                content = content[:last_album_end] + "\n" + build_dreamscape_block(ai_image_filename) + content[last_album_end:]
            elif tl_start != -1:
                content = insert_before(content, timeline_head,
                    build_dreamscape_block(ai_image_filename) + "\n")
            else:
                content += "\n\n" + build_dreamscape_block(ai_image_filename)

    write_journal(journal_path, content)
    return content


# ─── Update MochiMon summary ──────────────────────────────────────────────────

def update_mochimon_summary(
    journal_path: str,
    summary_text: str,
) -> str:
    """
    Update the [!SUMMARY] callout in the journal with new summary text.
    Returns updated content.
    """
    content = read_journal(journal_path)
    if content is None:
        raise FileNotFoundError(f"Journal not found: {journal_path}")

    marker = "> [!SUMMARY] 🍡 MochiMon says..."
    if marker in content:
        # Replace everything from the marker to the end of the block
        marker_idx = content.find(marker)
        # Find the end of this block (next # heading, next > [! or end of file)
        remaining = content[marker_idx + len(marker):]
        block_end_match = re.search(r"\n(?=#+\s|\n(?:> \[!))", remaining)
        if block_end_match:
            end_pos = marker_idx + len(marker) + block_end_match.start()
        else:
            end_pos = len(content)

        new_block = f"\n> {summary_text}\n"
        content = content[:marker_idx] + marker + new_block + content[end_pos:]
    else:
        # Marker not found — append at end of file
        content += f"\n\n> [!SUMMARY] 🍡 MochiMon says...\n> {summary_text}\n"

    write_journal(journal_path, content)
    return content


def get_mochimon_summary(journal_path: str) -> Optional[str]:
    """Read current MochiMon summary text from journal."""
    content = read_journal(journal_path)
    if content is None:
        return None
    marker = "> [!SUMMARY] 🍡 MochiMon says..."
    idx = content.find(marker)
    if idx == -1:
        return None
    # Extract the lines after the marker
    rest = content[idx + len(marker):]
    lines = []
    for line in rest.split("\n"):
        stripped = line.strip()
        if not stripped:
            break
        if stripped.startswith(">"):
            lines.append(stripped.lstrip(">").strip())
        else:
            break
    return " ".join(lines)


def update_leaflet_coords(journal_path: str, lat: float, lon: float,
                            time_str: str = None, location_label: str = None) -> bool:
    """
    Update the leaflet coordinate block AND add a marker for this photo.

    - Replaces the coordinate: [...] line with the new lat/lon.
    - Appends a new marker: line inside the ```leaflet block.

    Marker format (per vault template convention):
        marker: default, {lat}, {lon},{anchor}, {label},,

    Args:
        journal_path: path like .../Travel/Singapore/2026-05-12 Singapore.md
        lat, lon: GPS coordinates for this photo
        time_str: "HH:MM" from EXIF — used to build anchor link and label
        location_label: human-readable location name (from reverse geocoding)

    Returns True if updated, False if no leaflet block found.
    """
    content = read_journal(journal_path)
    if content is None:
        return False

    # ── 1. Update the coordinate: [lat, lon] center point ──────────────────
    coord_pattern = re.compile(r"coordinate:\s*\[[\d.,\-]+\]")
    new_coord = f"coordinate: [{lat}, {lon}]"

    if not coord_pattern.search(content):
        return False
    content = coord_pattern.sub(new_coord, content, count=1)

    # ── 2. Append a marker: line inside the ```leaflet block ──────────────
    # Extract country and date from journal_path to build anchor link.
    # Path format: .../Travel/<Country>/<date> <Country>.md
    country = None
    date_str = None
    try:
        parts = journal_path.replace("\\", "/").split("/")
        travel_idx = parts.index("Travel")
        country_raw = parts[travel_idx + 1]
        country = country_raw.replace("-", " ")  # "Singapore" stored as "Singapore", "South-Korea" → "South Korea"
        fname = parts[travel_idx + 2]  # "2026-05-12 Singapore.md"
        date_str = fname.split(" ")[0]  # "2026-05-12"
    except (IndexError, ValueError):
        pass

    # Build anchor and label for the marker
    anchor = f"Travel/{country_raw}/{date_str} {country_raw}.md"
    if time_str:
        # Convert "10:30" → "10:30 AM" label
        try:
            h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
            ampm = "AM" if h < 12 else "PM"
            hour_12 = h if h <= 12 else h - 12
            label = f"{hour_12}:{m:02d}{ampm}"
        except (ValueError, IndexError):
            label = time_str
        anchor = f"{anchor}#{time_str}"
    else:
        label = location_label or ""

    marker_line = f"marker: default, {lat}, {lon},{anchor},{label},,"

    # Find the ```leaflet block and append marker inside it
    leaflet_block_match = re.search(r"(```leaflet\n)(.*?)(\n```)", content, re.DOTALL)
    if leaflet_block_match:
        block_content = leaflet_block_match.group(2)
        # Avoid duplicate markers for the same location/time
        if marker_line not in block_content:
            new_block = block_content.rstrip() + "\n" + marker_line + "\n"
            content = content[:leaflet_block_match.start(2)] + new_block + content[leaflet_block_match.end(2):]

    write_journal(journal_path, content)
    return True