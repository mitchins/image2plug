from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import database
from .processing import process_job

POLL_INTERVAL = float(os.environ.get("IMAGE2PLUG_WORKER_INTERVAL", 2))


def run_once() -> bool:
    """Run a single queued job if available. Return True if a job was processed."""
    job = database.get_next_queued_job()
    if not job:
        return False

    opts = json.loads(job["options"]) if job.get("options") else {}
    database.update_status(job["id"], "running")
    process_job(
        job["id"],
        Path(job["input_image"]),
        Path(job["output_dir"]),
        smooth=opts.get("smooth", False),
        measure_error=opts.get("measure_error", False),
        border_mode=opts.get("border_mode", "tight"),
    )
    return True


def main() -> None:
    database.init_db()
    while True:
        processed = run_once()
        if not processed:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
