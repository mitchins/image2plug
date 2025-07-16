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
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(e.returncode)


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
        help="Calculate mean squared error when using --smooth",
    )
    args = parser.parse_args()

    out_dir = args.output_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        corrected = out_dir / CORRECTED_IMAGE
        meta_json = out_dir / "meta.json"
        phase1_out = run(["python", "straighten.py", str(args.image), str(corrected)])
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
            str(args.extrude_height),
            *( ["--smooth"] if args.smooth else [] ),
            *( ["--measure-error"] if args.measure_error else [] ),
        ])
        phase2 = json.loads(phase2_out)

        # Determine preview image for proofing (threshold variant)
        threshold_img = out_dir / "candidates" / "debug_threshold.png"
        preview_image = str(threshold_img.relative_to(out_dir)) if threshold_img.exists() else None

        if args.proof:
            report = ProofingReport(out_dir, copy_assets=False)
            report.record({
                "name": args.image.stem,
                "source_image": str(args.image),
                "corrected_image": CORRECTED_IMAGE,
                "preview_image": preview_image,
                "phase1": phase1,
                "phase2": phase2,
            })
            report.write()

        summary = {
            "corrected": phase1,
            "candidates": phase2,
        }
        print(json.dumps(summary))
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
