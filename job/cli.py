"""
Comprehensive CLI interface for job management.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from .store import JobStore
from .models import JobStatus
from .daemon import JobDaemon


class JobCLI:
    """
    Command-line interface for job queue management.
    
    Provides commands for:
    - Creating jobs
    - Listing jobs
    - Job status queries
    - Queue statistics
    - Job purging
    - Daemon management
    """
    
    def __init__(self, db_path: Path):
        """Initialize CLI with database path."""
        self.db_path = db_path
        self.store = JobStore(db_path)
        self.logger = logging.getLogger(__name__)

    def create_job(self, image_path: Path, metadata: Optional[dict] = None) -> str:
        """Create a new job and return its ID."""
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        job_id = self.store.create_job(image_path, metadata)
        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get job details by ID."""
        job = self.store.get_job(job_id)
        return job.to_dict() if job else None

    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 20) -> list:
        """List jobs with optional status filter."""
        jobs = self.store.list_jobs(status, limit)
        return [job.to_dict() for job in jobs]

    def get_stats(self) -> dict:
        """Get job queue statistics."""
        return self.store.get_stats()

    def purge_jobs(self, older_than_days: int = 30) -> int:
        """Purge old completed/failed jobs."""
        return self.store.purge_old_jobs(older_than_days)

    def format_job_table(self, jobs: list) -> str:
        """Format jobs as a readable table."""
        if not jobs:
            return "No jobs found."
        
        # Table headers
        headers = ["ID", "Status", "Image", "Created", "Duration"]
        
        # Calculate column widths
        id_width = max(8, max(len(job["id"][:8]) for job in jobs))
        status_width = max(7, max(len(job["status"]) for job in jobs))
        image_width = max(20, max(len(Path(job["image_path"]).name) for job in jobs))
        created_width = 19  # ISO timestamp length
        duration_width = 10
        
        # Format header
        header_line = f"{'ID':<{id_width}} {'Status':<{status_width}} {'Image':<{image_width}} {'Created':<{created_width}} {'Duration':<{duration_width}}"
        separator = "-" * len(header_line)
        
        # Format job rows
        rows = [header_line, separator]
        
        for job in jobs:
            job_id = job["id"][:8]
            status = job["status"]
            image_name = Path(job["image_path"]).name
            if len(image_name) > image_width:
                image_name = "..." + image_name[-(image_width-3):]
            
            created = datetime.fromisoformat(job["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            
            duration = ""
            if job["duration_seconds"] is not None:
                duration = f"{job['duration_seconds']:.1f}s"
            
            row = f"{job_id:<{id_width}} {status:<{status_width}} {image_name:<{image_width}} {created:<{created_width}} {duration:<{duration_width}}"
            rows.append(row)
        
        return "\n".join(rows)

    @staticmethod
    def setup_logging(verbose: bool = False):
        """Setup logging configuration."""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        description="Job queue management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--db", 
        type=Path, 
        default=Path("db/jobs.db"),
        help="Database file path (default: db/jobs.db)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create job command
    create_parser = subparsers.add_parser("create", help="Create a new job")
    create_parser.add_argument("image", type=Path, help="Path to image file")
    create_parser.add_argument("--metadata", type=str, help="JSON metadata for job")
    
    # Workflow options
    create_parser.add_argument("--proof", action="store_true", help="Generate HTML proof report")
    create_parser.add_argument("--extrude-height", type=float, default=10.0, help="Extrusion height (mm)")
    create_parser.add_argument("--smooth", action="store_true", help="Enable contour smoothing") 
    create_parser.add_argument("--measure-error", action="store_true", help="Calculate MSE between smoothed/raw contours")
    create_parser.add_argument("--border-mode", choices=["tight", "inside", "outside"], default="tight", help="Border interpretation mode")
    
    # Get job command
    get_parser = subparsers.add_parser("get", help="Get job details by ID")
    get_parser.add_argument("job_id", help="Job ID")
    get_parser.add_argument("--json", action="store_true", help="Output as JSON")
    get_parser.add_argument("--output-path", action="store_true", help="Show full output path")
    
    # List jobs command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--status", choices=[s.value for s in JobStatus], help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum jobs to show")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show queue statistics")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Purge command
    purge_parser = subparsers.add_parser("purge", help="Purge old jobs")
    purge_parser.add_argument("--days", type=int, default=30, help="Remove jobs older than N days")
    purge_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run job processing daemon")
    daemon_parser.add_argument("--output-root", type=Path, default=Path("web_results"), help="Root directory for job outputs")
    daemon_parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    daemon_parser.add_argument("--once", action="store_true", help="Process single job and exit")
    daemon_parser.add_argument("--max-jobs", type=int, help="Maximum jobs to process before stopping")
    
    # Status command - check what jobs are pending/running
    status_parser = subparsers.add_parser("status", help="Show detailed queue status") 
    status_parser.add_argument("--watch", "-w", action="store_true", help="Watch status continuously")
    status_parser.add_argument("--interval", type=float, default=2.0, help="Watch interval in seconds")
    
    # Find command - locate output directory for job
    find_parser = subparsers.add_parser("find", help="Find output directory for job ID")
    find_parser.add_argument("job_id", help="Job ID to find")
    find_parser.add_argument("--output-root", type=Path, default=Path("web_results"), help="Output root directory")
    
    return parser


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    JobCLI.setup_logging(args.verbose)
    
    # Ensure database directory exists
    args.db.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize CLI
    cli = JobCLI(args.db)
    
    try:
        if args.command == "create":
            # Build workflow options from command line args
            workflow_options = {
                "proof": args.proof,
                "extrude_height": args.extrude_height,
                "smooth": args.smooth,
                "measure_error": args.measure_error,
                "border_mode": args.border_mode
            }
            
            # Merge with any additional metadata
            metadata = json.loads(args.metadata) if args.metadata else {}
            metadata["workflow_options"] = workflow_options
            
            job_id = cli.create_job(args.image, metadata)
            print(job_id)
            
        elif args.command == "get":
            job = cli.get_job(args.job_id)
            if job is None:
                print(f"Job {args.job_id} not found", file=sys.stderr)
                return 1
            
            if args.output_path:
                # Show the actual filesystem path
                from pathlib import Path
                output_root = Path("web_results")  # Default output root
                full_path = output_root / job["output_dir"]
                print(f"Output directory: {full_path}")
                if full_path.exists():
                    print("Contents:")
                    for item in sorted(full_path.iterdir()):
                        print(f"  {item.name}")
                else:
                    print("Directory does not exist (job may not have completed)")
            elif args.json:
                print(json.dumps(job, indent=2))
            else:
                print(cli.format_job_table([job]))
                
        elif args.command == "list":
            status = JobStatus(args.status) if args.status else None
            jobs = cli.list_jobs(status, args.limit)
            
            if args.json:
                print(json.dumps(jobs, indent=2))
            else:
                print(cli.format_job_table(jobs))
                
        elif args.command == "stats":
            stats = cli.get_stats()
            
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("Job Queue Statistics:")
                for status, count in stats.items():
                    print(f"  {status.title()}: {count}")
                    
        elif args.command == "status":
            if args.watch:
                import time
                import os
                try:
                    while True:
                        # Clear screen
                        os.system('clear' if os.name == 'posix' else 'cls')
                        
                        # Show current status
                        print("=== Job Queue Status (Press Ctrl+C to exit) ===")
                        stats = cli.get_stats()
                        for status, count in stats.items():
                            print(f"  {status.title()}: {count}")
                        print()
                        
                        # Show recent jobs
                        print("Recent Jobs:")
                        jobs = cli.list_jobs(limit=10)
                        if jobs:
                            print(cli.format_job_table(jobs))
                        else:
                            print("  No jobs found")
                        
                        print(f"\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        time.sleep(args.interval)
                        
                except KeyboardInterrupt:
                    print("\nStopped watching.")
            else:
                print("=== Job Queue Status ===")
                stats = cli.get_stats()
                for status, count in stats.items():
                    print(f"  {status.title()}: {count}")
                print()
                
                print("Recent Jobs:")
                jobs = cli.list_jobs(limit=10) 
                if jobs:
                    print(cli.format_job_table(jobs))
                else:
                    print("  No jobs found")
                    
        elif args.command == "find":
            # Find output directory for job ID
            
            # Check if job exists first
            job = cli.get_job(args.job_id)
            if job is None:
                print(f"Job {args.job_id} not found", file=sys.stderr)
                return 1
            
            # Use job ID directly as output directory
            output_dir = args.job_id
            full_path = args.output_root / output_dir
            
            print(f"Job ID: {args.job_id}")
            print(f"Output directory: {full_path}")
            print(f"Status: {job['status']}")
            
            if full_path.exists():
                print("\nContents:")
                for item in sorted(full_path.iterdir()):
                    size = ""
                    if item.is_file():
                        size = f" ({item.stat().st_size} bytes)"
                    print(f"  {item.name}{size}")
            else:
                print("\nDirectory does not exist (job may not have completed)")
                    
        elif args.command == "purge":
            if args.dry_run:
                # TODO: Implement dry-run logic
                print("Dry-run mode not yet implemented")
                return 1
            else:
                purged = cli.purge_jobs(args.days)
                print(f"Purged {purged} old jobs")
                
        elif args.command == "daemon":
            # Import workflow processor with fallback
            run_workflow = None
            try:
                import sys
                import os
                from pathlib import Path
                # Add parent directory to path to import workflow
                parent_dir = str(Path(__file__).parent.parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                # Change working directory to project root for relative imports
                original_cwd = os.getcwd()
                os.chdir(parent_dir)
                from workflow import run_workflow
                os.chdir(original_cwd)
                print("Using full workflow processor")
            except ImportError as e:
                print(f"Warning: workflow module not available ({e}), using test processor")
            
            # Create processor function  
            def process_job(job):
                output_path = args.output_root / job.output_dir
                output_path.mkdir(parents=True, exist_ok=True)
                
                if run_workflow is not None:
                    # Extract workflow options from job metadata
                    workflow_options = {}
                    if job.metadata and "workflow_options" in job.metadata:
                        workflow_options = job.metadata["workflow_options"]
                    
                    # Use real workflow with job-specific options
                    run_workflow(
                        job.image_path, 
                        output_path,
                        proof=workflow_options.get("proof", False),
                        extrude_height=workflow_options.get("extrude_height", 10.0),
                        smooth=workflow_options.get("smooth", False),
                        measure_error=workflow_options.get("measure_error", False),
                        border_mode=workflow_options.get("border_mode", "tight")
                    )
                else:
                    # Fallback test processor
                    workflow_opts = job.metadata.get("workflow_options", {}) if job.metadata else {}
                    test_output = f"Processed {job.image_path}\nOptions: {workflow_opts}"
                    (output_path / "test_output.txt").write_text(test_output)
                    import time
                    time.sleep(0.1)  # Simulate processing time
            
            # Create and run daemon
            daemon = JobDaemon(
                store=cli.store,
                processor=process_job,
                interval=args.interval
            )
            
            if args.once:
                success = daemon.run_once()
                return 0 if success else 1
            else:
                daemon.run(max_jobs=args.max_jobs)
                return 0
                
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())