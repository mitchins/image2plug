import json
import subprocess
from pathlib import Path

def test_detect_candidates_on_reference(tmp_path):
    input_img = Path('assets/reference_image_us_letter.png')
    straightened = tmp_path / 'straightened.png'
    meta_json = tmp_path / 'meta.json'

    # run phase 1
    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(straightened)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)

    # run phase 2
    output_dir = tmp_path / 'candidates'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(straightened), str(meta_json), str(output_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert 'candidates' in data
    assert len(data['candidates']) >= 1
    first = data['candidates'][0]
    assert Path(first['image_crop']).exists()
    assert Path(first['dxf_path']).exists()
