import json
import subprocess
from pathlib import Path
import ezdxf


def _load_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {}


def _assert_scad_files_exist(candidates):
    for cand in candidates:
        assert Path(cand['scad_path']).exists()

def test_detect_candidates_on_reference(tmp_path, proof_recorder):
    input_img = Path('assets/reference_image_us_letter.png')
    corrected = tmp_path / 'corrected.png'
    meta_json = tmp_path / 'meta.json'

    # run phase 1
    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)
    phase1 = _load_json(res1.stdout)

    # run phase 2
    output_dir = tmp_path / 'candidates'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert 'candidates' in data
    assert len(data['candidates']) >= 1
    _assert_scad_files_exist(data['candidates'])

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


def test_detect_candidates_on_a4_template(tmp_path, proof_recorder):
    # Use the A4 printed reference image
    input_img = Path('assets/reference_image_a4_printed.jpeg')
    corrected = tmp_path / 'corrected_a4.png'
    meta_json = tmp_path / 'meta_a4.json'

    # Phase 1: straighten
    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)
    phase1 = _load_json(res1.stdout)

    # Phase 2: detect candidates
    output_dir = tmp_path / 'candidates_a4'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert 'candidates' in data
    assert len(data['candidates']) >= 1

    # Expected bbox from integration
    expected = [1356, 1584, 839, 843]
    # Allow 1% margin of error
    diffs = [
        abs(b - e) <= max(1, int(e * 0.01))
        for b, e in zip(data['candidates'][0]['bbox'], expected)
    ]
    assert all(diffs), f"A4 candidate bbox {data['candidates'][0]['bbox']} differs from expected {expected} by more than 1%"

    proof_recorder({
        'name': 'test_detect_candidates_on_a4_template',
        'source_image': str(input_img),
        'phase1': phase1,
        'phase2': data,
    })


def test_detect_candidates_on_sony_macro(tmp_path, proof_recorder):
    # Single-marker variant shot with Sony A7IV + Sigma Macro 90mm
    input_img = Path('assets/reference_image_a4_printed_macro.jpeg')
    corrected = tmp_path / 'corrected_sony.png'
    meta_json = tmp_path / 'meta_sony.json'

    # Phase 1: straighten (single-marker)
    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)
    phase1 = _load_json(res1.stdout)

    # Phase 2: detect candidates
    output_dir = tmp_path / 'candidates_sony'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert 'candidates' in data and data['candidates'], "No candidates found for Sony macro image"
    _assert_scad_files_exist(data['candidates'])

    # Expected bbox for the single-marker case
    expected = [2392, 2820, 1468, 1472]
    # Allow 1% margin of error
    diffs = [
        abs(b - e) <= max(1, int(e * 0.01))
        for b, e in zip(data['candidates'][0]['bbox'], expected)
    ]
    assert all(diffs), f"Sony macro bbox {data['candidates'][0]['bbox']} differs from expected {expected} by more than 1%"

    proof_recorder({
        'name': 'test_detect_candidates_on_sony_macro',
        'source_image': str(input_img),
        'phase1': phase1,
        'phase2': data,
    })

def test_detect_candidates_on_iphone_proraw_35mm(tmp_path, proof_recorder):
    # iPhone ProRAW, 35mm wide lens
    input_img = Path('assets/reference_image_a4_printed_pro_raw_35mm_wide_lens.jpeg')
    corrected = tmp_path / 'corrected_iphone_raw.png'
    meta_json = tmp_path / 'meta_iphone_raw.json'

    # Phase 1: straighten (single-marker)
    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)
    phase1 = _load_json(res1.stdout)

    # Phase 2: detect candidates
    output_dir = tmp_path / 'candidates_iphone_raw'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert 'candidates' in data and data['candidates'], "No candidates found for iPhone ProRAW 35mm image"
    _assert_scad_files_exist(data['candidates'])
    assert len(data['candidates']) == 1, "Expected exactly one candidate for iPhone ProRAW 35mm image"

    # Expected bbox for the single-marker case
    expected = [1482, 1790, 1174, 1178]
    # Allow 1% margin of error
    diffs = [
        abs(b - e) <= max(1, int(e * 0.01))
        for b, e in zip(data['candidates'][0]['bbox'], expected)
    ]
    assert all(diffs), f"iPhone ProRAW 35mm bbox {data['candidates'][0]['bbox']} differs from expected {expected} by more than 1%"

    proof_recorder({
        'name': 'test_detect_candidates_on_iphone_proraw_35mm',
        'source_image': str(input_img),
        'phase1': phase1,
        'phase2': data,
    })


def test_detect_candidates_with_smoothing(tmp_path, proof_recorder):
    input_img = Path('assets/reference_image_us_letter.png')
    corrected = tmp_path / 'corrected.png'
    meta_json = tmp_path / 'meta.json'

    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)

    output_dir = tmp_path / 'candidates_smooth'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir), '--smooth'],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert data['candidates']

    dxf_file = Path(data['candidates'][0]['dxf_path'])
    doc = ezdxf.readfile(str(dxf_file))
    poly = list(doc.modelspace().query('LWPOLYLINE'))[0]
    points = list(poly.get_points())
    assert len(points) <= 250

    proof_recorder({
        'name': 'test_detect_candidates_with_smoothing',
        'source_image': str(input_img),
        'phase1': json.loads(res1.stdout),
        'phase2': data,
    })


def test_detect_candidates_mse(tmp_path):
    input_img = Path('assets/reference_image_us_letter.png')
    corrected = tmp_path / 'corrected.png'
    meta_json = tmp_path / 'meta.json'

    res1 = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(corrected)],
        capture_output=True,
        text=True,
        check=True,
    )
    meta_json.write_text(res1.stdout)

    output_dir = tmp_path / 'candidates_error'
    res2 = subprocess.run(
        ['python', 'detect_candidates.py', str(corrected), str(meta_json), str(output_dir), '--smooth', '--measure-error'],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res2.stdout)
    assert data['candidates']
    assert 'mse' in data['candidates'][0]
    assert data['candidates'][0]['mse'] is not None


def test_border_mode_effects(tmp_path):
    import cv2
    import numpy as np
    # create blurred circle image
    img = np.full((200, 200, 3), 255, dtype=np.uint8)
    cv2.circle(img, (100, 100), 60, (0, 0, 0), -1)
    img = cv2.GaussianBlur(img, (21, 21), 0)
    img_path = tmp_path / "fuzzy.png"
    cv2.imwrite(str(img_path), img)

    meta = {"result": {"scale_x_mm_per_px": 1.0}}
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta))

    # baseline bbox from thresholded mask
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, base_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    base_contours, _ = cv2.findContours(base_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bx, by, bw, bh = cv2.boundingRect(base_contours[0])

    results = {}
    for mode in ["tight", "inside", "outside"]:
        out_dir = tmp_path / f"out_{mode}"
        res = subprocess.run([
            'python', 'detect_candidates.py', str(img_path), str(meta_path), str(out_dir),
            '--border-mode', mode
        ], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        assert data['border_mode'] == mode
        assert data['candidates']
        results[mode] = data['candidates'][0]['bbox']

    tight = results['tight']
    inside = results['inside']
    outside = results['outside']

    # inside bbox should lie within base bbox
    assert inside[0] >= bx and inside[1] >= by
    assert inside[0] + inside[2] <= bx + bw
    assert inside[1] + inside[3] <= by + bh

    # outside bbox should contain base bbox
    assert outside[0] <= bx and outside[1] <= by
    assert outside[0] + outside[2] >= bx + bw
    assert outside[1] + outside[3] >= by + bh

    # tight bbox should be close to base bbox (within 1px)
    diff = [abs(t - b) for t, b in zip(tight, [bx, by, bw, bh])]
    assert all(d <= 1 for d in diff)

