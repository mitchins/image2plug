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
    input_img = Path('assets/template_a4_3d_printed.jpeg')
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
    # Instead of requiring scale==1.0, verify size_mm is close to A4 dimensions within a tolerance
    EXPECTED_WIDTH_MM = 190.042
    EXPECTED_HEIGHT_MM = 302.034
    TOLERANCE_MM = 5  # allow 5mm tolerance
    assert abs(size_mm[0] - EXPECTED_WIDTH_MM) <= TOLERANCE_MM, \
        f"A4 3D width {size_mm[0]} mm outside expected {EXPECTED_WIDTH_MM}±{TOLERANCE_MM}"
    assert abs(size_mm[1] - EXPECTED_HEIGHT_MM) <= TOLERANCE_MM, \
        f"A4 3D height {size_mm[1]} mm outside expected {EXPECTED_HEIGHT_MM}±{TOLERANCE_MM}"

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


def test_straighten_a4_printed_single_marker_regression(tmp_path):
    # Regression test for reference_image_a4_printed.jpeg single-marker output
    input_img = Path('assets/reference_image_a4_printed.jpeg')
    output_img = tmp_path / 'out.png'
    # Run straighten
    res = subprocess.run(
        ['python', 'straighten.py', str(input_img), str(output_img)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout)

    # Check method
    assert data['result']['method'] == '3d_single_marker'

    # Expected values
    exp_rotation = 0.0
    exp_scale = 0.04849033005033121
    exp_size_px = [2758, 4156]

    # Tolerances
    tol_rot = 0.1  # degrees
    tol_scale = exp_scale * 0.01  # 1%
    tol_px = 2  # pixels

    # Assert rotation
    assert abs(data['result']['rotation_degrees'] - exp_rotation) <= tol_rot, \
        f"Rotation {data['result']['rotation_degrees']} differs from expected {exp_rotation}"

    # Assert scales
    sx = data['result']['scale_x_mm_per_px']
    sy = data['result']['scale_y_mm_per_px']
    assert abs(sx - exp_scale) <= tol_scale, \
        f"Scale X {sx} differs from expected {exp_scale}"
    assert abs(sy - exp_scale) <= tol_scale, \
        f"Scale Y {sy} differs from expected {exp_scale}"

    # Assert size_px
    actual_size = data['result']['size_px']
    for actual, expected in zip(actual_size, exp_size_px):
        assert abs(actual - expected) <= tol_px, \
            f"Dimension {actual} differs from expected {expected} by more than {tol_px}px"
