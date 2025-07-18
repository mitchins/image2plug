# Job Queue System Documentation

The **image2plug** job queue system provides robust, scalable image processing with persistence, error handling, and multi-process safety.

## Architecture

```
job/
├── __init__.py          # Public API exports
├── models.py            # Job data model and enums  
├── store.py             # SQLite database operations
├── daemon.py            # Job processing daemon
├── cli.py               # Command-line interface
└── tests/               # Test package
```

## Output Directory Structure

Job outputs are stored using the **job ID as the directory name** for security and simplicity:

**Example:**
- **Job ID:** `77aefbbae1c745b3b85e479e77f1c122`  
- **Output Directory:** `web_results/77aefbbae1c745b3b85e479e77f1c122/`

**Benefits:**
- **Security** - 32-character UUIDs are cryptographically unguessable
- **Web-ready** - Safe for public HTTP serving without enumeration risks
- **Simple** - Job ID = Directory name (no conversion needed)
- **Unique** - UUIDs guarantee no collisions

**Accessing outputs:**
```bash
# Find outputs for a job
python3 job_manager.py find 77aefbbae1c745b3b85e479e77f1c122

# Direct filesystem access
ls web_results/77aefbbae1c745b3b85e479e77f1c122/
```

## Core Components

### JobStore
Multi-process safe SQLite database for job persistence.

**Features:**
- WAL mode for concurrent access
- Atomic job fetching 
- Rich metadata support
- Auto-purging of old jobs
- Performance indexes

**Usage:**
```python
from job import JobStore, JobStatus

store = JobStore("db/jobs.db")

# Create job
job_id = store.create_job(
    image_path=Path("image.jpg"),
    metadata={"workflow_options": {"proof": True}}
)

# Fetch next job atomically  
job = store.fetch_next_job()

# Complete or fail job
store.complete_job(job_id)
store.fail_job(job_id, "Error message")
```

### Job Model
Rich data model with full lifecycle tracking.

```python
@dataclass
class Job:
    id: str                           # Unique identifier
    image_path: Path                  # Input image 
    output_dir: Path                  # Output directory
    status: JobStatus                 # Current status
    created_at: datetime              # Creation time
    started_at: Optional[datetime]    # Start time
    completed_at: Optional[datetime]  # Completion time
    error_message: Optional[str]      # Error details
    metadata: Optional[dict]          # Custom data

    @property
    def duration_seconds(self) -> Optional[float]
    @property  
    def is_finished(self) -> bool
    def to_dict(self) -> dict
```

**Job Statuses:**
- `PENDING` - Waiting for processing
- `RUNNING` - Currently being processed  
- `COMPLETED` - Successfully finished
- `FAILED` - Processing failed

### JobDaemon
Robust job processor with error handling.

**Features:**
- Graceful shutdown handling
- Configurable polling intervals
- Comprehensive logging
- Pluggable processors
- Single job mode for testing

**Usage:**
```python
from job import JobDaemon

def my_processor(job):
    # Process the job
    print(f"Processing {job.image_path}")
    
daemon = JobDaemon(store, my_processor, interval=1.0)
daemon.run()  # Continuous processing
daemon.run_once()  # Single job
```

## CLI Interface

The `job_manager.py` script provides complete job management:

### Job Creation
```bash
# Basic job creation
python3 job_manager.py create image.jpg

# With workflow options
python3 job_manager.py create image.jpg \
    --proof \
    --smooth \
    --extrude-height 15.0 \
    --border-mode inside \
    --measure-error

# With custom metadata  
python3 job_manager.py create image.jpg \
    --metadata '{"priority": "high", "user": "admin"}'
```

### Job Monitoring
```bash
# List all jobs
python3 job_manager.py list

# Filter by status
python3 job_manager.py list --status pending
python3 job_manager.py list --status running --limit 5

# Get specific job details
python3 job_manager.py get abc123def456 --json

# Find output directory for a job
python3 job_manager.py find abc123def456

# Show output path and contents
python3 job_manager.py get abc123def456 --output-path

# Live status monitoring
python3 job_manager.py status --watch --interval 1.0
```

### Daemon Management
```bash
# Run daemon continuously 
python3 job_manager.py daemon

# Process single job and exit
python3 job_manager.py daemon --once

# Custom configuration
python3 job_manager.py daemon \
    --output-root /var/results \
    --interval 0.5 \
    --max-jobs 100

# Debug mode
python3 job_manager.py --verbose daemon
```

### Maintenance
```bash
# Show queue statistics
python3 job_manager.py stats

# Clean up old jobs (30+ days)
python3 job_manager.py purge --days 30

# Dry run cleanup
python3 job_manager.py purge --days 7 --dry-run
```

## Database Schema

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,              -- UUID hex string
    image_path TEXT NOT NULL,         -- Input image path
    output_dir TEXT NOT NULL,         -- Output directory name
    status TEXT NOT NULL,             -- Job status enum
    created_at TEXT NOT NULL,         -- ISO timestamp
    started_at TEXT,                  -- ISO timestamp
    completed_at TEXT,                -- ISO timestamp  
    error_message TEXT,               -- Error details
    metadata TEXT                     -- JSON metadata
);

CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_created_at ON jobs(created_at);
```

## Workflow Integration

All `workflow.py` options are supported through job metadata:

```python
# Equivalent workflow calls:

# Direct execution
run_workflow(
    image=Path("photo.jpg"),
    output_dir=Path("results"),
    proof=True,
    smooth=True,
    extrude_height=15.0,
    border_mode="inside"
)

# Job queue execution  
job_id = enqueue_workflow_job(
    image=Path("photo.jpg"),
    proof=True,
    smooth=True,
    extrude_height=15.0,
    border_mode="inside"
)
```

**Supported Options:**
- `proof` - Generate HTML proof report
- `extrude_height` - Extrusion height in mm
- `smooth` - Enable contour smoothing
- `measure_error` - Calculate MSE between smoothed/raw contours
- `border_mode` - Border interpretation (tight/inside/outside)

## Web Security

The job system is designed with web deployment security in mind:

**Secure URLs:**
```
# Job ID serves as unguessable access token
GET /results/77aefbbae1c745b3b85e479e77f1c122/index.html
GET /results/77aefbbae1c745b3b85e479e77f1c122/candidates/shape.dxf

# No way to enumerate or guess other job results
# 32-character UUIDs provide 2^122 possible values
```

**Web Server Configuration:**
```nginx
# Example Nginx config
location /results/ {
    root /app/web_results;
    # Only serve if exact path exists - no directory listing
    try_files $uri =404;
}
```

**API Integration:**
```python
# Web API can safely return job IDs as access tokens
@app.route('/submit', methods=['POST'])
def submit_job():
    job_id = create_job(request.files['image'])
    return {
        'job_id': job_id,
        'status_url': f'/api/jobs/{job_id}',
        'results_url': f'/results/{job_id}/'
    }
```

## Docker Deployment

Example Dockerfile for production deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Create directories
RUN mkdir -p db web_results

# Run daemon
CMD ["python3", "job_manager.py", "daemon", "--output-root", "/app/web_results"]
```

## Error Handling

The system provides comprehensive error handling:

**Database Errors:**
- Connection timeouts with retries
- Transaction rollback on failures
- Schema migration support

**Job Processing Errors:**
- Individual job failures don't crash daemon
- Full error messages and stack traces logged
- Failed jobs marked with error details

**Logging:**
```python
import logging

# Configure logging for job system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Components log to these loggers:
# - job.store
# - job.daemon  
# - job.cli
```

## Performance Considerations

**SQLite Optimizations:**
- WAL mode for better concurrency
- Memory-mapped I/O
- Optimized timeouts
- Strategic indexes

**Job Processing:**
- Atomic job fetching prevents race conditions
- Configurable polling intervals
- Efficient status queries

**Memory Usage:**
- Streaming job processing
- Automatic cleanup of old jobs
- No in-memory job caching

## Integration with Workflow

The job system integrates seamlessly with the existing workflow:

**Direct processing:**
```bash
python3 workflow.py input.jpg results --proof --smooth
```

**Queue-based processing:**
```bash
# Enqueue job with same options
python3 job_manager.py create input.jpg --proof --smooth

# Process jobs
python3 job_manager.py daemon
```

**Programmatic usage:**
```python
# Direct processing
from workflow import run_workflow
run_workflow(image, output_dir, proof=True)

# Queue-based processing
from job import JobStore
store = JobStore("db/jobs.db")
job_id = store.create_job(image, {"workflow_options": {"proof": True}})
```

## API Reference

### JobStore Methods
- `create_job(image_path, metadata=None) -> str`
- `get_job(job_id) -> Optional[Job]`  
- `fetch_next_job() -> Optional[Job]`
- `complete_job(job_id) -> bool`
- `fail_job(job_id, error_message) -> bool`
- `list_jobs(status=None, limit=100) -> List[Job]`
- `get_stats() -> dict`
- `purge_old_jobs(older_than_days=30) -> int`

### JobDaemon Methods
- `run_once() -> bool`
- `run(max_jobs=None) -> None`
- `process_job(job) -> bool`
- `status() -> dict`


## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_job_system.py -v
```

**Test Coverage:**
- Job creation and retrieval
- Atomic job fetching
- Job completion and failure
- Status filtering and statistics  
- Daemon error handling
- Data model validation