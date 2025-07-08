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
