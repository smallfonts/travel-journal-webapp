"""
Stage 4: Media Processing Pipeline.

Functions for:
- Photo EXIF extraction (GPS, DateTime, camera, orientation)
- Video metadata extraction (ffprobe text mode)
- HEIC → JPEG conversion
- GPS → country via Nominatim reverse geocoding
- No-GPS fallback (manual confirmation flag)
- Orientation fix (save with exif[0x0112] = 1)
"""
import re, os, subprocess, json
from pathlib import Path
from typing import Optional
from PIL import Image


# ─── Photo EXIF extraction ──────────────────────────────────────────────────

def extract_photo_metadata(img_path: str) -> dict:
    """
    Robust EXIF extraction from JPEG/HEIC/PNG.
    Returns dict with: datetime, lat, lon, camera_make, camera_model,
    orientation, gps_raw, width, height.
    """
    try:
        img = Image.open(img_path)
    except Exception:
        return _empty_meta()

    raw_exif = img._getexif()
    if raw_exif is None:
        # No EXIF at all — still return dimensions
        return {
            **_empty_meta(),
            "width": img.width,
            "height": img.height,
        }

    # DateTime
    datetime = (
        raw_exif.get(36867)   # DateTimeOriginal
        or raw_exif.get(306)  # DateTime
        or None
    )

    # Camera
    make  = raw_exif.get(271)  # Make
    model = raw_exif.get(272)  # Model

    # Orientation (1=normal, 6=portrait rotated, etc.)
    orientation = raw_exif.get(274)

    # GPS (tag 34853) — INTEGER keys, NOT string keys
    gps_raw = raw_exif.get(34853)
    lat, lon = None, None
    if gps_raw and isinstance(gps_raw, dict):
        def to_decimal(t, ref):
            d, m, s = float(t[0]), float(t[1]), float(t[2])
            sign = -1 if ref in ("S", "W") else 1
            return sign * (d + m / 60 + s / 3600)

        try:
            if 2 in gps_raw and 1 in gps_raw:
                lat = to_decimal(gps_raw[2], gps_raw[1])
            if 4 in gps_raw and 3 in gps_raw:
                lon = to_decimal(gps_raw[4], gps_raw[3])
        except (TypeError, KeyError, ZeroDivisionError):
            lat, lon = None, None

    return {
        "datetime":    datetime,
        "lat":         lat,
        "lon":         lon,
        "camera_make": make,
        "camera_model": model,
        "orientation": orientation,
        "gps_raw":     gps_raw,
        "width":       img.width,
        "height":      img.height,
    }


def _empty_meta():
    return {
        "datetime": None, "lat": None, "lon": None,
        "camera_make": None, "camera_model": None,
        "orientation": None, "gps_raw": None,
        "width": None, "height": None,
    }


# ─── Video metadata via ffprobe ───────────────────────────────────────────────

def extract_video_metadata(video_path: str) -> dict:
    """
    Extract metadata from MOV/MP4 using ffprobe TEXT/grep mode.
    Returns: creation_time (UTC ISO str), lat, lon, duration_seconds.
    """
    fmt_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_format", video_path],
        capture_output=True, text=True,
    )
    streams_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_streams", video_path],
        capture_output=True, text=True,
    )

    creation_time = None
    iso6709 = None
    duration = None

    for line in fmt_result.stdout.splitlines():
        if line.startswith("TAG:creation_time="):
            creation_time = line.split("=", 1)[1].strip()
        elif line.startswith("TAG:com.apple.quicktime.location.ISO6709="):
            iso6709 = line.split("=", 1)[1].strip()
        elif line.startswith("duration="):
            try:
                duration = float(line.split("=", 1)[1])
            except ValueError:
                pass

    # Parse GPS from ISO6709 (e.g. "+01.3975+103.8934+026.435/")
    lat, lon = None, None
    if iso6709:
        match = re.match(r"([+-]\d+\.\d+)([+-]\d+\.\d+)", iso6709)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))

    # Resolution from streams
    width, height, codec = None, None, None
    for line in streams_result.stdout.splitlines():
        if line.startswith("width="):
            try:
                width = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("height="):
            try:
                height = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("codec_name="):
            codec = line.split("=", 1)[1].strip()

    return {
        "creation_time":   creation_time,
        "lat":             lat,
        "lon":             lon,
        "duration_seconds": duration,
        "width":           width,
        "height":          height,
        "codec":           codec,
    }


# ─── HEIC → JPEG conversion ──────────────────────────────────────────────────

def heic_to_jpeg(heic_path: str, jpeg_path: str, quality: int = 90) -> bool:
    """
    Convert a HEIC file to JPEG.
    Returns True on success, False if pillow-heif is unavailable or conversion fails.
    """
    try:
        import pillow_heif
    except ImportError:
        # pillow-heif not installed — try using Image directly (some HEICs PIL can open)
        try:
            with Image.open(heic_path) as img:
                img.save(jpeg_path, "JPEG", quality=quality)
            return True
        except Exception:
            return False

    try:
        heif_file = pillow_heif.open(heic_path)
        image = heif_file.to_pillow()
        image.save(jpeg_path, "JPEG", quality=quality)
        return True
    except Exception:
        return False


# ─── Orientation fix ──────────────────────────────────────────────────────────

def fix_orientation_and_save(img_path: str, output_path: str, quality: int = 90) -> dict:
    """
    Load an image, fix its orientation tag to 1 (normal), and save to output_path.
    If orientation indicates rotation is needed, physically rotates the pixels
    before saving (decision tree: check raw pixels vs EXIF tag).

    Returns dict with: saved_path, was_rotated (bool), final_orientation (int).
    """
    img = Image.open(img_path)
    raw_exif = img._getexif()
    orientation = raw_exif.get(274) if raw_exif else 1

    was_rotated = False

    # Decision tree: should we physically rotate?
    if orientation == 6 and img.height > img.width:
        # Orientation=6 (Rotate CW 90°) AND raw pixels already portrait (h>w)
        # → viewer double-rotates. Fix: physically rotate 90° CW → then save with orient=1
        img = img.transpose(Image.ROTATE_90)
        was_rotated = True
    elif orientation in (3, 8) and img.width > img.height:
        # 3 = Rotate 180°, 8 = Rotate CCW 90°
        # Only apply if raw pixels don't match what the viewer would produce
        # Simple heuristic: rotate 180 for orient 3, CCW 90 for orient 8
        rotations = {3: Image.ROTATE_180, 8: Image.ROTATE_270}
        img = img.transpose(rotations[orientation])
        was_rotated = True
    # else: orient=1 (normal) or already-correct raw pixels → save as-is

    # Build EXIF with orientation = 1
    new_exif = Image.Exif()
    new_exif[0x0112] = 1  # Orientation: normal

    img.save(output_path, "JPEG", quality=quality, exif=new_exif)

    return {
        "saved_path":         output_path,
        "was_rotated":        was_rotated,
        "final_orientation":  1,
    }


# ─── GPS → Country via Nominatim ─────────────────────────────────────────────

def gps_to_country(lat: float, lon: float) -> Optional[str]:
    """
    Reverse geocode GPS coordinates to a country name via Nominatim.
    Returns country name (e.g. "Singapore", "Japan") or None on failure.
    Caches results in memory to avoid repeated API calls for same coords.
    """
    if lat is None or lon is None:
        return None

    # Round to 2 decimal places (~1km) for cache grouping
    cache_key = (round(lat, 2), round(lon, 2))
    if hasattr(gps_to_country, "_cache"):
        if cache_key in gps_to_country._cache:
            return gps_to_country._cache[cache_key]
    else:
        gps_to_country._cache = {}

    try:
        import urllib.request
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?format=json&lat={lat}&lon={lon}&addressdetails=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "TravelJournalApp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        country = (
            data.get("address", {}).get("country")
            or data.get("address", {}).get("country_code", "").title()
        )
        gps_to_country._cache[cache_key] = country
        return country
    except Exception:
        return None


def format_coordinates(lat: float, lon: float) -> str:
    """Format lat/lon as a human-readable string."""
    if lat is None or lon is None:
        return "Unknown location"
    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}"


# ─── Date parsing ─────────────────────────────────────────────────────────────

def parse_exif_datetime(dt_str: str) -> Optional[str]:
    """
    Parse EXIF DateTime string ('YYYY:MM:DD HH:MM:SS') → 'YYYY-MM-DD HH:MM:SS'.
    Returns None if parsing fails.
    """
    if not dt_str:
        return None
    try:
        from datetime import datetime
        dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Try other formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                from datetime import datetime
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None


def extract_date_from_video(creation_time: str) -> Optional[str]:
    """
    Convert ffprobe creation_time (UTC ISO string) to local date string.
    ffprobe returns: '2026-05-01T09:30:45.000000Z' (UTC)
    We treat it as Singapore time (UTC+8) for display purposes.
    """
    if not creation_time:
        return None
    try:
        from datetime import datetime, timezone, timedelta
        # Strip microseconds and Z
        ct = re.sub(r"\.\d+Z?$", "", creation_time.rstrip("Z"))
        dt_utc = datetime.fromisoformat(ct).replace(tzinfo=timezone.utc)
        # Assume Singapore timezone (UTC+8) for local date
        sg = dt_utc.astimezone(timezone(timedelta(hours=8)))
        return sg.strftime("%Y-%m-%d")
    except Exception:
        return None


# ─── Full media metadata extraction (photo or video) ─────────────────────────

def extract_metadata(media_path: str) -> dict:
    """
    Unified metadata extraction for photos (JPEG/PNG/HEIC) and videos (MOV/MP4).
    Returns dict with: media_type ('photo'|'video'), datetime, lat, lon,
    country (derived), location_string, camera_make, camera_model,
    orientation, width, height, duration_seconds, no_gps (bool),
    needs_manual_location (bool), message (str).
    """
    path_lower = media_path.lower()
    is_video = path_lower.endswith((".mov", ".mp4", ".m4v"))

    if is_video:
        meta = extract_video_metadata(media_path)
        datetime_str = extract_date_from_video(meta.get("creation_time"))
        lat, lon = meta.get("lat"), meta.get("lon")
        message = (
            f"Video: {meta.get('codec', '?')} "
            f"{meta.get('width', '?')}×{meta.get('height', '?')}, "
            f"{meta.get('duration_seconds') or 0:.0f}s"
        )
    else:
        # Photo (JPEG, PNG, WebP, HEIC)
        # For HEIC files not yet converted, try conversion first
        if path_lower.endswith(".heic"):
            jpeg_path = media_path + ".jpg"
            if heic_to_jpeg(media_path, jpeg_path):
                media_path = jpeg_path  # use the converted JPEG for EXIF

        meta = extract_photo_metadata(media_path)
        datetime_str = parse_exif_datetime(meta.get("datetime"))
        lat, lon = meta.get("lat"), meta.get("lon")
        message = (
            f"Photo: {meta.get('width', '?')}×{meta.get('height', '?')}, "
            f"camera: {meta.get('camera_make', '')} {meta.get('camera_model', '')}"
        ).strip()

    country = gps_to_country(lat, lon) if lat is not None and lon is not None else None
    location_string = format_coordinates(lat, lon) if lat is not None else None
    no_gps = lat is None or lon is None
    needs_manual_location = no_gps

    return {
        "media_type":               "video" if is_video else "photo",
        "datetime":                 datetime_str,
        "lat":                     lat,
        "lon":                     lon,
        "country":                 country,
        "location_string":         location_string,
        "camera_make":             meta.get("camera_make"),
        "camera_model":            meta.get("camera_model"),
        "orientation":             meta.get("orientation"),
        "width":                   meta.get("width"),
        "height":                  meta.get("height"),
        "duration_seconds":        meta.get("duration_seconds"),
        "no_gps":                  no_gps,
        "needs_manual_location":   needs_manual_location,
        "message":                 message,
        "original_path":            media_path,
    }