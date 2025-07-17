import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import create_app


def test_upload_and_result(tmp_path):
    app = create_app(testing=True, base_dir=tmp_path)
    client = TestClient(app)

    img_path = Path("assets/reference_image_us_letter.png")
    with open(img_path, "rb") as f:
        resp = client.post(
            "/upload",
            files={"file": ("img.png", f, "image/png")},
            data={"smooth": "true", "measure_error": "true", "border_mode": "tight"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    job_id = resp.headers["location"].split("/")[-1]

    status = client.get(f"/jobs/{job_id}/status").json()
    assert status["status"] == "completed"

    res_page = client.get(f"/results/{job_id}")
    assert res_page.status_code == 200
    assert "Corrected Image" in res_page.text


def test_cleanup(tmp_path):
    from app.main import init_db, cleanup_old_jobs

    base = tmp_path
    db_path = base / "jobs.db"
    results_dir = base / "results"
    results_dir.mkdir(exist_ok=True)
    db = init_db(db_path)
    old_dir = results_dir / "old"
    old_dir.mkdir(parents=True, exist_ok=True)
    import time

    db.execute(
        "INSERT INTO jobs (id, status, options, created_at, result_dir) VALUES ('old', 'completed', '{}', ?, ?)",
        (time.time() - 90000, str(old_dir)),
    )
    db.commit()
    cleanup_old_jobs(db, max_age=3600)
    assert not old_dir.exists()
    row = db.execute("SELECT * FROM jobs WHERE id='old'").fetchone()
    assert row is None
