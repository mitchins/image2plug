import argparse
import json
import cv2
import numpy as np
from pathlib import Path


def order_points(pts):
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect = np.zeros((4, 2), dtype="float32")
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def detect_page_corners(gray):
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            return order_points(approx.reshape(4, 2))
    if contours:
        c = contours[0]
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        return order_points(approx.reshape(-1, 2)[:4])
    raise RuntimeError("Could not detect page corners")


def straighten_image(img, marker_size_mm=30.0):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    page_corners = detect_page_corners(gray)
    width_a = np.linalg.norm(page_corners[2] - page_corners[3])
    width_b = np.linalg.norm(page_corners[1] - page_corners[0])
    max_width = int(max(width_a, width_b))
    height_a = np.linalg.norm(page_corners[1] - page_corners[2])
    height_b = np.linalg.norm(page_corners[0] - page_corners[3])
    max_height = int(max(height_a, height_b))

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(page_corners, dst)
    warped = cv2.warpPerspective(img, M, (max_width, max_height))

    # ArUco marker detection for scale
    gray_warp = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(gray_warp)
    notes = []
    mm_per_pixel = None
    if ids is not None and len(ids) > 0:
        c = corners[0][0]
        marker_width_px = np.linalg.norm(c[0] - c[1])
        mm_per_pixel = marker_size_mm / marker_width_px
    else:
        notes.append("Aruco marker not detected; size may be inaccurate")

    result = {
        "image": warped,
        "mm_per_pixel": mm_per_pixel,
        "notes": notes,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Automatic perspective correction")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output straightened image path")
    parser.add_argument("--marker-size-mm", type=float, default=30.0, help="Size of ArUco marker in mm")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    img = cv2.imread(str(input_path))
    if img is None:
        raise SystemExit(f"Could not read input image: {input_path}")

    res = straighten_image(img, marker_size_mm=args.marker_size_mm)
    warped = res["image"]
    mm_per_pixel = res["mm_per_pixel"]
    notes = res["notes"]

    cv2.imwrite(str(output_path), warped)

    size_px = warped.shape[1], warped.shape[0]
    if mm_per_pixel is not None:
        size_mm = [round(mm_per_pixel * s, 3) for s in size_px]
    else:
        size_mm = None

    report = {
        "source": {
            "path": str(input_path),
            "size_px": [img.shape[1], img.shape[0]],
        },
        "result": {
            "path": str(output_path),
            "size_px": list(size_px),
        },
        "size_mm": size_mm,
        "notes": notes,
    }

    print(json.dumps(report))


if __name__ == "__main__":
    main()
