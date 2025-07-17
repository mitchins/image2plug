from __future__ import annotations

from pathlib import Path
import json
import os

from datetime import datetime

from lib import run_workflow
from . import database


def process_job(
    job_id: str,
    image_path: Path,
    output_dir: Path,
    *,
    smooth: bool,
    measure_error: bool,
    border_mode: str,
) -> None:
    """Run the heavy workflow and update the database when finished."""
    try:
        result = run_workflow(
            image_path,
            output_dir,
            smooth=smooth,
            measure_error=measure_error,
            border_mode=border_mode,
        )
        # Mark job complete and maybe store summary json
        (output_dir / "summary.json").write_text(json.dumps(result))
        database.update_status(job_id, "finished")
    except Exception:
        database.update_status(job_id, "failed")
        raise
