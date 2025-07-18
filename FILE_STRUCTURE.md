# Project File Structure

## Job System Files

### ✅ Active Files (Use These)
- `job_manager.py` - **Main entry point** for all job operations
- `job/` - **Modular job system** package
  - `job/__init__.py` - Public API exports
  - `job/models.py` - Job data model and status enums
  - `job/store.py` - SQLite database operations
  - `job/daemon.py` - Job processing daemon
  - `job/cli.py` - Command-line interface logic
  - `job/compat.py` - Compatibility utilities
  - `job/tests/` - Test package directory

### 🌐 Web Application
- `web_server.py` - **FastAPI web server with integrated daemon**
- `static/index.html` - **Material UI frontend interface**
- `static/app.js` - **JavaScript application logic**
- `environment.yml` - **Conda environment specification**
- `Dockerfile` - **Single container deployment (conda-based)**
- `docker-compose.yml` - **Development setup**
- `setup-conda.sh` - **Conda environment setup script**
- `start.sh` - **Easy deployment script**

### 📚 Documentation
- `JOB_SYSTEM.md` - **Comprehensive job system documentation**
- `DEPLOYMENT.md` - **Web deployment and Cloudflare setup guide**
- `README.md` - **Updated with job system section**
- `FILE_STRUCTURE.md` - This file

### 🧪 Tests
- `tests/test_job_system.py` - **Comprehensive test suite**

## Core Application Files

### 🎯 Main Workflow
- `workflow.py` - Main image processing pipeline
- `detect_candidates.py` - Shape detection
- `straighten.py` - Image straightening
- `proofing.py` - Report generation

### 📁 Supporting Files
- `requirements.txt` - Python dependencies
- `assets/` - Example images and templates
- `scripts/` - Utility scripts
- `templates/` - HTML/React templates

## Usage Examples

### ✅ Correct Usage
```bash
# Job system
python3 job_manager.py create image.jpg --proof
python3 job_manager.py daemon
python3 job_manager.py status

# Direct processing  
python3 workflow.py image.jpg results --proof
```

## System Design

**Clean Architecture:**
- Modular job system under `job/` package
- Enhanced CLI with all workflow options
- Comprehensive documentation and testing
- Web-ready security model

**Key Features:**
- Multi-process safe SQLite operations
- Full workflow option support per job
- Secure UUID-based output directories
- Rich job metadata and lifecycle tracking
- Auto-purging and maintenance utilities