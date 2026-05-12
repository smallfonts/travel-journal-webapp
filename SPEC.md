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
- [ ] Read daily template from vault (`Travel/Travel Journal Entry Daily Template (YYYY-MM-DD).md`)
- [ ] Find or create `Travel/<Country>/YYYY-MM-DD <Country>.md`
- [ ] Insert into correct hourly section with `cards-album`
- [ ] Leaflet marker update (discretion-based)
- [ ] Vision enrichment (`mcp_MiniMax_understand_image`)
- [ ] Update MochiMon summary
- [ ] Verify: end-to-end test — upload photo → check vault entry

## Stage 6 — AI DreamScape Generation
- [ ] MiniMax API integration (read key from `.env`)
- [ ] Pixel-art prompt builder (per-event, MochiMon protagonist, enforcement terms)
- [ ] Save to `Travel/<Country>/media/YYYY-MM-DD-HHMM-eventname.jpg`
- [ ] Insert into `☁️Mochi's Dreamscape` section of journal
- [ ] Verify: AI image appears in journal DreamScape section

## Stage 7 — Processing Status + Result Page
- [ ] Progress tracking (in-memory job store with job_id)
- [ ] Per-file status: ✅ saved, 📍 location, 🗺️ marker added
- [ ] Result page with Obsidian journal link
- [ ] DreamScape image preview
- [ ] "Upload more" button

## Stage 8 — Integration with Hermes Gateway
- [ ] Expose via gateway reverse proxy rule (`/travel-journal/` → `http://localhost:8000/`)
- [ ] Test web form accessible through gateway
- [ ] API accessible via `curl` from internal network

---

*Last updated: 2026-05-12*