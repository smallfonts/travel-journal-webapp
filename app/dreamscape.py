"""
Stage 6: AI DreamScape Generation.

MiniMax image-01 integration for generating MochiMon pixel-art
illustrations for each travel moment, saved to vault and inserted
into the ☁️Mochi's Dreamscape section of the journal.
"""
import os, base64, time, json
import requests

MINIMAX_API_URL = "https://api.minimax.io/v1/image_generation"


def _get_api_key() -> str:
    """Read MiniMax API key directly from .env file (not os.environ)."""
    env_path = "/home/cube/.hermes/.env"
    with open(env_path, "r") as f:
        for line in f:
            if "MINIMAX_API_KEY" in line and not line.strip().startswith("#"):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("MINIMAX_API_KEY not found in /home/cube/.hermes/.env")


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_dreamscape_prompt(
    caption: str,
    location_string: str = "",
    datetime_str: str = "",
    media_type: str = "photo",
) -> str:
    """
    Build a MiniMax pixel-art prompt for MochiMon Dreamscape illustration.

    MochiMon (🍡) is always the protagonist — a kawaii white mochi character
    with a cute face, small stubby horns, and expressive eyes. Set in the
    real travel scene from the user's photo.

    Args:
        caption: User-provided caption from the journal entry
        location_string: Location from EXIF (e.g. "Botanic Gardens, Singapore")
        datetime_str: "YYYY-MM-DD HH:MM" from EXIF
        media_type: "photo" or "video"
    Returns: Full prompt string for MiniMax
    """
    # Determine time of day for lighting/atmosphere
    hour = None
    if datetime_str:
        try:
            hour = int(datetime_str.split(" ")[1].split(":")[0])
        except (IndexError, ValueError):
            pass

    if hour is not None:
        if 6 <= hour < 12:
            time_scene = "morning sunlight, golden hour, warm and bright"
        elif 12 <= hour < 17:
            time_scene = "bright afternoon, clear blue skies, warm sunlight"
        elif 17 <= hour < 20:
            time_scene = "golden sunset, orange and pink skies, warm evening glow"
        else:
            time_scene = "night time, city lights, stars and lanterns, cozy and magical"
    else:
        time_scene = "bright daylight"

    # Extract key activity words from caption for scene richness
    activity = caption if caption else "exploring a beautiful place"

    # Build scene description
    if location_string:
        scene = f"in {location_string}"
    else:
        scene = "in a beautiful scenic location"

    # Style enforcement — always pixel art, always MochiMon as protagonist
    prompt = (
        f"pixel art style, {time_scene}, "
        f"chibi MochiMon (white fluffy mochi creature with cute round face, "
        f"big sparkly eyes, small pink horns, happy expression, standing proudly) "
        f"{scene}, {activity}, "
        f"vibrant colors, fantasy storybook illustration, "
        f"high detail pixel art, clean lines, Nostalgia Zone palette, "
        f"horizontal composition, soft ambient lighting"
    )
    return prompt


# ─── Image Generation ─────────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    aspect_ratio: str = "16:9",
    save_path: str = "/tmp/dreamscape.jpg",
) -> dict:
    """
    Generate an image via MiniMax image-01 API.

    Returns:
        {"ok": bool, "path": str or None, "error": str or None, "prompt": str}
    """
    try:
        api_key = _get_api_key()
    except RuntimeError as e:
        return {"ok": False, "path": None, "error": str(e), "prompt": prompt}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "image-01",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "response_format": "base64",
    }

    try:
        resp = requests.post(MINIMAX_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return {"ok": False, "path": None, "error": "Request timed out after 60s", "prompt": prompt}
    except requests.exceptions.HTTPError as e:
        body = resp.text[:500]
        return {"ok": False, "path": None, "error": f"HTTP {e.code} — {body}", "prompt": prompt}
    except Exception as e:
        return {"ok": False, "path": None, "error": str(e), "prompt": prompt}

    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "path": None, "error": f"Invalid JSON response: {resp.text[:200]}", "prompt": prompt}
    if not isinstance(data, dict):
        return {"ok": False, "path": None, "error": f"Expected JSON object, got {type(data)}: {resp.text[:200]}", "prompt": prompt}
    images = data.get("data", {}) or {}
    if isinstance(images, dict):
        images = images.get("image_base64", []) or []
    if not images:
        return {"ok": False, "path": None, "error": f"No image returned: {data}", "prompt": prompt}

    # Save first image
    try:
        img_bytes = base64.b64decode(images[0])
        with open(save_path, "wb") as f:
            f.write(img_bytes)
        file_size = os.path.getsize(save_path)
        return {"ok": True, "path": save_path, "error": None, "prompt": prompt, "size_bytes": file_size}
    except Exception as e:
        return {"ok": False, "path": None, "error": f"Failed to decode/save: {e}", "prompt": prompt}


# ─── High-level generator ────────────────────────────────────────────────────

def generate_dreamscape_image(
    caption: str,
    location_string: str = "",
    datetime_str: str = "",
    media_type: str = "photo",
    vault_path: str = "/home/cube/Dropbox/Apps/remotely-save/WeeksObsidianVault",
    country: str = "Singapore",
    date_str: str = "2026-01-01",
    time_str: str = "1200",
) -> dict:
    """
    End-to-end: build prompt → generate via MiniMax → save to vault media dir.

    Args:
        caption: User caption describing the moment
        location_string: Location from EXIF GPS
        datetime_str: "YYYY-MM-DD HH:MM:SS" from EXIF
        media_type: "photo" or "video"
        vault_path: Path to Obsidian vault
        country: Country folder name (e.g. "Singapore")
        date_str: "YYYY-MM-DD"
        time_str: "HHMM" (e.g. "1430")

    Returns:
        {"ok": bool, "path": str, "error": str, "prompt": str, "vault_dest": str}
    """
    # Build output path
    safe_country = country.replace(" ", "-")
    media_dir = os.path.join(vault_path, "Travel", safe_country, "media")
    os.makedirs(media_dir, exist_ok=True)

    out_name = f"{date_str}-{time_str}-dreamscape.jpg"
    out_path = os.path.join(media_dir, out_name)

    # Build prompt
    prompt = build_dreamscape_prompt(caption, location_string, datetime_str, media_type)

    # Generate
    result = generate_image(prompt=prompt, aspect_ratio="16:9", save_path=out_path)

    return {
        "ok": result["ok"],
        "path": result.get("path"),
        "error": result.get("error"),
        "prompt": prompt,
        "vault_dest": out_path,
    }