"""
SQLite-based job store with multi-process safety and comprehensive operations.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import json

from .models import Job, JobStatus


class JobStore:
    """
    Multi-process safe SQLite job store.
    
    Features:
    - WAL mode for better concurrency
    - Connection timeouts and retries
    - Job lifecycle management
    - Auto-purging of old jobs
    """
    
    DEFAULT_TIMEOUT = 30.0
    
    def __init__(self, db_path: Path, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize job store.
        
        Args:
            db_path: Path to SQLite database file
            timeout: Database connection timeout in seconds
        """
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create database connection with optimal settings."""
        conn = sqlite3.connect(
            self.db_path, 
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        return conn

    def _init_db(self):
        """Initialize database schema."""
        with self._connect() as conn:
            # Create jobs table with enhanced schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    image_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)")

    def _generate_output_dir(self, job_id: str) -> str:
        """Use job ID directly as output directory for security."""
        return job_id

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job object."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else None
        
        return Job(
            id=row["id"],
            image_path=Path(row["image_path"]),
            output_dir=Path(row["output_dir"]),
            status=JobStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"],
            metadata=metadata
        )

    def create_job(self, image_path: Path, metadata: Optional[dict] = None) -> str:
        """
        Create a new job in the queue.
        
        Args:
            image_path: Path to input image
            metadata: Optional job metadata
            
        Returns:
            Job ID
        """
        job_id = uuid.uuid4().hex
        output_dir = self._generate_output_dir(job_id)
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, image_path, output_dir, status, created_at, 
                    started_at, completed_at, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, str(image_path), output_dir, JobStatus.PENDING.value,
                now, None, None, None, metadata_json
            ))
        
        self.logger.info(f"Created job {job_id} for image {image_path}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job object or None if not found
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            
            return self._row_to_job(row) if row else None

    def fetch_next_job(self) -> Optional[Job]:
        """
        Atomically fetch and mark the next pending job as running.
        
        Returns:
            Next job to process or None if queue is empty
        """
        with self._connect() as conn:
            # Begin immediate transaction for atomicity
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                # Find oldest pending job
                row = conn.execute("""
                    SELECT * FROM jobs 
                    WHERE status = ? 
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (JobStatus.PENDING.value,)).fetchone()
                
                if not row:
                    conn.rollback()
                    return None
                
                job_id = row["id"]
                now = datetime.utcnow().isoformat()
                
                # Mark as running
                conn.execute("""
                    UPDATE jobs 
                    SET status = ?, started_at = ? 
                    WHERE id = ?
                """, (JobStatus.RUNNING.value, now, job_id))
                
                # Fetch updated row
                updated_row = conn.execute(
                    "SELECT * FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                
                conn.commit()
                job = self._row_to_job(updated_row)
                self.logger.info(f"Fetched job {job_id} for processing")
                return job
                
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to fetch next job: {e}")
                raise

    def complete_job(self, job_id: str) -> bool:
        """
        Mark job as completed successfully.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was updated, False if not found
        """
        now = datetime.utcnow().isoformat()
        
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE jobs 
                SET status = ?, completed_at = ? 
                WHERE id = ? AND status = ?
            """, (JobStatus.COMPLETED.value, now, job_id, JobStatus.RUNNING.value))
            
            updated = cursor.rowcount > 0
            if updated:
                self.logger.info(f"Completed job {job_id}")
            else:
                self.logger.warning(f"Could not complete job {job_id} - not found or not running")
            
            return updated

    def fail_job(self, job_id: str, error_message: str) -> bool:
        """
        Mark job as failed with error message.
        
        Args:
            job_id: Job identifier
            error_message: Error description
            
        Returns:
            True if job was updated, False if not found
        """
        now = datetime.utcnow().isoformat()
        
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE jobs 
                SET status = ?, completed_at = ?, error_message = ? 
                WHERE id = ? AND status = ?
            """, (JobStatus.FAILED.value, now, error_message, job_id, JobStatus.RUNNING.value))
            
            updated = cursor.rowcount > 0
            if updated:
                self.logger.error(f"Failed job {job_id}: {error_message}")
            else:
                self.logger.warning(f"Could not fail job {job_id} - not found or not running")
            
            return updated

    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[Job]:
        """
        List jobs with optional status filter.
        
        Args:
            status: Filter by job status (optional)
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs ordered by creation time (newest first)
        """
        with self._connect() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM jobs 
                    WHERE status = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (status.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM jobs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
            
            return [self._row_to_job(row) for row in rows]

    def get_stats(self) -> dict:
        """
        Get job queue statistics.
        
        Returns:
            Dictionary with job counts by status
        """
        with self._connect() as conn:
            stats = {}
            for status in JobStatus:
                count = conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status = ?", 
                    (status.value,)
                ).fetchone()[0]
                stats[status.value] = count
                
            stats["total"] = sum(stats.values())
            return stats

    def purge_old_jobs(self, older_than_days: int = 30) -> int:
        """
        Remove completed and failed jobs older than specified days.
        
        Args:
            older_than_days: Remove jobs older than this many days
            
        Returns:
            Number of jobs purged
        """
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        cutoff_iso = cutoff.isoformat()
        
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM jobs 
                WHERE completed_at < ? 
                AND status IN (?, ?)
            """, (cutoff_iso, JobStatus.COMPLETED.value, JobStatus.FAILED.value))
            
            purged_count = cursor.rowcount
            if purged_count > 0:
                self.logger.info(f"Purged {purged_count} old jobs")
            
            return purged_count