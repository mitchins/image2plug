from pathlib import Path
from unittest import mock
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_and_status(tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"fake")

    with mock.patch("lib.jobs.run_job", return_value={"ok": True}):
        resp = client.post(
            "/upload",
            files={"image": ("img.png", img.read_bytes(), "image/png")},
            data={"smooth": "false", "measure_error": "false", "border_mode": "tight"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        status = client.get(f"/status/{job_id}")
        assert status.status_code == 200

def test_purge_old_jobs(tmp_path):
    from db.models import SessionLocal, Job, purge_old_jobs
    session = SessionLocal()
    job = Job(id="old", created_at=datetime.utcnow() - timedelta(hours=25),
              status="finished", options="{}", input_path="", output_dir=str(tmp_path))
    session.add(job)
    session.commit()

    purge_old_jobs(session)
    remaining = session.query(Job).filter(Job.id == "old").first()
    session.close()
    assert remaining is None

