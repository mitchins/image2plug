import argparse
import json
from pathlib import Path

from typing import Optional, Tuple

import cv2
import numpy as np
import ezdxf


def load_metadata(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_aruco_candidate(img_crop: np.ndarray):
    try:
        aruco = cv2.aruco
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        detector = aruco.ArucoDetector(dictionary, parameters)
        corners, ids, _ = detector.detectMarkers(img_crop)
        return ids is not None and len(ids) > 0
    except AttributeError:
        return False


def detect_contours(img: np.ndarray) -> list:
    """
    Simple contour detection using global Otsu thresholding.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return contours


def contour_to_dxf(contour: np.ndarray, path: Path):
    points = contour.reshape(-1, 2)
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(points.tolist(), close=True)
    doc.saveas(str(path))


def main():
    parser = argparse.ArgumentParser(description="Detect candidate holes from a straightened image")
    parser.add_argument("image", type=Path, help="Input straightened image")
    parser.add_argument("metadata", type=Path, help="Metadata JSON from straighten.py")
    parser.add_argument("output_dir", type=Path, help="Directory to write results")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--fast", action="store_true", default=False, help="Use fast downsampled thresholding (default: False)")
    parser.add_argument("--threshold", action="store_true", default=False,
                        help="Enable binary thresholding for contour detection (default: off)")
    args = parser.parse_args()

    img = cv2.imread(str(args.image))
    if img is None:
        raise SystemExit(f"Could not read input image: {args.image}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    meta = load_metadata(args.metadata)
    mm_per_px = meta["result"].get("scale_x_mm_per_px")

    # margin around markers in pixels
    margin_mm = 20.0
    margin_px = margin_mm / mm_per_px if mm_per_px else 0

    args.output_dir.mkdir(parents=True, exist_ok=True)

    marker_boxes = []
    # Detect ArUco markers
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    detector = aruco.ArucoDetector(dictionary)
    full_corners, full_ids, _ = detector.detectMarkers(img)
    if full_ids is not None:
        for corners in full_corners:
            x_m, y_m, w_m, h_m = cv2.boundingRect(corners)
            marker_boxes.append((x_m, y_m, w_m, h_m))

    # Detect QR codes and treat as markers
    qr_detector = cv2.QRCodeDetector()
    qr_corners = None
    # Try detectMulti first (retval, corners)
    try:
        retval, corners = qr_detector.detectMulti(gray)
        if retval:
            qr_corners = corners
    except Exception:
        # Fallback to detectAndDecodeMulti
        retval, _, corners, _ = qr_detector.detectAndDecodeMulti(gray)
        if retval:
            qr_corners = corners
    if qr_corners is not None:
        for corner in qr_corners:
            x_q, y_q, w_q, h_q = cv2.boundingRect(corner.astype(int))
            marker_boxes.append((x_q, y_q, w_q, h_q))

    # Use fast mode unless debug is enabled or --fast is set
    if args.fast:
        fast_mode = True
    elif args.debug:
        fast_mode = False
    else:
        fast_mode = True

    # Prepare path to save thresholded image variant only if thresholding is enabled
    if args.threshold:
        threshold_debug_path = args.output_dir / "debug_threshold.png"
    else:
        threshold_debug_path = None

    contours = detect_contours(img)
    img_area = img.shape[0] * img.shape[1]

    candidates = []
    for idx, c in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        # Skip tiny contours: less than 10 mm × 10 mm
        if mm_per_px:
            width_mm = w * mm_per_px
            height_mm = h * mm_per_px
            if width_mm < 10.0 or height_mm < 10.0:
                if args.debug:
                    print(f"[DEBUG] Skipping small contour {idx}: {width_mm:.1f}×{height_mm:.1f} mm", file=sys.stderr)
                continue

        # check if contour bbox is within margin_px of any marker box
        near_marker = False
        for mx, my, mw, mh in marker_boxes:
            # compute distance in x and y between boxes
            dx = max(mx - (x + w), x - (mx + mw), 0)
            dy = max(my - (y + h), y - (my + mh), 0)
            if dx <= margin_px and dy <= margin_px:
                near_marker = True
                break

        # if not near a marker, apply area filters
        if not near_marker:
            if area < 1000:
                continue
            if area > img_area * 0.95:
                continue

        pad = 5
        x0 = max(x - pad, 0)
        y0 = max(y - pad, 0)
        x1 = min(x + w + pad, img.shape[1])
        y1 = min(y + h + pad, img.shape[0])

        crop = img[y0:y1, x0:x1]

        # Skip contour if it overlaps a marker by more than 50% area
        skip = False
        for mx, my, mw, mh in marker_boxes:
            ix0 = max(x, mx)
            iy0 = max(y, my)
            ix1 = min(x + w, mx + mw)
            iy1 = min(y + h, my + mh)
            if ix1 > ix0 and iy1 > iy0:
                inter_area = (ix1 - ix0) * (iy1 - iy0)
                marker_area = mw * mh
                if inter_area / marker_area > 0.5:
                    skip = True
                    break
        if skip:
            if args.debug:
                print(f"[DEBUG] Rejected contour {idx} overlapping marker bbox {mx},{my},{mw},{mh}")
            continue

        crop_path = args.output_dir / f"candidate_{idx}.png"
        cv2.imwrite(str(crop_path), crop)

        dxf_path = args.output_dir / f"candidate_{idx}.dxf"
        contour_to_dxf(c, dxf_path)

        if mm_per_px is not None:
            size_mm = [round(w * mm_per_px, 3), round(h * mm_per_px, 3)]
        else:
            size_mm = None
        candidates.append({
            "image_crop": str(crop_path),
            "dxf_path": str(dxf_path),
            "bbox": [int(x), int(y), int(w), int(h)],
            "size": size_mm,
        })

        if args.debug:
            print(f"[DEBUG] Accepted candidate {idx}, bbox {x},{y},{w},{h}, size {size_mm}")

    # In single-marker mode, keep only the candidate nearest to the marker center
    if len(marker_boxes) == 1 and candidates:
        # Compute marker center
        mx, my, mw, mh = marker_boxes[0]
        marker_cx = mx + mw / 2.0
        marker_cy = my + mh / 2.0
        # Compute candidate center distances
        def dist_to_marker(cand):
            x, y, w, h = cand["bbox"]
            cx = x + w / 2.0
            cy = y + h / 2.0
            return (cx - marker_cx)**2 + (cy - marker_cy)**2
        # Sort and keep only closest
        candidates = sorted(candidates, key=dist_to_marker)
        if args.debug:
            print(f"[DEBUG] Single-marker: selecting closest candidate {candidates[0]['bbox']}", file=sys.stderr)
        candidates = [candidates[0]]

    summary = {"candidates": candidates}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
