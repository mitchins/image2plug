import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib
import uuid


class JobStore:
    """Simple SQLite backed job queue."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    image_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT
                )
                """
            )

    def _output_dir(self, job_id: str) -> str:
        return hashlib.sha256(job_id.encode()).hexdigest()[:16]

    def enqueue(self, image_path: Path) -> str:
        job_id = uuid.uuid4().hex
        output_dir = self._output_dir(job_id)
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                (job_id, str(image_path), output_dir, "pending", now, None, None),
            )
        return job_id

    def fetch_next(self):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='pending' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE jobs SET status='running' WHERE id=?", (row["id"],)
            )
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            return dict(row)

    def complete(self, job_id: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='complete', completed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), job_id),
            )

    def fail(self, job_id: str, error: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='error', completed_at=?, error=? WHERE id=?",
                (datetime.utcnow().isoformat(), error, job_id),
            )

    def get(self, job_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None
