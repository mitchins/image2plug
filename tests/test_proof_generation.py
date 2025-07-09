import subprocess
from pathlib import Path


def test_proof_generation(tmp_path):
    proof_dir = tmp_path / "proof"
    output_dir = tmp_path / "out"
    subprocess.run([
        "python",
        "workflow.py",
        "assets/reference_image_us_letter.png",
        str(output_dir),
        "--proof",
        str(proof_dir),
    ], check=True)

    assert (proof_dir / "index.html").exists()
