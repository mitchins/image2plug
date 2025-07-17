import json
import subprocess
from pathlib import Path


RESULTS_DIR = Path("results")


def run_job(image_path: Path, output_dir: Path, smooth: bool = False,
            measure_error: bool = False, border_mode: str = "tight") -> dict:
    """Run the full workflow on the given image and return parsed results."""
    args = [
        "python",
        "workflow.py",
        str(image_path),
        str(output_dir),
        "--border-mode",
        border_mode,
    ]
    if smooth:
        args.append("--smooth")
    if measure_error:
        args.append("--measure-error")
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def generate_job_id() -> str:
    """Generate a simple unique job id."""
    import uuid
    return uuid.uuid4().hex
