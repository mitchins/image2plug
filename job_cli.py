#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from job_store import JobStore


def main():
    parser = argparse.ArgumentParser(description="Enqueue a job")
    parser.add_argument("image", type=Path, help="Image to process")
    parser.add_argument("--db", type=Path, default=Path("jobs.db"))
    args = parser.parse_args()

    store = JobStore(args.db)
    job_id = store.enqueue(args.image)
    print(job_id)


if __name__ == "__main__":
    main()
