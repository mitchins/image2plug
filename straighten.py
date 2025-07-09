import os
from pathlib import Path
import argparse
import cv2
import numpy as np
from pathlib import Path
import json
import sys

# Placeholder template triangle positions for three-marker 3D correction (in mm)
TEMPLATE_MARKER_POSITIONS = {
    0: (0.0, 0.0),
    1: (100.0, 0.0),    # placeholder X distance
    2: (50.0, 86.6),    # placeholder Y for equilateral triangle
}


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


def _rectify_from_markers(img: np.ndarray, corners, ids, marker_size_mm: float, marker_positions: dict):
    """Warp the image using all detected ArUco markers.

    Uses all markers to solve a homography for better 3D correction.
    Returns warped image, homography matrix, mm_per_pixel and rotation angle.
    """

    # Prepare source and destination points
    src_pts = []
    dst_pts = []
    for i, c in enumerate(corners):
        # Try ID-based position (from config or calibration), otherwise index-based (dynamic)
        origin_mm = None
        marker_id = ids[i][0] if ids is not None else None
        if marker_id in marker_positions:
            origin_mm = marker_positions[marker_id]
        elif i in marker_positions:
            origin_mm = marker_positions[i]
        else:
            continue
        pts = c[0].astype("float32")
        src_pts.extend(pts)

        dst_pts.extend([
            [origin_mm[0], origin_mm[1]],
            [origin_mm[0] + marker_size_mm, origin_mm[1]],
            [origin_mm[0] + marker_size_mm, origin_mm[1] + marker_size_mm],
            [origin_mm[0], origin_mm[1] + marker_size_mm],
        ])

    src_pts = np.array(src_pts, dtype=np.float32)
    dst_pts = np.array(dst_pts, dtype=np.float32)

    # Find the homography matrix using RANSAC
    H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransacReprojThreshold=3.0)

    # Determine output image size based on destination points
    dst_pts_transformed = cv2.perspectiveTransform(
        np.array([[[0, 0]], [[img.shape[1], 0]], [[img.shape[1], img.shape[0]]], [[0, img.shape[0]]]], dtype=np.float32), H)
    min_x = np.min(dst_pts_transformed[:, 0, 0])
    min_y = np.min(dst_pts_transformed[:, 0, 1])
    max_x = np.max(dst_pts_transformed[:, 0, 0])
    max_y = np.max(dst_pts_transformed[:, 0, 1])

    width = int(np.ceil(max_x - min_x))
    height = int(np.ceil(max_y - min_y))

    # Apply perspective warp
    warped = cv2.warpPerspective(img, H, (width, height))

    # After warping, output pixels represent millimeters directly
    mm_per_px = 1.0

    return warped, H, mm_per_px, 0.0


"""
straighten_image:
    Perform perspective correction using ArUco markers.

    Flow paths:
      - 3d_template: If three or more markers are detected, uses a hardcoded template triangle
        in TEMPLATE_MARKER_POSITIONS to compute a full-plane homography.
      - 3d_single_marker: If exactly one marker is detected, computes a homography based on that
        marker's square to flatten and scale the image (1 px = 1 mm).
      - identity: If no markers are detected, returns the original image and logs a note.

    The selected method is returned in the 'method' field of the result metadata.
"""
def straighten_image(img, marker_size_mm=30.0, marker_positions=None, camera_matrix=None, dist_coeffs=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(gray)

    notes = []
    transform = None
    rotation_degrees = 0.0

    if ids is not None and len(corners) >= 3:
        # Three-marker template-based correction
        marker_positions = TEMPLATE_MARKER_POSITIONS
        warped, M, mm_per_pixel, angle = _rectify_from_markers(
            img, corners, ids, marker_size_mm, marker_positions
        )
        rotation_degrees = float(np.degrees(angle))
        transform = M
        method = "3d_template"
        print("[DEBUG] using 3d_template branch", file=sys.stderr)

        # Crop warped image to original image viewport
        h0, w0 = img.shape[:2]
        corners_img = np.array([[[0,0]], [[w0,0]], [[w0,h0]], [[0,h0]]], dtype=np.float32)
        pts = cv2.perspectiveTransform(corners_img, M).reshape(-1,2)
        min_x, min_y = pts.min(axis=0)
        max_x, max_y = pts.max(axis=0)
        x0, y0 = int(np.floor(min_x)), int(np.floor(min_y))
        x1, y1 = int(np.ceil(max_x)), int(np.ceil(max_y))
        x0, y0 = max(x0,0), max(y0,0)
        x1, y1 = min(x1, warped.shape[1]), min(y1, warped.shape[0])
        warped = warped[y0:y1, x0:x1]

    elif ids is not None and len(corners) >= 1:
        # Single-marker 3D correction
        ref_pts = corners[0][0].astype(np.float32)
        # Compute mm_per_pixel from marker size and detected pixel width
        pixel_width = float(np.linalg.norm(ref_pts[0] - ref_pts[1]))
        mm_per_pixel = marker_size_mm / pixel_width
        dst = np.array([
            [0, 0],
            [marker_size_mm, 0],
            [marker_size_mm, marker_size_mm],
            [0, marker_size_mm]
        ], dtype=np.float32)
        H, _ = cv2.findHomography(ref_pts, dst)
        # Compute pixel-preserving warp: H maps pixel->mm, scale back to pixel units
        # Build translation in mm
        h, w = img.shape[:2]
        corners_img = np.array([[[0,0]], [[w,0]], [[w,h]], [[0,h]]], dtype=np.float32)
        # Compute bounding box in mm coordinates
        pts_mm = cv2.perspectiveTransform(corners_img, H).reshape(-1,2)
        min_x_mm, min_y_mm = pts_mm.min(axis=0)
        max_x_mm, max_y_mm = pts_mm.max(axis=0)
        # Translation in mm to bring min to origin
        T_mm = np.array([
            [1, 0, -min_x_mm],
            [0, 1, -min_y_mm],
            [0, 0, 1]
        ], dtype=np.float32)
        # Scale mm back to pixel units
        S_px = np.array([
            [1/mm_per_pixel, 0, 0],
            [0, 1/mm_per_pixel, 0],
            [0, 0, 1]
        ], dtype=np.float32)
        # Combined homography: pixel->mm->translate->scale->pixel
        H_pix = S_px @ T_mm @ H
        # Determine output pixel extents
        pts_px = cv2.perspectiveTransform(corners_img, H_pix).reshape(-1,2)
        min_x_px, min_y_px = pts_px.min(axis=0)
        max_x_px, max_y_px = pts_px.max(axis=0)
        out_w_px = int(np.ceil(max_x_px - min_x_px))
        out_h_px = int(np.ceil(max_y_px - min_y_px))
        # Final translation to shift to positive pixel coords
        T_px = np.array([
            [1, 0, -min_x_px],
            [0, 1, -min_y_px],
            [0, 0, 1]
        ], dtype=np.float32)
        H_final = T_px @ H_pix
        warped = cv2.warpPerspective(img, H_final, (out_w_px, out_h_px))

        # Crop to valid region using transformed original corners
        h0, w0 = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w0, 0]], [[w0, h0]], [[0, h0]]], dtype=np.float32)
        pts = cv2.perspectiveTransform(corners_img, H_final).reshape(-1, 2)
        min_x, min_y = pts.min(axis=0)
        max_x, max_y = pts.max(axis=0)
        x0, y0 = int(np.floor(min_x)), int(np.floor(min_y))
        x1, y1 = int(np.ceil(max_x)), int(np.ceil(max_y))
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, warped.shape[1]), min(y1, warped.shape[0])
        warped = warped[y0:y1, x0:x1]

        transform = H_final
        method = "3d_single_marker"
        print("[DEBUG] using 3d_single_marker branch", file=sys.stderr)
    else:
        # No markers: fallback
        warped = img
        mm_per_pixel = None
        method = "identity"
        print("[DEBUG] using identity branch (no markers)", file=sys.stderr)
        notes.append("No ArUco markers detected; metric correction skipped")

    scale_x_mm_per_px = mm_per_pixel
    scale_y_mm_per_px = mm_per_pixel

    result = {
        "image": warped,
        "mm_per_pixel": mm_per_pixel,
        "scale_x_mm_per_px": scale_x_mm_per_px,
        "scale_y_mm_per_px": scale_y_mm_per_px,
        "rotation_degrees": round(rotation_degrees, 3),
        "transform": transform,
        "method": method,
        "notes": notes,
        "marker_positions": marker_positions,
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
            "scale_x_mm_per_px": res["scale_x_mm_per_px"],
            "scale_y_mm_per_px": res["scale_y_mm_per_px"],
            "rotation_degrees": res["rotation_degrees"],
            "transform": res["transform"].tolist() if hasattr(res["transform"], "tolist") else res["transform"],
            "method": res["method"],
        },
        "size_mm": size_mm,
        "notes": notes,
    }

    print(json.dumps(report))


if __name__ == "__main__":
    main()
