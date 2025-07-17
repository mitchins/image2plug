from __future__ import annotations

import os
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from . import database


app = FastAPI(title="image2plug web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure paths exist
RESULTS_DIR = database.RESULTS_DIR
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
database.init_db()

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(index_path.read_text())


@app.post("/jobs/upload")
async def upload_job(
    image: UploadFile = File(...),
    smooth: bool = Form(False),
    measure_error: bool = Form(False),
    border_mode: str = Form("tight"),
):
    if border_mode not in {"tight", "inside", "outside"}:
        raise HTTPException(status_code=400, detail="invalid border mode")
    database.purge_old_jobs()

    job_id = str(uuid.uuid4())
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    image_path = job_dir / image.filename
    with open(image_path, "wb") as f:
        f.write(await image.read())

    opts = {
        "smooth": smooth,
        "measure_error": measure_error,
        "border_mode": border_mode,
    }
    database.add_job(
        job_id,
        datetime.utcnow(),
        "queued",
        json.dumps(opts),
        str(image_path),
        str(job_dir),
    )

    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": job_id, "status": job["status"]}


@app.get("/jobs/{job_id}/results")
def job_results(job_id: str):
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    output_dir = Path(job["output_dir"])
    index = output_dir / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="result not ready")
    return FileResponse(index)
