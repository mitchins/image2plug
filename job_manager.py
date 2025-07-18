#!/usr/bin/env python
"""
Main job management entry point.

This script provides a unified interface to the job system,
replacing the old job_cli.py, job_daemon.py, and job_store.py scripts.
"""

from job.cli import main

if __name__ == "__main__":
    exit(main())