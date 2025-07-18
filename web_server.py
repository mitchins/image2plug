#!/usr/bin/env python3
"""
FastAPI web server for image2plug job processing.

Provides REST API for job submission and status checking,
plus static file serving for results.
"""

import asyncio
import threading
import time
import tempfile
import shutil
import os
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request, Depends, Cookie, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
import time
import uuid
import secrets
from collections import defaultdict, deque
from typing import Optional

from job import JobStore, JobDaemon, JobStatus
from workflow import run_workflow


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment detection
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "development").lower() == "development"
IS_PRODUCTION = not IS_DEVELOPMENT

logger.info(f"Starting image2plug server in {'DEVELOPMENT' if IS_DEVELOPMENT else 'PRODUCTION'} mode")

# Rate limiting storage
rate_limit_storage = defaultdict(lambda: deque())

# Session storage for user job tracking
user_sessions = {}  # session_id -> {jobs: set(), created_at: timestamp}
SESSION_EXPIRY_HOURS = 24

# Global daemon instance
daemon_instance = None
daemon_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    start_daemon()
    yield
    # Shutdown
    stop_daemon()

app = FastAPI(
    title="image2plug Job API",
    description="REST API for submitting and monitoring image processing jobs",
    version="1.0.0",
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.your-domain.com"]  # Configure for production
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 10, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
    
    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        
        # Clean old entries
        client_requests = rate_limit_storage[client_ip]
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True


# Rate limiters for different endpoints - more lenient in development
if IS_DEVELOPMENT:
    job_submission_limiter = RateLimiter(max_requests=100, window_minutes=1)  # 100 jobs per minute in dev
    api_limiter = RateLimiter(max_requests=1000, window_minutes=1)  # 1000 API calls per minute in dev
else:
    job_submission_limiter = RateLimiter(max_requests=5, window_minutes=1)  # 5 jobs per minute in prod
    api_limiter = RateLimiter(max_requests=60, window_minutes=1)  # 60 API calls per minute in prod


def get_client_ip(request: Request) -> str:
    """Get client IP address, handling proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host


def check_rate_limit(limiter: RateLimiter, client_ip: str, bypass_in_dev: bool = True) -> bool:
    """Check rate limit, with optional bypass in development."""
    if IS_DEVELOPMENT and bypass_in_dev:
        return True
    return limiter.is_allowed(client_ip)


def get_or_create_session(session_id: Optional[str] = Cookie(None)) -> tuple[str, bool]:
    """Get existing session or create new one. Returns (session_id, is_new)."""
    now = time.time()
    
    # Clean expired sessions
    expired_sessions = [
        sid for sid, data in user_sessions.items()
        if now - data["created_at"] > SESSION_EXPIRY_HOURS * 3600
    ]
    for sid in expired_sessions:
        del user_sessions[sid]
    
    # Check if session exists and is valid
    if session_id and session_id in user_sessions:
        return session_id, False
    
    # Create new session
    new_session_id = secrets.token_urlsafe(32)
    user_sessions[new_session_id] = {
        "jobs": set(),
        "created_at": now
    }
    return new_session_id, True


def get_user_jobs(session_id: str) -> set:
    """Get job IDs for a user session."""
    if session_id in user_sessions:
        return user_sessions[session_id]["jobs"]
    return set()


def add_job_to_session(session_id: str, job_id: str):
    """Add a job to a user session."""
    if session_id in user_sessions:
        user_sessions[session_id]["jobs"].add(job_id)

# Configuration
DB_PATH = Path("db/jobs.db")
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("web_results")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Ensure directories exist
DB_PATH.parent.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Initialize job store
store = JobStore(DB_PATH)


class JobSubmission(BaseModel):
    """Job submission parameters."""
    proof: bool = Field(default=False, description="Generate HTML proof report")
    extrude_height: float = Field(default=10.0, ge=0.1, le=100.0, description="Extrusion height in mm")
    smooth: bool = Field(default=False, description="Enable contour smoothing")
    measure_error: bool = Field(default=False, description="Calculate MSE between smoothed/raw contours")
    border_mode: str = Field(default="tight", pattern="^(tight|inside|outside)$", description="Border interpretation mode")


class JobResponse(BaseModel):
    """Job response model."""
    job_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    results_url: Optional[str] = None


class JobStats(BaseModel):
    """Job queue statistics."""
    pending: int
    running: int
    completed: int
    failed: int
    total: int
    average_processing_time: Optional[float] = None
    queue_position: Optional[int] = None  # Position for user's pending jobs


def create_job_processor():
    """Create job processor function for daemon."""
    def process_job(job):
        try:
            logger.info(f"Processing job {job.id}: {job.image_path}")
            
            # Extract workflow options
            workflow_options = {}
            if job.metadata and "workflow_options" in job.metadata:
                workflow_options = job.metadata["workflow_options"]
            
            # Run the workflow
            output_path = RESULTS_DIR / job.output_dir
            output_path.mkdir(parents=True, exist_ok=True)
            
            run_workflow(
                job.image_path,
                output_path,
                proof=workflow_options.get("proof", False),
                extrude_height=workflow_options.get("extrude_height", 10.0),
                smooth=workflow_options.get("smooth", False),
                measure_error=workflow_options.get("measure_error", False),
                border_mode=workflow_options.get("border_mode", "tight")
            )
            
            logger.info(f"Successfully completed job {job.id}")
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}", exc_info=True)
            raise
    
    return process_job


def start_daemon():
    """Start the job processing daemon in background thread."""
    global daemon_instance, daemon_thread
    
    if daemon_instance is not None:
        return
    
    processor = create_job_processor()
    daemon_instance = JobDaemon(store, processor, interval=1.0, setup_signal_handlers=False)
    
    def run_daemon():
        logger.info("Starting job daemon thread")
        daemon_instance.run()
    
    daemon_thread = threading.Thread(target=run_daemon, daemon=True)
    daemon_thread.start()
    logger.info("Job daemon started in background thread")


def stop_daemon():
    """Stop the job processing daemon."""
    global daemon_instance, daemon_thread
    if daemon_instance:
        logger.info("Stopping job daemon...")
        daemon_instance.running = False
        
        # Wait for daemon thread to finish (with timeout)
        if daemon_thread and daemon_thread.is_alive():
            daemon_thread.join(timeout=2.0)
            if daemon_thread.is_alive():
                logger.warning("Daemon thread did not stop gracefully")
        
        daemon_instance = None
        daemon_thread = None



@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session_data: tuple = Depends(get_or_create_session)):
    """Serve the main web interface."""
    session_id, is_new = session_data
    
    response = FileResponse("static/index.html")
    if is_new:
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=SESSION_EXPIRY_HOURS * 3600,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
    return response


@app.post("/api/jobs", response_model=JobResponse)
async def submit_job(
    request: Request,
    file: UploadFile = File(...),
    proof: bool = Form(False),
    extrude_height: float = Form(10.0),
    smooth: bool = Form(False),
    measure_error: bool = Form(False),
    border_mode: str = Form("tight"),
    session_data: tuple = Depends(get_or_create_session)
):
    """Submit a new image processing job."""
    session_id, is_new = session_data
    
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(job_submission_limiter, client_ip):
        limit_msg = "100 job submissions per minute" if IS_DEVELOPMENT else "5 job submissions per minute"
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {limit_msg}."
        )
    
    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Validate filename to prevent path traversal
    if not file.filename or ".." in file.filename or "/" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
    
    # Additional security: verify it's actually an image
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(contents)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
    
    # Save uploaded file
    file_path = UPLOAD_DIR / f"{int(time.time())}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Create job
    metadata = {
        "workflow_options": {
            "proof": proof,
            "extrude_height": extrude_height,
            "smooth": smooth,
            "measure_error": measure_error,
            "border_mode": border_mode
        },
        "original_filename": file.filename
    }
    
    job_id = store.create_job(file_path, metadata)
    job = store.get_job(job_id)
    
    # Add job to user session
    add_job_to_session(session_id, job_id)
    
    response = JobResponse(
        job_id=job.id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        metadata=job.metadata,
        results_url=f"/results/{job.id}/"
    )
    
    return response


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    request: Request, 
    job_id: str,
    session_data: tuple = Depends(get_or_create_session)
):
    """Get job status and details."""
    session_id, is_new = session_data
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(api_limiter, client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Validate job_id format (UUID without hyphens)
    if not job_id or len(job_id) != 32 or not all(c in '0123456789abcdef' for c in job_id.lower()):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    # Check if user owns this job
    user_job_ids = get_user_jobs(session_id)
    if job_id not in user_job_ids:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    results_url = None
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        results_url = f"/results/{job.id}/"
    
    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        metadata=job.metadata,
        results_url=results_url
    )


@app.get("/api/stats", response_model=JobStats)
async def get_queue_stats(
    request: Request,
    session_data: tuple = Depends(get_or_create_session)
):
    """Get job queue statistics."""
    session_id, is_new = session_data
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(api_limiter, client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    stats = store.get_stats()
    
    # Calculate average processing time for completed jobs
    completed_jobs = store.list_jobs(status=JobStatus.COMPLETED, limit=100)
    if completed_jobs:
        durations = [job.duration_seconds for job in completed_jobs if job.duration_seconds]
        avg_time = sum(durations) / len(durations) if durations else None
    else:
        avg_time = None
    
    # Calculate queue position for user's pending jobs
    user_job_ids = get_user_jobs(session_id)
    queue_position = None
    if user_job_ids:
        pending_jobs = store.list_jobs(status=JobStatus.PENDING, limit=1000)
        for i, job in enumerate(pending_jobs):
            if job.id in user_job_ids:
                queue_position = i + 1
                break
    
    return JobStats(
        **stats,
        average_processing_time=avg_time,
        queue_position=queue_position
    )


@app.get("/api/jobs", response_model=list[JobResponse])
async def list_jobs(
    request: Request, 
    limit: int = 50, 
    status: Optional[str] = None,
    session_data: tuple = Depends(get_or_create_session)
):
    """List user's own jobs with optional status filter."""
    session_id, is_new = session_data
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(api_limiter, client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Limit the maximum number of jobs that can be requested
    limit = min(limit, 100)
    job_status = None
    if status:
        try:
            job_status = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get all jobs, then filter to user's jobs
    all_jobs = store.list_jobs(status=job_status, limit=1000)
    user_job_ids = get_user_jobs(session_id)
    
    # Filter to only user's jobs
    jobs = [job for job in all_jobs if job.id in user_job_ids][:limit]
    
    return [
        JobResponse(
            job_id=job.id,
            status=job.status.value,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            metadata=job.metadata,
            results_url=f"/results/{job.id}/" if job.status in (JobStatus.COMPLETED, JobStatus.FAILED) else None
        )
        for job in jobs
    ]


# Mount static file serving for results, with directory index serving (html=True)
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR), html=True), name="results")

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    stop_daemon()
    sys.exit(0)


if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        stop_daemon()
        sys.exit(0)