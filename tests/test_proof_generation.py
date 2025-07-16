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
        "--smooth",
        "--measure-error",
    ], check=True)

    assert (output_dir / "index.html").exists()
    # Ensure that a SCAD file was generated for the candidate
    scads = list((output_dir / "candidates").glob("*.scad"))
    assert scads, "No SCAD output generated"
    # Verify the proof report links to the SCAD output
    html = (output_dir / "index.html").read_text()
    assert any(scad.name in html for scad in scads)
    # Ensure a SCAD preview image was created and referenced
    previews = list((output_dir / "candidates").glob("*_3d-preview.png"))
    assert previews, "No SCAD preview generated"
    assert any(preview.name in html for preview in previews)
    assert "MSE" in html
