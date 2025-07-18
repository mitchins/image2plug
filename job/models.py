"""
Job data models and enums.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pathlib import Path


class JobStatus(Enum):
    """Enumeration of possible job statuses."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """
    Job data model representing a single image processing task.
    
    Attributes:
        id: Unique job identifier
        image_path: Path to the input image file
        output_dir: Directory for job output files
        status: Current job status
        created_at: Timestamp when job was created
        started_at: Timestamp when job processing began
        completed_at: Timestamp when job finished (success or failure)
        error_message: Error details if job failed
        metadata: Additional job-specific data
    """
    id: str
    image_path: Path
    output_dir: Path
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds if started."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def is_finished(self) -> bool:
        """Check if job has completed (successfully or with error)."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED)
    
    def to_dict(self) -> dict:
        """Convert job to dictionary representation."""
        return {
            "id": self.id,
            "image_path": str(self.image_path),
            "output_dir": str(self.output_dir),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds
        }