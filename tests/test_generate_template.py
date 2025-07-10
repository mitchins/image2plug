import subprocess
from pathlib import Path
from PIL import Image


def test_generate_template_default(tmp_path):
    out = tmp_path / "template.png"
    subprocess.run([
        "python",
        "scripts/generate_template.py",
        "-o",
        str(out),
    ], check=True)
    assert out.exists()
    img = Image.open(out)
    assert img.size == (2480, 3508)  # A4 at 300 DPI
