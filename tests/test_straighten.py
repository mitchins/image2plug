import json
import subprocess
from pathlib import Path


def test_straighten(tmp_path):
    input_img = Path('assets/reference_image.png')
    output_img = tmp_path / 'out.png'
    result = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(output_img)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data['result']['path'] == str(output_img)
    assert Path(data['result']['path']).exists()
    size_mm = data['size_mm']
    assert size_mm is not None
    assert size_mm[0] > 100 and size_mm[1] > 100


