"""Travel Journal Web App — FastAPI entry point."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.config import settings

app = FastAPI(title="Travel Journal Web App")

# ─── Routes (placeholder stubs for now) ────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    """Web upload form."""
    return "<h1>Travel Journal Web App</h1><p>Coming soon...</p>"

@app.get("/health")
async def health():
    """Liveness check."""
    return {"status": "ok"}

@app.post("/upload")
async def upload():
    """Handle file upload from web form."""
    return {"message": "Not implemented yet"}

@app.post("/api/journal/upload")
async def api_upload():
    """Internal REST API for Hermes/cron integration."""
    return {"message": "Not implemented yet"}

@app.get("/api/journal/status/{job_id}")
async def job_status(job_id: str):
    """Poll job status."""
    return {"job_id": job_id, "status": "not_found"}

# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    print(f"Travel Journal Web App starting...")
    print(f"  Vault: {settings.VAULT_PATH}")
    print(f"  Image cache: {settings.CACHE_IMAGES}")
    print(f"  Video cache: {settings.CACHE_VIDEOS}")
    print(f"  Template: {settings.template_path}")