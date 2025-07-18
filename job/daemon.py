"""
Job processing daemon with robust error handling and lifecycle management.
"""

import time
import signal
import logging
from pathlib import Path
from typing import Optional, Callable
import sys

from .store import JobStore
from .models import Job


class JobDaemon:
    """
    Robust job processing daemon.
    
    Features:
    - Graceful shutdown handling
    - Configurable processing intervals
    - Comprehensive error handling and logging
    - Pluggable job processors
    - Single job mode for testing
    """
    
    def __init__(
        self, 
        store: JobStore,
        processor: Callable[[Job], None],
        interval: float = 1.0
    ):
        """
        Initialize job daemon.
        
        Args:
            store: Job store instance
            processor: Function to process jobs (job) -> None
            interval: Polling interval in seconds
        """
        self.store = store
        self.processor = processor
        self.interval = interval
        
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def process_job(self, job: Job) -> bool:
        """
        Process a single job with error handling.
        
        Args:
            job: Job to process
            
        Returns:
            True if successful, False if failed
        """
        try:
            self.logger.info(f"Processing job {job.id}: {job.image_path}")
            
            # Execute the job processor
            self.processor(job)
            
            # Mark as completed
            self.store.complete_job(job.id)
            self.logger.info(f"Successfully completed job {job.id}")
            return True
            
        except Exception as e:
            error_msg = f"Job processing failed: {str(e)}"
            self.logger.error(f"Job {job.id} failed: {error_msg}", exc_info=True)
            
            # Mark as failed
            self.store.fail_job(job.id, error_msg)
            return False

    def run_once(self) -> bool:
        """
        Process one job from the queue.
        
        Returns:
            True if a job was processed, False if queue was empty
        """
        job = self.store.fetch_next_job()
        if job is None:
            return False
            
        self.process_job(job)
        return True

    def run(self, max_jobs: Optional[int] = None) -> None:
        """
        Run the daemon, processing jobs until stopped.
        
        Args:
            max_jobs: Maximum number of jobs to process (None for unlimited)
        """
        self.running = True
        processed_count = 0
        idle_cycles = 0
        
        self.logger.info(f"Job daemon starting (interval={self.interval}s, max_jobs={max_jobs})")
        
        try:
            while self.running:
                # Check if we've hit the job limit
                if max_jobs is not None and processed_count >= max_jobs:
                    self.logger.info(f"Reached maximum job limit ({max_jobs})")
                    break
                
                # Try to process a job
                if self.run_once():
                    processed_count += 1
                    idle_cycles = 0
                    self.logger.info(f"Jobs processed: {processed_count}")
                else:
                    # No jobs available, sleep before checking again
                    idle_cycles += 1
                    if idle_cycles == 1:
                        self.logger.info("No jobs available, waiting...")
                    elif idle_cycles % 10 == 0:  # Log every 10 cycles to show daemon is alive
                        self.logger.debug(f"Still waiting for jobs (idle cycles: {idle_cycles})")
                    
                    time.sleep(self.interval)
                    
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Daemon error: {e}", exc_info=True)
            raise
        finally:
            self.running = False
            self.logger.info(f"Job daemon stopped. Processed {processed_count} jobs.")

    def status(self) -> dict:
        """
        Get daemon status information.
        
        Returns:
            Status dictionary
        """
        return {
            "running": self.running,
            "interval": self.interval,
            "job_stats": self.store.get_stats()
        }