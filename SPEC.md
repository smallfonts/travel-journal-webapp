# Travel Journal Web App — Task List

## Stage 1 — Project Scaffold
- [ ] Create project folder `Projects/TravelJournalWebApp/`
- [ ] Create `SPEC.md` (this file, kept in sync as we go)
- [ ] Set up FastAPI app skeleton (`main.py`, `app/` package)
- [ ] Add `requirements.txt` (fastapi, uvicorn, python-multipart, jinja2, pillow, pillow-heif)
- [ ] Create env var config (`.env` template + `settings.py`)
- [ ] Verify: `python3 -m uvicorn app.main:app --port 8000` starts without errors

## Stage 2 — Web Form UI
- [ ] `GET /` — Jinja2 template with upload form
- [ ] Drag-and-drop multi-file upload zone
- [ ] Caption textarea, date override input, process_now checkbox
- [ ] File preview (thumbnails + filenames) after selection
- [ ] Submit button → `POST /upload`
- [ ] Mobile-responsive, minimal clean styling

## Stage 3 — Internal REST API
- [ ] `POST /api/journal/upload` — multipart endpoint (no auth — accessible via Tailscale only)
- [ ] `GET /api/journal/status/{job_id}` — polling endpoint
- [ ] `GET /health` — liveness check
- [ ] Verify: upload a test file and check response

## Stage 4 — Media Processing Pipeline
- [ ] File cache step — copy uploaded files to Hermes image/video cache
- [ ] EXIF extraction (`extract_photo_metadata()` from travel-journal skill)
- [ ] GPS → country routing (Nominatim reverse geocode → `Travel/<Country>/`)
- [ ] No-GPS fallback: flag for manual country confirmation
- [ ] HEIC → JPEG conversion (pillow_heif for non-Telegram files)
- [ ] Orientation fix (save with `exif[0x0112] = 1`)
- [ ] Verify: process a test JPEG and HEIC file end-to-end

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