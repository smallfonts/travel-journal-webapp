"""
Enrichment module — AI-powered caption and summary generation.

Functions:
- enrich_caption_with_vision() — MiniMax vision to enrich user caption
- generate_daily_mochimon_summary() — MiniMax LLM to summarise all events
"""
import os, json, base64, urllib.request, urllib.error
from typing import Optional

MINIMAX_API_KEY = None   # loaded lazily from ~/.hermes/.env
MINIMAX_BASE = "https://api.minimax.chat/v1"


def _load_api_key() -> str:
    global MINIMAX_API_KEY
    if MINIMAX_API_KEY is None:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("MINIMAX_API_KEY="):
                        MINIMAX_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not MINIMAX_API_KEY:
            raise RuntimeError("MINIMAX_API_KEY not found in ~/.hermes/.env")
    return MINIMAX_API_KEY


def _mini_max_vision(prompt: str, image_path: str = None, model: str = "image-01") -> dict:
    """
    Call MiniMax API with an optional image attachment.

    Returns {"ok": True, "content": "...", "revised_prompt": "..."}
    or {"ok": False, "error": "..."}.
    """
    key = _load_api_key()
    url = f"{MINIMAX_BASE}/text/chatcompletion_v2?model=image-01"

    messages = [{"role": "user", "content": []}]
    if image_path:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })
    messages[0]["content"].append({"type": "text", "text": prompt})

    payload = {"model": model, "messages": messages}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        revised = content
        return {"ok": True, "content": content, "revised_prompt": revised}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def enrich_caption_with_vision(
    image_path: str,
    user_caption: str,
    location_hint: str = None,
    activity_hint: str = None,
) -> str:
    """
    Use MiniMax vision to enrich/extend the user's raw caption with
    details visible in the photo (scene, food, people, mood, etc.).

    Returns enriched caption string (may replace or extend user_caption).
    """
    location_part = f"\nLocation context: {location_hint}" if location_hint else ""
    activity_part = f"\nKnown activity: {activity_hint}" if activity_hint else ""

    vision_prompt = (
        f"You are given a travel photo and a user-provided caption.\n"
        f"User caption: \"{user_caption}\"\n"
        f"{location_part}{activity_part}\n\n"
        f"Your task: enrich the caption with vivid, specific details visible in the photo "
        f"(e.g. food names, dishes, place names, mood, weather, what people are doing).\n"
        f"Write a single, enriched caption (1-2 sentences, natural prose, not a list).\n"
        f"Do NOT make up details you cannot see. Keep the original spirit of the caption.\n"
        f"Output ONLY the enriched caption text, nothing else."
    )

    result = _mini_max_vision(vision_prompt, image_path=image_path)
    if result["ok"]:
        return result["content"].strip()
    else:
        # Fall back to user caption unchanged
        return user_caption


def generate_daily_mochimon_summary(
    entries: list[dict],  # [{"time": "HH:MM", "caption": "...", "location": "..."}]
    country: str,
    date_readable: str,   # e.g. "Tuesday, 12 May 2026"
) -> str:
    """
    Use MiniMax LLM to generate a MochiMon daily summary from all event entries.

    entries: list of {time, enriched_caption, location} for the day
    Returns prose summary string (2-3 sentences, key events in chronological order).
    """
    key = _load_api_key()
    url = f"{MINIMAX_BASE}/text/chatcompletion_v2?model=abab6.5s-chat"

    if not entries:
        return f"A quiet day in {country} — rest and recharge before the next adventure! 🌙"

    events_text = "\n".join(
        f"- {e['time']}: {e.get('enriched_caption', e.get('caption', ''))}"
        + (f" at {e['location']}" if e.get("location") else "")
        for e in entries
    )

    prompt = (
        f"You are MochiMon 🍡 — a tiny kawaii mochi companion writing a warm, prose summary "
        f"of a day's travel events.\n\n"
        f"Date: {date_readable}\n"
        f"Country: {country}\n\n"
        f"Today's events:\n"
        f"{events_text}\n\n"
        f"Write a 2-3 sentence prose summary in MochiMon's voice:\n"
        f"- Chronological order, key highlights (food, places, activities)\n"
        f"- Warm and affectionate tone, mention country/context\n"
        f"- End with a forward-looking note\n"
        f"- Avoid excessive emojis (1-3 max)\n"
        f"- Do NOT use bullet points\n\n"
        f"Output ONLY the summary text, nothing else."
    )

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    payload = {"model": "abab6.5s-chat", "messages": messages}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        # Fallback summary
        highlights = "; ".join(e.get("enriched_caption", e.get("caption", "")) for e in entries[:3])
        return f"A wonderful day in {country}! Highlights: {highlights}. 🌟"