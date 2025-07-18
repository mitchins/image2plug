#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import shutil
import sys
from subprocess import CalledProcessError

from proofing import ProofingReport

CORRECTED_IMAGE = "corrected.png"

def run(cmd):
    """Run a subprocess command and return its stdout.

    Raises CalledProcessError if the command fails. This helper is used by
    :func:`run_workflow` and the CLI entry point.
    """

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(e.returncode)


def run_workflow(
    image: Path,
    output_dir: Path,
    *,
    proof: bool = False,
    extrude_height: float = 10.0,
    smooth: bool = False,
    measure_error: bool = False,
    border_mode: str = "tight",
):
    """Execute the full workflow pipeline.

    This function encapsulates the logic used by the ``workflow.py`` CLI and is
    imported by the job daemon. Keeping all of the processing steps in this
    single function ensures there is only one source of truth for the workflow
    behaviour.
    """

    out_dir = Path(output_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    corrected = out_dir / CORRECTED_IMAGE
    meta_json = out_dir / "meta.json"

    phase1_out = run(["python", "straighten.py", str(image), str(corrected)])
    meta_json.write_text(phase1_out)
    phase1 = json.loads(phase1_out)

    cand_dir = out_dir / "candidates"
    phase2_out = run([
        "python",
        "detect_candidates.py",
        str(corrected),
        str(meta_json),
        str(cand_dir),
        "--extrude-height",
        str(extrude_height),
        "--border-mode",
        border_mode,
        *( ["--smooth"] if smooth else [] ),
        *( ["--measure-error"] if measure_error else [] ),
    ])
    phase2 = json.loads(phase2_out)

    # No threshold preview - feature was never implemented
    preview_image = None

    if proof:
        report = ProofingReport(out_dir, copy_assets=True)
        report.record(
            {
                "name": image.stem,
                "source_image": str(image),
                "corrected_image": CORRECTED_IMAGE,
                "preview_image": preview_image,
                "options": {
                    "smooth": smooth,
                    "measure_error": measure_error,
                    "extrude_height": extrude_height,
                    "border_mode": border_mode,
                },
                "phase1": phase1,
                "phase2": phase2,
            }
        )
        report.write()

    summary = {
        "corrected": phase1,
        "candidates": phase2,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Run the full image2plug pipeline")
    parser.add_argument("image", type=Path, help="Input image")
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=Path("results"),
        help="Directory to place results (default: results)",
    )
    parser.add_argument(
        "--proof",
        action="store_true",
        help="Generate an HTML proof report in the output directory",
    )
    parser.add_argument(
        "--extrude-height",
        type=float,
        default=10.0,
        help="Extrusion height for generated OpenSCAD files (mm)",
    )
    parser.add_argument(
        "--smooth",
        action="store_true",
        help="Regress contours to smooth vector shapes",
    )
    parser.add_argument(
        "--measure-error",
        action="store_true",
        help="Calculate MSE between smoothed and raw contours",
    )
    parser.add_argument(
        "--border-mode",
        choices=["tight", "inside", "outside"],
        default="tight",
        help=(
            "Controls border interpretation when detecting candidates"
        ),
    )
    args = parser.parse_args()

    out_dir = args.output_dir
    try:
        summary = run_workflow(
            args.image,
            out_dir,
            proof=args.proof,
            extrude_height=args.extrude_height,
            smooth=args.smooth,
            measure_error=args.measure_error,
            border_mode=args.border_mode,
        )
        print(json.dumps(summary))
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
