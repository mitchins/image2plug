#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import shutil

from proofing import ProofingReport


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout


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
    args = parser.parse_args()

    out_dir = args.output_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        straightened = out_dir / "straightened.png"
        meta_json = out_dir / "meta.json"
        phase1_out = run(["python", "straighten.py", str(args.image), str(straightened)])
        meta_json.write_text(phase1_out)
        phase1 = json.loads(phase1_out)

        cand_dir = out_dir / "candidates"
        phase2_out = run(["python", "detect_candidates.py", str(straightened), str(meta_json), str(cand_dir)])
        phase2 = json.loads(phase2_out)

        if args.proof:
            report = ProofingReport(out_dir, copy_assets=False)
            report.record({
                "name": args.image.stem,
                "source_image": str(args.image),
                "phase1": phase1,
                "phase2": phase2,
            })
            report.write()

        summary = {
            "straighten": phase1,
            "candidates": phase2,
        }
        print(json.dumps(summary))
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
