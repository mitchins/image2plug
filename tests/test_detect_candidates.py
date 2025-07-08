import json
import subprocess
from pathlib import Path


def _load_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {}

def test_detect_candidates_on_reference(tmp_path, proof_recorder):
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
    phase1 = _load_json(res1.stdout)

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

    # Verify one of the candidates closely matches the expected star position
    expected_bbox = [740, 1230, 480, 480]  # ±10 pixels margin
    tolerance = 10

    found = False
    for cand in data['candidates']:
        bbox = cand.get("bbox", [0, 0, 0, 0])
        if all(abs(b - e) <= tolerance for b, e in zip(bbox, expected_bbox)):
            found = True
            break

    assert found, f"No candidate matched expected bbox {expected_bbox}"

    proof_recorder({
        'name': 'test_detect_candidates_on_reference',
        'source_image': str(input_img),
        'phase1': phase1,
        'phase2': data,
    })
