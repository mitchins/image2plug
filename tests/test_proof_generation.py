import subprocess
from pathlib import Path


def test_proof_generation(tmp_path):
    output_dir = tmp_path / "out"
    subprocess.run([
        "python",
        "workflow.py",
        "assets/reference_image_us_letter.png",
        str(output_dir),
        "--proof",
    ], check=True)

    assert (output_dir / "proof.html").exists()
