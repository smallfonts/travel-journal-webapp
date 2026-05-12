"""Travel Journal Web App — FastAPI entry point."""
import uuid, json, os, asyncio, sqlite3, shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from typing import Optional

from app.config import settings
from app.pipeline import (
    extract_metadata, fix_orientation_and_save, gps_to_country,
    format_coordinates, parse_exif_datetime,
)
from app.journal import (
    get_journal_path, get_media_dir, read_journal,
    insert_media_into_journal, insert_ai_image_into_dreamscape,
    update_mochimon_summary, create_journal_entry,
)

app = FastAPI(title="Travel Journal Web App")

# ─── Job Store (SQLite) ───────────────────────────────────────────────────────

JOBS_DB = os.path.join(os.path.dirname(__file__), "jobs.db")

def init_jobs_db():
    with sqlite3.connect(JOBS_DB) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id    TEXT PRIMARY KEY,
                status    TEXT DEFAULT 'pending',
                caption   TEXT,
                date_override TEXT,
                process_now  INTEGER DEFAULT 0,
                created_at   TEXT DEFAULT (datetime('now')),
                files_json   TEXT DEFAULT '[]',
                result_json TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS job_files (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id    TEXT,
                filename  TEXT,
                size      INTEGER,
                ctype     TEXT,
                cache_path TEXT,
                status    TEXT DEFAULT 'pending',
                message   TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)

init_jobs_db()

def create_job(files_info: list, caption: str, date_override: Optional[str], process_now: bool) -> str:
    job_id = str(uuid.uuid4())[:8]
    with sqlite3.connect(JOBS_DB) as db:
        db.execute(
            "INSERT INTO jobs (job_id, caption, date_override, process_now, files_json) VALUES (?, ?, ?, ?, ?)",
            (job_id, caption, date_override, int(process_now), json.dumps([]))
        )
        for fi in files_info:
            db.execute(
                "INSERT INTO job_files (job_id, filename, size, ctype, cache_path) VALUES (?, ?, ?, ?, ?)",
                (job_id, fi["filename"], fi["size"], fi["ctype"], fi["cache_path"])
            )
    return job_id

def get_job(job_id: str) -> Optional[dict]:
    with sqlite3.connect(JOBS_DB) as db:
        db.row_factory = sqlite3.Row
        job = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not job:
            return None
        files = db.execute("SELECT * FROM job_files WHERE job_id = ?", (job_id,)).fetchall()
        return {
            **dict(job),
            "files": [dict(f) for f in files]
        }

def update_job_status(job_id: str, status: str, result_json: str = None):
    with sqlite3.connect(JOBS_DB) as db:
        if result_json:
            db.execute("UPDATE jobs SET status = ?, result_json = ? WHERE job_id = ?", (status, result_json, job_id))
        else:
            db.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))

def update_file_status(job_id: str, filename: str, status: str, message: str):
    with sqlite3.connect(JOBS_DB) as db:
        db.execute(
            "UPDATE job_files SET status = ?, message = ? WHERE job_id = ? AND filename = ?",
            (status, message, job_id, filename)
        )

# ─── HTML Form (inline to avoid Jinja2 dict-hashing bug in hermes-agent venv) ──

UPLOAD_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📸 Travel Journal</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f7f8fa; color: #1a1a2e; min-height: 100vh; padding: 2rem 1rem; }
    .container { max-width: 640px; margin: 0 auto; }
    header { text-align: center; margin-bottom: 2rem; }
    header h1 { font-size: 1.75rem; font-weight: 700; }
    header p { font-size: 0.875rem; color: #6b7280; margin-top: 0.25rem; }
    .card { background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); padding: 1.5rem; margin-bottom: 1rem; }
    label { display: block; font-size: 0.8125rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem; }
    .upload-zone { border: 2px dashed #d1d5db; border-radius: 10px; padding: 2.5rem 1.5rem; text-align: center; cursor: pointer; transition: border-color 0.2s, background 0.2s; margin-bottom: 1rem; }
    .upload-zone:hover, .upload-zone.dragover { border-color: #6366f1; background: #f0f0ff; }
    .upload-zone input[type="file"] { display: none; }
    .upload-zone .icon { font-size: 2rem; margin-bottom: 0.5rem; }
    .upload-zone .text { font-size: 0.9375rem; color: #374151; }
    .upload-zone .text strong { color: #6366f1; }
    .upload-zone .hint { font-size: 0.75rem; color: #9ca3af; margin-top: 0.25rem; }
    .file-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.625rem 0.75rem; background: #f9fafb; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.875rem; }
    .file-item img { width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb; }
    .file-item .info { flex: 1; overflow: hidden; }
    .file-item .name { font-weight: 500; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .file-item .size { font-size: 0.75rem; color: #9ca3af; }
    .file-item .remove { background: none; border: none; color: #9ca3af; font-size: 1.25rem; cursor: pointer; }
    .file-item .remove:hover { color: #ef4444; }
    textarea, input[type="date"] { width: 100%; border: 1px solid #d1d5db; border-radius: 8px; padding: 0.625rem 0.875rem; font-size: 0.9375rem; font-family: inherit; }
    textarea:focus, input[type="date"]:focus { outline: none; border-color: #6366f1; }
    textarea { resize: vertical; min-height: 80px; margin-bottom: 1rem; }
    .row { display: flex; gap: 1rem; align-items: flex-end; margin-bottom: 1rem; }
    .row .field { flex: 1; }
    .checkbox-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; font-size: 0.875rem; color: #4b5563; }
    .checkbox-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: #6366f1; }
    .checkbox-row label { margin-bottom: 0; font-weight: 400; }
    .btn-primary { width: 100%; background: #6366f1; color: #fff; border: none; border-radius: 10px; padding: 0.875rem; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    .btn-primary:hover { background: #4f46e5; }
    .btn-primary:disabled { background: #a5a6f6; cursor: not-allowed; }
    .options-toggle { background: none; border: none; font-size: 0.8125rem; color: #6366f1; cursor: pointer; padding: 0; margin-bottom: 0.75rem; }
    #options-panel { display: none; margin-bottom: 1rem; }
    #options-panel.open { display: block; }
    #status-panel { display: none; margin-top: 1rem; }
    #status-panel.visible { display: block; }
    .status-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: #f9fafb; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.875rem; }
    .status-item .emoji { font-size: 1.1rem; }
    .status-item .msg { flex: 1; color: #374151; }
    .status-item .ok { color: #10b981; font-weight: 600; }
    .status-item .err { color: #ef4444; font-weight: 600; }
    .status-item .pending { color: #f59e0b; font-weight: 600; }
    .result-links { text-align: center; margin-top: 1.5rem; padding: 1rem; background: #f0fdf4; border-radius: 10px; }
    .result-links a { color: #6366f1; text-decoration: none; font-weight: 600; }
    .btn-secondary { display: inline-block; margin-top: 1rem; background: #6366f1; color: #fff; border: none; border-radius: 8px; padding: 0.625rem 1.5rem; font-size: 0.9375rem; font-weight: 600; cursor: pointer; text-decoration: none; }
    .btn-secondary:hover { background: #4f46e5; }
    #dream-scape-img { display: none; max-width: 100%; border-radius: 8px; margin-top: 0.75rem; }
    .job-id-line { text-align: center; font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem; }
    .job-id-line code { background: #f3f4f6; padding: 0.125rem 0.4rem; border-radius: 4px; font-size: 0.7rem; }
  </style>
</head>
<body>
<div class="container">
  <header>
    <h1>📸 Travel Journal</h1>
    <p>Upload photos and videos — they'll be filed into your Obsidian vault automatically.</p>
  </header>

  <form id="upload-form" enctype="multipart/form-data">
    <div class="card">
      <div class="upload-zone" id="upload-zone">
        <div class="icon">📷</div>
        <div class="text">Drag & drop photos or videos here, or <strong>browse files</strong></div>
        <div class="hint">JPEG, PNG, WebP, HEIC, MOV, MP4 — max 50 MB each</div>
        <input type="file" name="files" id="file-input" multiple accept="image/*,video/*">
      </div>
      <div id="file-list"></div>
    </div>

    <div class="card">
      <label for="caption">Caption / Description</label>
      <textarea name="caption" id="caption" placeholder="What were you up to? (optional — EXIF data fills in the rest)"></textarea>

      <button type="button" class="options-toggle" id="options-toggle">⚙️ Show more options</button>
      <div id="options-panel">
        <div class="row">
          <div class="field">
            <label for="date_override">Date override</label>
            <input type="date" name="date_override" id="date_override">
          </div>
        </div>
      </div>

      <div class="checkbox-row">
        <input type="checkbox" name="process_now" id="process_now" value="1">
        <label for="process_now">Generate AI DreamScape image (pixel art via MiniMax)</label>
      </div>
    </div>

    <button type="submit" class="btn-primary" id="submit-btn">Upload & Process</button>
  </form>

  <div id="status-panel">
    <div class="card" id="status-card">
      <div id="status-items"></div>
      <div class="job-id-line" id="job-id-line"></div>
    </div>
    <div class="result-links" id="result-links" style="display:none">
      <p>✅ Done!</p>
      <a id="journal-link" href="#" target="_blank">Open journal entry →</a><br>
      <img id="dream-scape-img" src="">
      <br>
      <button class="btn-secondary" onclick="resetForm()">Upload more</button>
    </div>
  </div>
</div>

<script>
  const zone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');
  const fileList = document.getElementById('file-list');
  const form = document.getElementById('upload-form');
  const statusPanel = document.getElementById('status-panel');
  const statusItems = document.getElementById('status-items');
  const submitBtn = document.getElementById('submit-btn');
  const optionsToggle = document.getElementById('options-toggle');
  const optionsPanel = document.getElementById('options-panel');

  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragover'); fileInput.files = e.dataTransfer.files; previewFiles(); });
  fileInput.addEventListener('change', previewFiles);

  optionsToggle.addEventListener('click', () => {
    optionsPanel.classList.toggle('open');
    optionsToggle.textContent = optionsPanel.classList.contains('open') ? '⚙️ Hide options' : '⚙️ Show more options';
  });

  const filesData = [];

  function previewFiles() {
    fileList.innerHTML = '';
    filesData.length = 0;
    for (const file of fileInput.files) {
      filesData.push(file);
      const el = document.createElement('div');
      el.className = 'file-item';
      if (file.type.startsWith('image/')) {
        const url = URL.createObjectURL(file);
        el.innerHTML = `<img src="${url}"><div class="info"><div class="name">${escHtml(file.name)}</div><div class="size">${fmtSize(file.size)}</div></div><button class="remove" type="button" data-index="${filesData.length - 1}">✕</button>`;
      } else {
        el.innerHTML = `<span style="font-size:1.5rem">🎬</span><div class="info"><div class="name">${escHtml(file.name)}</div><div class="size">${fmtSize(file.size)}</div></div><button class="remove" type="button" data-index="${filesData.length - 1}">✕</button>`;
      }
      fileList.appendChild(el);
    }
    document.querySelectorAll('.file-item .remove').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.index);
        filesData.splice(idx, 1);
        const dt = new DataTransfer();
        filesData.forEach(f => dt.items.add(f));
        fileInput.files = dt.files;
        previewFiles();
      });
    });
  }

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/1048576).toFixed(1) + ' MB';
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function pollStatus(jobId) {
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`/api/journal/status/${jobId}`);
        const data = await r.json();
        renderStatus(data);
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(interval);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Upload & Process';
          if (data.status === 'done') showResults(data);
        }
      } catch(err) {
        clearInterval(interval);
        statusItems.innerHTML += `<div class="status-item"><span class="emoji">❌</span><span class="msg err">Poll failed: ${escHtml(err.message)}</span></div>`;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Upload & Process';
      }
    }, 2000);
  }

  function renderStatus(data) {
    const statusMap = { pending: '⏳', processing: '🔄', done: '✅', error: '❌' };
    const labelMap = { pending: 'Pending', processing: 'Processing…', done: 'Done', error: 'Error' };
    let html = `<div class="status-item"><span class="emoji">${statusMap[data.status] || '❓'}</span><span class="msg ${data.status === 'error' ? 'err' : ''}">Job ${labelMap[data.status] || data.status}</span></div>`;
    for (const f of (data.files || [])) {
      const s = f.status || 'pending';
      html += `<div class="status-item"><span class="emoji">${statusMap[s] || '❓'}</span><span class="msg ${s === 'error' ? 'err' : s === 'done' ? 'ok' : 'pending'}">${escHtml(f.filename)} — ${f.message || labelMap[s] || s}</span></div>`;
    }
    statusItems.innerHTML = html;
    document.getElementById('job-id-line').innerHTML = `Job ID: <code>${jobId}</code> &nbsp;·&nbsp; <a href="/api/journal/status/${jobId}" target="_blank" style="color:#6366f1;font-size:0.7rem">JSON</a>`;
  }

  function showResults(data) {
    const rl = document.getElementById('result-links');
    const jl = document.getElementById('journal-link');
    if (data.result) {
      jl.href = data.result.journal_url || '#';
      jl.textContent = data.result.journal_file || 'Open journal entry';
      const dsi = document.getElementById('dream-scape-img');
      if (data.result.dream_scape_url) { dsi.src = data.result.dream_scape_url; dsi.style.display = 'block'; }
      else { dsi.style.display = 'none'; }
    }
    rl.style.display = 'block';
  }

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (filesData.length === 0) { alert('Please select at least one file.'); return; }
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';
    statusPanel.classList.add('visible');
    statusItems.innerHTML = '<div class="status-item"><span class="emoji">⏳</span><span class="msg">Creating job...</span></div>';
    document.getElementById('result-links').style.display = 'none';
    const data = new FormData(form);
    filesData.forEach(f => data.append('files', f));
    try {
      const res = await fetch('/api/journal/upload', { method: 'POST', body: data });
      const json = await res.json();
      if (json.job_id) {
        statusItems.innerHTML = '<div class="status-item"><span class="emoji">🔄</span><span class="msg">Processing started — polling status...</span></div>';
        submitBtn.textContent = 'Processing...';
        document.getElementById('job-id-line').innerHTML = `Job ID: <code>${json.job_id}</code> &nbsp;·&nbsp; <a href="/api/journal/status/${json.job_id}" target="_blank" style="color:#6366f1;font-size:0.7rem">JSON</a>`;
        pollStatus(json.job_id);
      } else {
        statusItems.innerHTML = `<div class="status-item"><span class="emoji">❌</span><span class="msg err">${escHtml(json.message || 'Unknown error')}</span></div>`;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Upload & Process';
      }
    } catch(err) {
      statusItems.innerHTML = `<div class="status-item"><span class="emoji">❌</span><span class="msg err">${escHtml(err.message)}</span></div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Upload & Process';
    }
  });

  function resetForm() {
    form.reset();
    filesData.length = 0;
    fileList.innerHTML = '';
    statusPanel.classList.remove('visible');
    document.getElementById('dream-scape-img').style.display = 'none';
    document.getElementById('result-links').style.display = 'none';
    document.getElementById('job-id-line').innerHTML = '';
  }
</script>
</body>
</html>"""

# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=UPLOAD_FORM)

@app.get("/health")
async def health():
    return {"status": "ok", "vault": settings.VAULT_PATH}

# ─── Internal REST API ──────────────────────────────────────────────────────

@app.post("/api/journal/upload")
async def api_upload(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = [],
    caption: Optional[str] = Form(""),
    date_override: Optional[str] = Form(None),
    process_now: Optional[str] = Form(None),
):
    """
    Stage 3: Create a job, save files to cache, return job_id immediately.
    Real pipeline processing (EXIF → journal → AI) wires in at Stage 4.
    """
    if not files:
        return {"status": "error", "message": "No files provided"}

    # Save files to cache dirs and collect info
    files_info = []
    for f in files:
        content = await f.read()
        cache_dir = settings.CACHE_IMAGES if f.content_type.startswith("image/") else settings.CACHE_VIDEOS
        out_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
        out_path = os.path.join(cache_dir, out_name)
        with open(out_path, "wb") as out:
            out.write(content)
        files_info.append({
            "filename": f.filename,
            "size": len(content),
            "ctype": f.content_type,
            "cache_path": out_path,
        })

    # Create job
    job_id = create_job(
        files_info=files_info,
        caption=caption or "",
        date_override=date_override,
        process_now=bool(process_now),
    )

    update_job_status(job_id, "processing")

    # ─── Stage 4+5 Pipeline (runs async in background) ───────────────────────
    async def run_pipeline():
        journal_entries = []  # {date, country, vault_path, meta, filename, time_str}

        for fi in files_info:
            update_file_status(job_id, fi["filename"], "processing", "Extracting metadata...")

            meta = extract_metadata(fi["cache_path"])

            # Update file status with metadata findings
            meta_summary = meta["message"]
            if meta["country"]:
                meta_summary += f" | {meta['country']}"
            if meta["location_string"]:
                meta_summary += f" | {meta['location_string']}"
            if meta["datetime"]:
                meta_summary += f" | {meta['datetime']}"

            update_file_status(job_id, fi["filename"], "processing", meta_summary)

            # Determine date
            date_str = None
            time_str = None
            if meta["datetime"]:
                dt = datetime.strptime(meta["datetime"], "%Y-%m-%d %H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            elif date_override:
                date_str = date_override
                time_str = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
            else:
                date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
                time_str = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")

            # Determine country
            country = meta["country"]
            if not country:
                if meta["no_gps"]:
                    update_file_status(job_id, fi["filename"], "done",
                        f"No GPS — manual location confirmation needed. Date: {date_str}")
                else:
                    update_file_status(job_id, fi["filename"], "done",
                        f"Country unknown — please confirm. Date: {date_str}")
                continue

            safe_country = country.replace(" ", "-")
            media_dir = get_media_dir(settings.VAULT_PATH, safe_country)
            os.makedirs(media_dir, exist_ok=True)

            is_video = meta["media_type"] == "video"
            time_suffix = time_str.replace(":", "")
            out_name = f"{date_str}-{time_suffix}-{fi['filename']}"
            out_name = "".join(c if c.isalnum() or c in (".", "-", "_") else "_" for c in out_name)
            vault_dest = os.path.join(media_dir, out_name)

            # Process image (fix orientation) or copy video
            if is_video:
                shutil.copy2(fi["cache_path"], vault_dest)
            else:
                result = fix_orientation_and_save(fi["cache_path"], vault_dest)
                if result["was_rotated"]:
                    update_file_status(job_id, fi["filename"], "processing",
                        f"Photo rotated to correct orientation, saved to {safe_country}/media/")

            update_file_status(job_id, fi["filename"], "processing", "Updating journal entry...")

            # ─── Stage 5: Journal Integration ──────────────────────────────
            journal_path = get_journal_path(settings.VAULT_PATH, safe_country, date_str)

            # Create journal if doesn't exist
            if not os.path.exists(journal_path):
                lat = meta.get("lat") or 0.0
                lon = meta.get("lon") or 0.0
                create_journal_entry(settings.VAULT_PATH, safe_country, date_str,
                                     lat=lat, lon=lon, day_num=1)
                update_file_status(job_id, fi["filename"], "processing",
                    f"Created new journal: Travel/{safe_country}/{date_str} {safe_country}.md")

            # Determine caption
            entry_caption = caption if caption else (meta.get("location_string") or "Travel moment")

            # Insert into journal timeline
            insert_media_into_journal(
                journal_path=journal_path,
                time_str=time_str,
                caption=entry_caption,
                vault_media_path=vault_dest,
                is_video=is_video,
            )

            update_file_status(job_id, fi["filename"], "done",
                f"✅ Saved to Travel/{safe_country}/media/ + journal entry updated")

            journal_entries.append({
                "date":       date_str,
                "country":    safe_country,
                "vault_path": vault_dest,
                "meta":       meta,
                "filename":   fi["filename"],
                "time_str":   time_str,
            })

        # Build result summary
        if journal_entries:
            countries = list(set(e["country"] for e in journal_entries))
            primary = countries[0]
            date_str = journal_entries[0]["date"]
            journal_file = f"{primary}/{date_str} {primary}.md"
            journal_url = f"obsidian://open?vault=WeeksObsidianVault&file=Travel/{journal_file}"
            update_job_status(job_id, "done", json.dumps({
                "journal_file":   journal_file,
                "journal_url":    journal_url,
                "entries_count":  len(journal_entries),
                "countries":      countries,
            }))
        else:
            update_job_status(job_id, "done", json.dumps({
                "journal_file":   None,
                "journal_url":    None,
                "entries_count":  0,
                "countries":      [],
                "message":        "No entries — GPS was missing for all files",
            }))

    background_tasks.add_task(run_pipeline)

    return {"status": "accepted", "job_id": job_id, "message": f"Job created — {len(files)} file(s)"}


@app.get("/api/journal/status/{job_id}")
async def job_status(job_id: str):
    """Poll job status — returns current state + per-file breakdown."""
    job = get_job(job_id)
    if not job:
        return {"status": "error", "message": f"Job {job_id} not found"}
    result = json.loads(job["result_json"]) if job["result_json"] else None
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "caption": job["caption"],
        "date_override": job["date_override"],
        "process_now": bool(job["process_now"]),
        "created_at": job["created_at"],
        "files": [
            {
                "filename": f["filename"],
                "size": f["size"],
                "status": f["status"],
                "message": f["message"],
            }
            for f in job["files"]
        ],
        "result": result,
    }

# Keep the old /upload for backward compat (Stage 2-style form)
@app.post("/upload")
async def upload(
    files: list[UploadFile] = [],
    caption: Optional[str] = Form(""),
    date_override: Optional[str] = Form(None),
    process_now: Optional[str] = Form(None),
):
    if not files:
        return {"status": "error", "message": "No files provided"}
    saved = []
    for f in files:
        content = await f.read()
        cache_dir = settings.CACHE_IMAGES if f.content_type.startswith("image/") else settings.CACHE_VIDEOS
        out_path = os.path.join(cache_dir, f"stage2_{f.filename}")
        with open(out_path, "wb") as out:
            out.write(content)
        saved.append({"filename": f.filename, "size": len(content), "ok": True, "message": f"{f.filename} received (Stage 2 stub)"})
    return {"status": "done", "files": saved, "journal_file": "Stage 4 — not wired yet", "journal_url": "#"}

# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    print(f"Travel Journal Web App starting...")
    print(f"  Local:     http://127.0.0.1:8001")
    print(f"  Tailscale: http://100.85.28.35:8001")
    print(f"  Vault:     {settings.VAULT_PATH}")
    print(f"  Jobs DB:   {JOBS_DB}")