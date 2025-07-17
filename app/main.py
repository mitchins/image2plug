import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline

DB_PATH = Path(os.getenv("IMAGE2PLUG_DB", "db/jobs.db"))
RESULTS_DIR = Path(os.getenv("IMAGE2PLUG_RESULTS", "jobs"))
RESULTS_DIR.mkdir(exist_ok=True)
DB_PATH.parent.mkdir(exist_ok=True)

app = FastAPI(title="image2plug Web")


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT,
            created_at TEXT,
            options TEXT,
            result_dir TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


@app.on_event("startup")
def startup_event() -> None:
    purge_old_jobs()


def add_job(job_id: str, status: str, options: dict, result_dir: Path) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO jobs (id, status, created_at, options, result_dir) VALUES (?, ?, ?, ?, ?)",
        (
            job_id,
            status,
            datetime.utcnow().isoformat(),
            json.dumps(options),
            str(result_dir),
        ),
    )
    conn.commit()
    conn.close()


def update_job(job_id: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute(
        "SELECT id, status, created_at, options, result_dir FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "created_at": row[2],
        "options": json.loads(row[3]),
        "result_dir": row[4],
    }


def purge_old_jobs(hours: int = 24) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute("SELECT id, result_dir, created_at FROM jobs").fetchall()
    to_delete = [r for r in rows if datetime.fromisoformat(r[2]) < cutoff]
    for job_id, result_dir, _ in to_delete:
        try:
            Path(result_dir).unlink(missing_ok=True)
            shutil.rmtree(result_dir, ignore_errors=True)
        except Exception:
            pass
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    smooth: bool = Form(False),
    measure_error: bool = Form(False),
    border_mode: str = Form("tight"),
    turnstile_token: str = Form(None),
):
    # TODO: verify turnstile_token when configured
    job_id = str(uuid.uuid4())
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    img_path = job_dir / image.filename
    with img_path.open("wb") as f:
        f.write(await image.read())
    options = {
        "smooth": smooth,
        "measure_error": measure_error,
        "border_mode": border_mode,
    }
    add_job(job_id, "queued", options, job_dir)
    background_tasks.add_task(run_job, job_id, img_path, options, job_dir)
    return {"job_id": job_id}


def run_job(job_id: str, image_path: Path, options: dict, job_dir: Path) -> None:
    update_job(job_id, "processing")
    try:
        pipeline.run_workflow(image_path, job_dir, options)
        update_job(job_id, "done")
    except Exception:
        update_job(job_id, "failed")
        raise


@app.get("/status/{job_id}")
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": job["status"]}


@app.get("/results/{job_id}", response_class=HTMLResponse)
async def results(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    index = Path(job["result_dir"]) / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Result not ready")
    return index.read_text()


app.mount("/files", StaticFiles(directory=RESULTS_DIR), name="files")
