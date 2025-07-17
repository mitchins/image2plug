from pathlib import Path
from job_store import JobStore


def test_enqueue_and_fetch(tmp_path):
    db = tmp_path / "jobs.db"
    store = JobStore(db)
    img = tmp_path / "img.txt"
    img.write_text("x")
    job_id = store.enqueue(img)
    assert job_id

    job = store.fetch_next()
    assert job["id"] == job_id
    assert job["status"] == "running"

    store.complete(job_id)
    info = store.get(job_id)
    assert info["status"] == "complete"
    assert info["completed_at"] is not None
