"""
Compatibility utilities for migrating from direct workflow execution to job queue.
"""

from pathlib import Path
from typing import Optional
from .store import JobStore


def enqueue_workflow_job(
    image: Path,
    db_path: Path = Path("db/jobs.db"),
    *,
    proof: bool = False,
    extrude_height: float = 10.0,
    smooth: bool = False,
    measure_error: bool = False,
    border_mode: str = "tight"
) -> str:
    """
    Enqueue a workflow job with the same parameters as run_workflow.
    
    This provides a drop-in replacement for immediate workflow execution,
    allowing gradual migration to the job queue system.
    
    Args:
        image: Path to input image
        db_path: Database file path
        proof: Generate HTML proof report
        extrude_height: Extrusion height in mm
        smooth: Enable contour smoothing
        measure_error: Calculate MSE between smoothed/raw contours
        border_mode: Border interpretation mode
        
    Returns:
        Job ID string
    """
    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create job store and enqueue with workflow options
    store = JobStore(db_path)
    
    metadata = {
        "workflow_options": {
            "proof": proof,
            "extrude_height": extrude_height,
            "smooth": smooth,
            "measure_error": measure_error,
            "border_mode": border_mode
        }
    }
    
    return store.create_job(image, metadata)