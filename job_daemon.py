#!/usr/bin/env python
from __future__ import annotations

import argparse
import time
from pathlib import Path

from job_store import JobStore
from workflow import run_workflow


def process_job(store: JobStore, job: dict, output_root: Path):
    job_id = job["id"]
    out_dir = output_root / job["output_dir"]
    image = Path(job["image_path"])
    try:
        run_workflow(image, out_dir)
        store.complete(job_id)
    except Exception as exc:  # pragma: no cover - rare failures
        store.fail(job_id, str(exc))


def main():
    parser = argparse.ArgumentParser(description="Job processing daemon")
    parser.add_argument("--db", type=Path, default=Path("jobs.db"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="Process a single job and exit")
    args = parser.parse_args()

    store = JobStore(args.db)
    args.output_root.mkdir(parents=True, exist_ok=True)

    while True:
        job = store.fetch_next()
        if job is None:
            if args.once:
                break
            time.sleep(args.interval)
            continue
        process_job(store, job, args.output_root)
        if args.once:
            break


if __name__ == "__main__":
    main()
