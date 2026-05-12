"""Travel Journal Web App — FastAPI entry point."""
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse
from typing import Optional
import os

from app.config import settings

app = FastAPI(title="Travel Journal Web App")

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
    .result-links { text-align: center; margin-top: 1.5rem; padding: 1rem; background: #f0fdf4; border-radius: 10px; }
    .result-links a { color: #6366f1; text-decoration: none; font-weight: 600; }
    .btn-secondary { display: inline-block; margin-top: 1rem; background: #6366f1; color: #fff; border: none; border-radius: 8px; padding: 0.625rem 1.5rem; font-size: 0.9375rem; font-weight: 600; cursor: pointer; text-decoration: none; }
    .btn-secondary:hover { background: #4f46e5; }
    #dream-scape-img { display: none; max-width: 100%; border-radius: 8px; margin-top: 0.75rem; }
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

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (filesData.length === 0) { alert('Please select at least one file.'); return; }
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing...';
    statusPanel.classList.add('visible');
    statusItems.innerHTML = '<div class="status-item"><span class="emoji">⏳</span><span class="msg">Uploading and processing...</span></div>';
    const data = new FormData(form);
    filesData.forEach(f => data.append('files', f));
    try {
      const res = await fetch('/upload', { method: 'POST', body: data });
      const json = await res.json();
      if (json.status === 'done') {
        statusItems.innerHTML = '';
        (json.files || []).forEach(f => {
          const item = document.createElement('div');
          item.className = 'status-item';
          item.innerHTML = `<span class="emoji">${f.ok ? '✅' : '❌'}</span><span class="msg ${f.ok ? 'ok' : 'err'}">${escHtml(f.message)}</span>`;
          statusItems.appendChild(item);
        });
        const rl = document.getElementById('result-links');
        const jl = document.getElementById('journal-link');
        jl.href = json.journal_url || '#';
        jl.textContent = json.journal_file || 'Open journal entry';
        const dsi = document.getElementById('dream-scape-img');
        if (json.dream_scape_url) { dsi.src = json.dream_scape_url; dsi.style.display = 'block'; }
        else { dsi.style.display = 'none'; }
        rl.style.display = 'block';
      } else {
        statusItems.innerHTML = `<div class="status-item"><span class="emoji">❌</span><span class="msg err">${escHtml(json.message || 'Unknown error')}</span></div>`;
      }
    } catch(err) {
      statusItems.innerHTML = `<div class="status-item"><span class="emoji">❌</span><span class="msg err">${escHtml(err.message)}</span></div>`;
    }
    submitBtn.disabled = false;
    submitBtn.textContent = 'Upload & Process';
  });

  function resetForm() {
    form.reset();
    filesData.length = 0;
    fileList.innerHTML = '';
    statusPanel.classList.remove('visible');
    document.getElementById('dream-scape-img').style.display = 'none';
  }
</script>
</body>
</html>"""

# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    """Web upload form."""
    return HTMLResponse(content=UPLOAD_FORM)


@app.get("/health")
async def health():
    """Liveness check."""
    return {"status": "ok", "vault": settings.VAULT_PATH}


@app.post("/upload")
async def upload(
    files: list[UploadFile],
    caption: Optional[str] = Form(""),
    date_override: Optional[str] = Form(None),
    process_now: Optional[str] = Form(None),
):
    """
    Handle file upload from web form.
    Full pipeline processing (EXIF → journal → AI image) is wired up in Stage 4–6.
    Stage 2 just validates the upload and returns a stub response.
    """
    if not files:
        return {"status": "error", "message": "No files provided"}

    saved = []
    for f in files:
        content = await f.read()
        cache_dir = settings.CACHE_IMAGES if f.content_type.startswith("image/") else settings.CACHE_VIDEOS
        out_path = os.path.join(cache_dir, f"stage2_{f.filename}")
        with open(out_path, "wb") as out:
            out.write(content)
        saved.append({"filename": f.filename, "size": len(content), "ok": True, "message": f"{f.filename} received — pipeline not yet wired (Stage 2 stub)"})

    return {
        "status": "done",
        "message": f"Stage 2: {len(saved)} file(s) received. Pipeline comes in Stage 4.",
        "files": saved,
        "journal_file": "Stage 4 — not wired yet",
        "journal_url": "#",
    }


@app.post("/api/journal/upload")
async def api_upload():
    """Internal REST API — stub."""
    return {"message": "Not implemented yet (Stage 3)"}


@app.get("/api/journal/status/{job_id}")
async def job_status(job_id: str):
    """Poll job status — stub."""
    return {"job_id": job_id, "status": "not_found"}


# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    print(f"Travel Journal Web App starting...")
    print(f"  Vault: {settings.VAULT_PATH}")
    print(f"  Image cache: {settings.CACHE_IMAGES}")
    print(f"  Video cache: {settings.CACHE_VIDEOS}")