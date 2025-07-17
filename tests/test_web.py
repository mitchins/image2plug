from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
from fastapi.testclient import TestClient
import app.main as app_module
from app.main import app, purge_old_jobs

client = TestClient(app)


def test_upload_endpoint(monkeypatch, tmp_path):
    def fake_run(image, out_dir, opts):
        (Path(out_dir) / "index.html").write_text("done")

    monkeypatch.setattr("app.pipeline.run_workflow", fake_run)

    image_path = Path("assets/aruco_marker_30mm.png")
    with image_path.open("rb") as f:
        resp = client.post(
            "/upload",
            files={"image": (image_path.name, f, "image/png")},
            data={"smooth": "false", "measure_error": "false", "border_mode": "tight"},
        )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    status = client.get(f"/status/{job_id}")
    assert status.json()["status"] in {"queued", "processing", "done"}


def test_purge_old_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    monkeypatch.setattr(app_module, "RESULTS_DIR", tmp_path / "jobs")
    app_module.RESULTS_DIR.mkdir()
    app_module.init_db()
    now = datetime.utcnow() - timedelta(hours=25)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO jobs (id, status, created_at, options, result_dir) VALUES ('old', 'done', ?, '{}', ?)",
        (now.isoformat(), str(tmp_path / "old")),
    )
    conn.commit()
    conn.close()
    (tmp_path / "old").mkdir()
    purge_old_jobs()
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    assert row == 0
