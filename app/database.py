from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(os.environ.get("IMAGE2PLUG_DB", "db/jobs.db"))
RESULTS_DIR = Path(os.environ.get("IMAGE2PLUG_RESULTS", "web_results"))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP,
            status TEXT,
            options TEXT,
            input_image TEXT,
            output_dir TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_job(
    job_id: str,
    created_at: datetime,
    status: str,
    options: str,
    input_image: str,
    output_dir: str,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO jobs (id, created_at, status, options, input_image, output_dir) VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, created_at.isoformat(), status, options, input_image, output_dir),
    )
    conn.commit()
    conn.close()


def update_status(job_id: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, created_at, status, options, input_image, output_dir FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "created_at": row[1],
            "status": row[2],
            "options": row[3],
            "input_image": row[4],
            "output_dir": row[5],
        }
    return None


def purge_old_jobs(max_age_hours: int = 24) -> None:
    threshold = datetime.utcnow() - timedelta(hours=max_age_hours)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, output_dir FROM jobs WHERE created_at < ?", (threshold.isoformat(),)
    ).fetchall()
    conn.execute("DELETE FROM jobs WHERE created_at < ?", (threshold.isoformat(),))
    conn.commit()
    conn.close()

    for _id, out_dir in rows:
        try:
            path = Path(out_dir)
            if path.exists():
                for child in path.glob("*"):
                    child.unlink(missing_ok=True)
                path.rmdir()
        except Exception:
            pass
