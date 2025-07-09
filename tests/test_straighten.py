import numpy as np
import json
import subprocess
from pathlib import Path


def test_straighten_when_perfect_us_letter_image(tmp_path):
    input_img = Path('assets/reference_image_us_letter.png')
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

    print(f"Detected size: {size_mm[0]} mm × {size_mm[1]} mm")

    # Expected size for US Letter paper (8.5" x 11"), allowing for some margin of error
    EXPECTED_WIDTH_MM = 216
    EXPECTED_HEIGHT_MM = 279
    TOLERANCE_MM = 10  # Allow for framing/cropping and straightening variations

    try:
        assert abs(size_mm[0] - EXPECTED_WIDTH_MM) <= TOLERANCE_MM, f"Width {size_mm[0]} mm outside expected range"
        assert abs(size_mm[1] - EXPECTED_HEIGHT_MM) <= TOLERANCE_MM, f"Height {size_mm[1]} mm outside expected range"
    except AssertionError as e:
        print(f"[DEBUG] Rotation: {data['result'].get('rotation_degrees')}")
        print(f"[DEBUG] Scale X (mm/px): {data['result'].get('scale_x_mm_per_px')}")
        print(f"[DEBUG] Scale Y (mm/px): {data['result'].get('scale_y_mm_per_px')}")
        print(f"[DEBUG] Notes: {data.get('notes')}")
        raise e


def test_straighten_when_perfect_a4_image(tmp_path):
    input_img = Path('assets/reference_image_a4.png')
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

    print(f"Detected size: {size_mm[0]} mm × {size_mm[1]} mm")

    # Expected size for A4 paper (210 mm x 297 mm), allowing for some margin of error
    EXPECTED_WIDTH_MM = 210
    EXPECTED_HEIGHT_MM = 297
    TOLERANCE_MM = 10  # Allow for framing/cropping and straightening variations

    try:
        assert abs(size_mm[0] - EXPECTED_WIDTH_MM) <= TOLERANCE_MM, f"Width {size_mm[0]} mm outside expected range"
        assert abs(size_mm[1] - EXPECTED_HEIGHT_MM) <= TOLERANCE_MM, f"Height {size_mm[1]} mm outside expected range"
    except AssertionError as e:
        print(f"[DEBUG] Rotation: {data['result'].get('rotation_degrees')}")
        print(f"[DEBUG] Scale X (mm/px): {data['result'].get('scale_x_mm_per_px')}")
        print(f"[DEBUG] Scale Y (mm/px): {data['result'].get('scale_y_mm_per_px')}")
        print(f"[DEBUG] Notes: {data.get('notes')}")
        raise e


def test_straighten_when_a4_3d_image(tmp_path):
    input_img = Path('assets/reference_image_a4_3d_printed.jpeg')
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
    assert data['result'].get('method') == 'aruco_3d'
    assert data['result'].get('transform') is not None
    size_mm = data['size_mm']
    assert size_mm is not None
    # size may vary depending on marker placement, but for aruco_3d method, scale should be exactly 1.0
    assert data['result']['scale_x_mm_per_px'] == 1.0
    assert data['result']['scale_y_mm_per_px'] == 1.0

    # Verify that the homography is not the identity (i.e., a meaningful transform was applied)
    transform = np.array(data['result']['transform'], dtype=float)
    assert transform.shape == (3, 3)
    # Should not be an identity matrix
    assert not np.allclose(transform, np.eye(3), atol=1e-6)

    # Ensure the straightened image dimensions are not too small compared to the original
    orig_w, orig_h = data['source']['size_px']
    new_w, new_h   = data['result']['size_px']
    assert new_w >= 0.75 * orig_w, f"Result width {new_w} less than 75% of original {orig_w}"
    assert new_h >= 0.75 * orig_h, f"Result height {new_h} less than 75% of original {orig_h}"
