# Travel Journal Web App — Task List

## Stage 1 — Project Scaffold
- [x] Create project folder `Projects/TravelJournalWebApp/`
- [x] Create `SPEC.md` (this file, kept in sync as we go)
- [x] Set up FastAPI app skeleton (`main.py`, `app/` package)
- [x] Add `requirements.txt` (fastapi, uvicorn, python-multipart, jinja2, pillow, pillow-heif)
- [x] Create env var config (`.env` template + `settings.py`)
- [x] Verify: `python3 -m uvicorn main:app --port 8001` starts without errors (port 8000 occupied by node/SillyTavern)

## Stage 2 — Web Form UI
- [x] `GET /` — Jinja2 template with upload form (inline HTML — Jinja2Templates causes dict hashing error in hermes-agent venv, using HTMLResponse with template string instead)
- [x] Server bound to `0.0.0.0:8001` — accessible via Tailscale at `http://100.85.28.35:8001`
- [x] Systemd user service (`travel-journal-webapp`) installed and enabled
- [x] Drag-and-drop multi-file upload zone
- [x] Caption textarea, date override input, process_now checkbox
- [x] File preview (thumbnails + filenames) after selection
- [x] Submit button → `POST /upload`
- [x] Mobile-responsive, minimal clean styling

## Stage 3 — Internal REST API
- [x] `POST /api/journal/upload` — multipart endpoint (no auth — accessible via Tailscale only)
- [x] `GET /api/journal/status/{job_id}` — polling endpoint (returns job state + per-file breakdown)
- [x] `GET /health` — liveness check
- [x] SQLite job store (`jobs.db`) with `jobs` + `job_files` tables
- [x] Background task stub (`complete_stub`) — Stage 4 wires in real pipeline
- [x] Frontend JS polls `/api/journal/status/{job_id}` every 2s and renders progress
- [x] Verify: upload a test file and check response + poll cycle

## Stage 4 — Media Processing Pipeline
- [x] File cache step — copy uploaded files to Hermes image/video cache
- [x] EXIF extraction (`extract_photo_metadata()` from travel-journal skill)
- [x] GPS → country routing (Nominatim reverse geocode → `Travel/<Country>/`)
- [x] No-GPS fallback: flag for manual country confirmation
- [x] HEIC → JPEG conversion (pillow_heif for non-Telegram files)
- [x] Orientation fix (save with `exif[0x0112] = 1`)
- [x] Verify: process a test JPEG and HEIC file end-to-end (60 tests passing)
- [x] Pushed at `9683894`

## Stage 5 — Journal Entry Integration
- [x] Read daily template from vault (`Travel Journal Entry Daily Template (YYYY-MM-DD).md` is AI instruction file — use built-in DAILY_TEMPLATE instead)
- [x] Find or create `Travel/<Country>/YYYY-MM-DD <Country>.md`
- [x] Insert into correct hourly section with `cards-album`
- [x] Leaflet marker update (coordinates from EXIF GPS)
- [x] Create journal entry when missing (from built-in DAILY_TEMPLATE with leaflet block, Dreamscape, MochiMon summary, Travel Timeline)
- [x] Verify: end-to-end test — upload photo → check vault entry (81 tests passing, pushed at `db00d01`)

## Stage 6 — AI DreamScape Generation
- [x] MiniMax API integration (read key from `/home/cube/.hermes/.env` directly — os.environ not available in sandbox)
- [x] Pixel-art prompt builder (per-event, MochiMon protagonist, time-of-day lighting, location scene)
- [x] `generate_dreamscape_image()` — end-to-end: build prompt → call MiniMax → save to `Travel/<Country>/media/YYYY-MM-DD-HHMM-dreamscape.jpg`
- [x] Insert into `☁️Mochi's Dreamscape` section via `insert_ai_image_into_dreamscape()`
- [x] Wired into pipeline: AI image generated after each media file is saved + journal updated
- [x] Graceful handling: if AI fails, pipeline continues with warning (no hard failure)
- [x] Verify: 96 tests passing, pushed at `cf1550e`

## Stage 7 — Processing Status + Result Page
- [x] Per-file status: ✅ saved, 📍 location, 🗺️ marker added (wired in run_pipeline, message updates per stage)
- [x] Result page with Obsidian journal link — `showResults()` renders `journal_file` + `journal_url` from result JSON
- [x] DreamScape image preview — `showResults()` uses `/api/media/{country}/{filename}` to display DreamScape JPEG in browser (obsidian:// doesn't work in browser)
- [x] `/api/media/{country}/{filename}` endpoint — serves vault media files for browser display
- [x] "Upload more" button — `resetForm()` clears form, status panel, result links
- [x] **Bug fix: `jobId` JS error** — `renderStatus()` and `showResults()` both now receive `jobId`; `showResults()` reads `data.result.mochimon_summary`
- [x] **Leaflet map marker update** — `update_leaflet_coords()` replaces `coordinate: [lat, lon]` when a photo with GPS is added to an existing journal
- [x] **Caption enrichment via MiniMax vision** — `enrich_caption_with_vision()` in `app/enrich.py` sends photo + user caption to MiniMax vision model and returns enriched prose (scene details, food names, mood). Falls back to original caption on API failure
- [x] **MochiMon daily summary** — `generate_daily_mochimon_summary()` calls MiniMax LLM to generate a warm prose summary from all enriched captions; `update_mochimon_summary()` writes it to all journal files at end of job
- [x] **Dreamscape insertion order** — `insert_ai_image_into_dreamscape()` now appends to last `cards-album` in Dreamscape section (not before MochiMon summary), ensuring proper ordering: Dreamscape images → MochiMon summary → Travel Timeline
- [x] Verify: 96 tests passing, pushed at `93824c1`

## Stage 8 — Integration with Hermes Gateway
- [ ] Expose via gateway reverse proxy rule (`/travel-journal/` → `http://localhost:8000/`)
- [ ] Test web form accessible through gateway
- [ ] API accessible via `curl` from internal network

## Stage 9 — Bug Fixes + Polish
- [x] **Version badge** — `v1.0.1` pill in header; `APP_VERSION` is single source of truth in JS; badge updates to `✓` on results page to confirm fresh state
- [x] **Duplicate journal entries** — pipeline loop now deduplicates by original filename (set tracking); skips and marks duplicate files as "Duplicate — already processed in this job"
- [x] **Poll failed: Can't find variable: jobId** — `showResults(data, jobId)` now receives `jobId` as second argument; version badge refresh confirms page is not stale
- [x] Verify: 96 tests passing, pushed at `1e8e393`

## Stage 10 — HEIC Bug Fixes + Upload Deduplication
- [x] **HEIC GPS/EXIF extraction fixed** — `heic_to_jpeg()` was calling `pillow_heif.open(path)` (wrong API); corrected to `pillow_heif.open_heif(path)` which returns a `HeifFile` with `.info['exif']`
- [x] **EXIF bytes preserved in JPEG** — raw EXIF bytes from `heif.info['exif']` are now embedded directly via `image.save(jpeg_path, "JPEG", exif=raw_exif_bytes)`, ensuring `_getexif()` returns GPS metadata on the converted file
- [x] **GPS parsing fallback** — added `_parse_gps_from_exif_bytes()` helper to parse GPS IFD directly from raw EXIF bytes (RATIONAL type 5 → degrees) when `_getexif()` returns None
- [x] **DateTime parsing fallback** — added `_parse_datetime_from_exif_bytes()` via piexif for when EXIF DateTime tag is present but not normalised by `_getexif()`
- [x] **Upload deduplication** — `create_job()` now deduplicates incoming files by `(filename, size)` tuple; skips duplicate uploads within the same batch and stores only one entry in `job_files`
- [x] **pillow_heif API confirmed** — v0.20.0 uses `open_heif()`, NOT `open()`; `HeifFile` has no `has_exif` attribute; raw bytes in `heif.info['exif']` are reliable
- [x] **piexif GPS key types** — GPS dict uses integer keys (1=N/S, 2=lat, 3=E/W, 4=lon), not string keys; `gps.get("1")` always returned None
- [x] **Portrait photos displayed as landscape (orientation bug)** — `fix_orientation_and_save()` in `app/pipeline.py` had the rotation condition inverted: `orientation == 6 and img.width > img.height` caused portrait photos (h>w) with orient=6 to skip the physical rotation step, then saved with orient=1 — leaving them appearing as landscape in the journal. Corrected back to `img.height > img.width` so portrait photos are physically rotated 90° CW before saving with orient=1
- [x] **GPS data not added to leaflet map (missing markers)** — `update_leaflet_coords()` in `app/journal.py` only updated the `coordinate: [lat, lon]` center point but never added individual `marker:` entries per photo. Fixed: now appends a `marker: default, {lat}, {lon},{anchor},{label},,` line inside the ```leaflet block for every photo with GPS, building an anchor link to the photo's time slot. Also added `time_str` and `location_label` parameters to construct meaningful marker labels. Call site in `main.py` now passes `time_str=time_str` and `location_label=meta["location_string"]`
- [x] **Version bumped to v1.0.5** — `APP_VERSION` in `main.py` line 250
- [x] Verify: 96 tests passing, pushed at `e84bb0e`

---

*Last updated: 2026-05-12*