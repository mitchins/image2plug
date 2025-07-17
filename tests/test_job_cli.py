import sqlite3
import subprocess
from pathlib import Path

from job_store import JobStore


def test_cli_enqueue(tmp_path):
    db = tmp_path / "jobs.db"
    img = tmp_path / "img.txt"
    img.write_text("x")
    res = subprocess.run(
        ["python", "job_cli.py", str(img), "--db", str(db)], capture_output=True, text=True, check=True
    )
    job_id = res.stdout.strip()
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row[0] == "pending"
