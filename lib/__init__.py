"""Helper imports exposing core processing functions for the web app."""

from pathlib import Path
from typing import Dict, Optional

import subprocess
import sys
import json

ROOT = Path(__file__).resolve().parent.parent


# Utilities to call existing CLI scripts ---------------------------------------


def run_workflow(
    image: Path,
    output_dir: Path,
    *,
    smooth: bool,
    measure_error: bool,
    border_mode: str
) -> Dict:
    """Execute workflow.py with the given options and return parsed JSON."""
    cmd = [
        sys.executable,
        str(ROOT / "workflow.py"),
        str(image),
        str(output_dir),
        "--proof",
        "--border-mode",
        border_mode,
    ]
    if smooth:
        cmd.append("--smooth")
    if measure_error:
        cmd.append("--measure-error")

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
