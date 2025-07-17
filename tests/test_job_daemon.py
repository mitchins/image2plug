import sqlite3
import subprocess
from pathlib import Path

from job_store import JobStore


def test_daemon_processes_job(tmp_path):
    db = tmp_path / "jobs.db"
    out_root = tmp_path / "out"
    store = JobStore(db)
    img = Path("assets/reference_image_us_letter.png")
    job_id = store.enqueue(img)

    subprocess.run(
        ["python", "job_daemon.py", "--db", str(db), "--output-root", str(out_root), "--once"],
        check=True,
    )

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT status, completed_at, output_dir FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row[0] == "complete"
    assert row[1] is not None
    assert (out_root / row[2]).exists()
