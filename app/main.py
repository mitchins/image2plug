import json
import sqlite3
import uuid
import shutil
import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from lib.pipeline import run_pipeline


def _init_paths(base: Optional[Path] = None):
    base_dir = base or Path("data")
    base_dir.mkdir(exist_ok=True)
    db_path = base_dir / "jobs.db"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)
    return base_dir, db_path, results_dir


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT,
            options TEXT,
            created_at REAL,
            completed_at REAL,
            result TEXT,
            result_dir TEXT,
            original_image TEXT
        )
        """
    )
    return conn


def cleanup_old_jobs(conn: sqlite3.Connection, *, max_age: float = 86400.0) -> None:
    cutoff = time.time() - max_age
    rows = conn.execute(
        "SELECT id, result_dir FROM jobs WHERE created_at < ?",
        (cutoff,),
    ).fetchall()
    for row in rows:
        if row["result_dir"]:
            shutil.rmtree(row["result_dir"], ignore_errors=True)
        conn.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
    conn.commit()


def create_app(testing: bool = False, base_dir: Optional[Path] = None) -> FastAPI:
    base_dir, db_path, results_dir = _init_paths(base_dir)
    conn = init_db(db_path)
    cleanup_old_jobs(conn)
    app = FastAPI()
    templates = Jinja2Templates(directory="app/templates")
    app.mount(
        "/results-static", StaticFiles(directory=results_dir), name="results-static"
    )

    executor = None if testing else asyncio.get_event_loop()

    def process(job_id: str, img_path: Path, options: dict, job_dir: Path) -> None:
        try:
            result = run_pipeline(img_path, job_dir, **options)
            conn.execute(
                "UPDATE jobs SET status=?, completed_at=?, result=? WHERE id=?",
                ("completed", time.time(), json.dumps(result), job_id),
            )
        except Exception as e:  # pragma: no cover - capture errors
            conn.execute(
                "UPDATE jobs SET status=?, completed_at=?, result=? WHERE id=?",
                ("error", time.time(), json.dumps({"error": str(e)}), job_id),
            )
        conn.commit()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.post("/upload")
    async def upload(
        request: Request,
        file: UploadFile = File(...),
        smooth: Optional[bool] = Form(False),
        measure_error: Optional[bool] = Form(False),
        border_mode: str = Form("tight"),
    ):
        job_id = str(uuid.uuid4())
        job_dir = results_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        img_path = job_dir / file.filename
        with open(img_path, "wb") as f:
            f.write(await file.read())

        options = {
            "smooth": bool(smooth),
            "measure_error": bool(measure_error),
            "border_mode": border_mode,
        }

        conn.execute(
            "INSERT INTO jobs (id, status, options, created_at, result_dir, original_image) VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                "processing",
                json.dumps(options),
                time.time(),
                str(job_dir),
                str(img_path),
            ),
        )
        conn.commit()

        if testing:
            process(job_id, img_path, options, job_dir)
        else:
            loop = executor
            loop.run_in_executor(None, process, job_id, img_path, options, job_dir)

        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_page(request: Request, job_id: str):
        return templates.TemplateResponse(
            "job.html", {"request": request, "job_id": job_id}
        )

    @app.get("/jobs/{job_id}/status")
    def job_status(job_id: str):
        row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return {"status": "unknown"}
        return {"status": row["status"]}

    @app.get("/results/{job_id}", response_class=HTMLResponse)
    def job_result(request: Request, job_id: str):
        row = conn.execute("SELECT result FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return HTMLResponse("Job not found", status_code=404)
        data = json.loads(row["result"])
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "job_id": job_id,
                "data": data,
            },
        )

    return app


app = create_app()
