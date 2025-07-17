import os
from pathlib import Path
from importlib import reload
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def setup_app(tmp_path):
    os.environ["IMAGE2PLUG_DB"] = str(tmp_path / "jobs.db")
    os.environ["IMAGE2PLUG_RESULTS"] = str(tmp_path / "results")
    import app.database as db

    reload(db)
    db.init_db()
    import app.main as main

    reload(main)
    return main, db, TestClient(main.app)


def test_upload_endpoint(tmp_path, monkeypatch):
    main, db, client = setup_app(tmp_path)

    def dummy(job_id, image_path, output_dir, smooth, measure_error, border_mode):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text("ok")
        db.update_status(job_id, "finished")

    monkeypatch.setattr(main, "process_job", dummy)

    with open("assets/reference_image_us_letter.png", "rb") as f:
        resp = client.post(
            "/jobs/upload",
            files={"image": ("us.png", f, "image/png")},
            data={"smooth": "true", "measure_error": "false", "border_mode": "tight"},
        )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    status = client.get(f"/jobs/{job_id}")
    assert status.json()["status"] == "finished"

    r = client.get(f"/jobs/{job_id}/results")
    assert r.status_code == 200


def test_purge_old_jobs(tmp_path):
    main, db, client = setup_app(tmp_path)
    old_dir = Path(os.environ["IMAGE2PLUG_RESULTS"]) / "old"
    old_dir.mkdir(parents=True)
    (old_dir / "dummy.txt").write_text("x")
    db.add_job(
        "old",
        datetime.utcnow() - timedelta(hours=25),
        "finished",
        "{}",
        "img",
        str(old_dir),
    )
    db.purge_old_jobs()
    assert db.get_job("old") is None
    assert not old_dir.exists()
