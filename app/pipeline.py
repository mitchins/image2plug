from pathlib import Path
import json
import subprocess
from typing import Dict


def run_workflow(image: Path, output_dir: Path, options: Dict[str, bool]) -> None:
    """Run the CLI workflow with given options."""
    cmd = [
        "python",
        "workflow.py",
        str(image),
        str(output_dir),
        "--proof",
        "--border-mode",
        options.get("border_mode", "tight"),
    ]
    if options.get("smooth"):
        cmd.append("--smooth")
    if options.get("measure_error"):
        cmd.append("--measure-error")
    subprocess.run(cmd, check=True)
