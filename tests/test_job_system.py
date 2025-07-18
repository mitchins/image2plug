"""
Tests for the new modular job system.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from job import JobStore, Job, JobStatus, JobDaemon


class TestJobStore:
    """Test the JobStore class."""
    
    def test_create_and_get_job(self, tmp_path):
        """Test job creation and retrieval."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        # Create test image file
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Create job
        job_id = store.create_job(image_path)
        assert job_id is not None
        assert len(job_id) == 32  # UUID hex string
        
        # Retrieve job
        job = store.get_job(job_id)
        assert job is not None
        assert job.id == job_id
        assert job.image_path == image_path
        assert job.status == JobStatus.PENDING
        assert job.created_at is not None
    
    def test_job_metadata(self, tmp_path):
        """Test job creation with metadata."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        metadata = {
            "workflow_options": {
                "proof": True,
                "extrude_height": 15.0,
                "smooth": True
            }
        }
        
        job_id = store.create_job(image_path, metadata)
        job = store.get_job(job_id)
        
        assert job.metadata == metadata
        assert job.metadata["workflow_options"]["proof"] is True
        assert job.metadata["workflow_options"]["extrude_height"] == 15.0
    
    def test_fetch_next_job(self, tmp_path):
        """Test atomic job fetching."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Create multiple jobs
        job_id1 = store.create_job(image_path)
        job_id2 = store.create_job(image_path)
        
        # Fetch first job
        job = store.fetch_next_job()
        assert job is not None
        assert job.id == job_id1
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        
        # Fetch second job
        job = store.fetch_next_job()
        assert job is not None
        assert job.id == job_id2
        assert job.status == JobStatus.RUNNING
        
        # No more jobs
        job = store.fetch_next_job()
        assert job is None
    
    def test_complete_job(self, tmp_path):
        """Test job completion."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        job_id = store.create_job(image_path)
        
        # Fetch and complete job
        job = store.fetch_next_job()
        assert store.complete_job(job_id) is True
        
        # Check job status
        job = store.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.duration_seconds > 0
    
    def test_fail_job(self, tmp_path):
        """Test job failure handling."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        job_id = store.create_job(image_path)
        
        # Fetch and fail job
        job = store.fetch_next_job()
        error_msg = "Test error message"
        assert store.fail_job(job_id, error_msg) is True
        
        # Check job status
        job = store.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_message == error_msg
        assert job.completed_at is not None
    
    def test_list_jobs(self, tmp_path):
        """Test job listing with filters."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Create jobs
        job_id1 = store.create_job(image_path)
        job_id2 = store.create_job(image_path)
        
        # Complete one job
        job = store.fetch_next_job()
        store.complete_job(job.id)
        
        # List all jobs
        all_jobs = store.list_jobs()
        assert len(all_jobs) == 2
        
        # List only pending jobs
        pending_jobs = store.list_jobs(status=JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].status == JobStatus.PENDING
        
        # List only completed jobs
        completed_jobs = store.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed_jobs) == 1
        assert completed_jobs[0].status == JobStatus.COMPLETED
    
    def test_job_stats(self, tmp_path):
        """Test job statistics."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Initially no jobs
        stats = store.get_stats()
        assert stats["total"] == 0
        assert stats["pending"] == 0
        
        # Create jobs
        job_id1 = store.create_job(image_path)
        job_id2 = store.create_job(image_path)
        
        stats = store.get_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 2
        assert stats["running"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        
        # Process one job
        job = store.fetch_next_job()
        store.complete_job(job.id)
        
        stats = store.get_stats()
        assert stats["pending"] == 1
        assert stats["completed"] == 1


class TestJobDaemon:
    """Test the JobDaemon class."""
    
    def test_process_single_job(self, tmp_path):
        """Test single job processing."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Create test processor
        processed_jobs = []
        def test_processor(job):
            processed_jobs.append(job.id)
            # Create test output
            output_path = tmp_path / "outputs" / job.output_dir
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "result.txt").write_text(f"Processed {job.image_path}")
        
        # Create daemon and job
        daemon = JobDaemon(store, test_processor)
        job_id = store.create_job(image_path)
        
        # Process one job
        success = daemon.run_once()
        assert success is True
        assert len(processed_jobs) == 1
        assert processed_jobs[0] == job_id
        
        # Check job completed
        job = store.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        
        # Check no more jobs
        success = daemon.run_once()
        assert success is False
    
    def test_daemon_error_handling(self, tmp_path):
        """Test daemon handles job processing errors."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path)
        
        image_path = tmp_path / "test.jpg"
        image_path.write_text("fake image data")
        
        # Create processor that always fails
        def failing_processor(job):
            raise Exception("Processing failed")
        
        daemon = JobDaemon(store, failing_processor)
        job_id = store.create_job(image_path)
        
        # Process job (should handle error)
        success = daemon.run_once()
        assert success is True  # Daemon handled the error
        
        # Check job failed
        job = store.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert "Processing failed" in job.error_message


class TestJobModel:
    """Test the Job data model."""
    
    def test_job_duration(self):
        """Test job duration calculation."""
        now = datetime.utcnow()
        
        job = Job(
            id="test123",
            image_path=Path("test.jpg"),
            output_dir=Path("output"),
            status=JobStatus.RUNNING,
            created_at=now,
            started_at=now,
            completed_at=now + timedelta(seconds=5)
        )
        
        assert job.duration_seconds == pytest.approx(5.0, rel=0.1)
    
    def test_job_is_finished(self):
        """Test job finished status."""
        job = Job(
            id="test123",
            image_path=Path("test.jpg"),
            output_dir=Path("output"),
            status=JobStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        assert job.is_finished is False
        
        job.status = JobStatus.RUNNING
        assert job.is_finished is False
        
        job.status = JobStatus.COMPLETED
        assert job.is_finished is True
        
        job.status = JobStatus.FAILED
        assert job.is_finished is True
    
    def test_job_to_dict(self):
        """Test job serialization."""
        now = datetime.utcnow()
        
        job = Job(
            id="test123",
            image_path=Path("test.jpg"),
            output_dir=Path("output"),
            status=JobStatus.COMPLETED,
            created_at=now,
            started_at=now,
            completed_at=now + timedelta(seconds=2),
            metadata={"test": "value"}
        )
        
        data = job.to_dict()
        
        assert data["id"] == "test123"
        assert data["status"] == "completed"
        assert data["metadata"] == {"test": "value"}
        assert data["duration_seconds"] == pytest.approx(2.0, rel=0.1)
        assert isinstance(data["created_at"], str)  # ISO format