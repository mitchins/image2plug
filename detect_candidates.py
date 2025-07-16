import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import ezdxf
from scipy.interpolate import splprep, splev


def load_metadata(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def detect_marker_boxes(img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Detect marker bounding boxes in the image using ArUco markers.
    QR code detection is included as an experimental/alternative method.
    Returns a list of bounding boxes (x, y, w, h).
    """
    marker_boxes = []

    # Primary production method: ArUco marker detection
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    detector = aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(img)
    if ids is not None:
        for c in corners:
            x, y, w, h = cv2.boundingRect(c)
            marker_boxes.append((x, y, w, h))

    # Experimental/alternative: QR code detection
    qr_detector = cv2.QRCodeDetector()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    qr_corners = None
    try:
        retval, corners = qr_detector.detectMulti(gray)
        if retval:
            qr_corners = corners
    except Exception:
        retval, _, corners, _ = qr_detector.detectAndDecodeMulti(gray)
        if retval:
            qr_corners = corners
    if qr_corners is not None:
        for corner in qr_corners:
            x, y, w, h = cv2.boundingRect(corner.astype(int))
            marker_boxes.append((x, y, w, h))

    return marker_boxes


def detect_contours(img: np.ndarray) -> List[np.ndarray]:
    """
    Detect contours in the image using global Otsu thresholding.
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


def smooth_contour(
    contour: np.ndarray,
    *,
    num_points: int = 200,
    smooth_factor: float = 0.5,
) -> np.ndarray:
    """Return a smoothed version of *contour* using a B-spline fit."""
    pts = contour.reshape(-1, 2)
    if len(pts) < 3:
        return contour
    tck, _ = splprep([pts[:, 0], pts[:, 1]], s=smooth_factor, per=True)
    u_new = np.linspace(0, 1, num_points)
    out = np.array(splev(u_new, tck)).T
    return out.reshape(-1, 1, 2).astype(np.float32)


def contour_to_dxf(contour: np.ndarray, path: Path, *, smooth: bool = False) -> np.ndarray:
    if smooth:
        contour = smooth_contour(contour)
    points = contour.reshape(-1, 2)
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(points.tolist(), close=True)
    doc.saveas(str(path))
    return contour


def dxf_to_scad(dxf_path: Path, scad_path: Path, height: float) -> None:
    """Generate a simple OpenSCAD script extruding the DXF profile."""
    content = f"linear_extrude(height = {height}) import(\"{dxf_path.name}\");\n"
    scad_path.write_text(content)


def contour_mse(original: np.ndarray, fitted: np.ndarray) -> float:
    """Return the mean squared distance between two contours."""
    orig_pts = original.reshape(-1, 2).astype(float)
    fit_pts = fitted.reshape(-1, 2).astype(float)
    err = 0.0
    for pt in fit_pts:
        dist = cv2.pointPolygonTest(original, (pt[0], pt[1]), True)
        err += dist ** 2
    for pt in orig_pts:
        dist = cv2.pointPolygonTest(fitted, (pt[0], pt[1]), True)
        err += dist ** 2
    return err / (len(orig_pts) + len(fit_pts))


def filter_candidates(
    contours: List[np.ndarray],
    marker_boxes: List[Tuple[int, int, int, int]],
    mm_per_px: Optional[float],
    img_shape: Tuple[int, int, int],
    debug: bool = False
) -> List[dict]:
    """
    Filter contours to identify candidate holes, considering proximity to markers,
    size thresholds, and overlap with markers.
    Returns a list of candidate dictionaries with image crop paths, DXF paths, bounding boxes, and sizes.
    """
    margin_mm = 20.0
    margin_px = margin_mm / mm_per_px if mm_per_px else 0
    img_area = img_shape[0] * img_shape[1]
    candidates = []

    for idx, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)

        # Skip contours smaller than 10mm x 10mm if scale is known
        if mm_per_px is not None:
            width_mm = w * mm_per_px
            height_mm = h * mm_per_px
            if width_mm < 10.0 or height_mm < 10.0:
                if debug:
                    print(f"[DEBUG] Skipping small contour {idx}: {width_mm:.1f}×{height_mm:.1f} mm", file=sys.stderr)
                continue

        # Check if contour bbox is near any marker box within margin_px
        near_marker = False
        for mx, my, mw, mh in marker_boxes:
            dx = max(mx - (x + w), x - (mx + mw), 0)
            dy = max(my - (y + h), y - (my + mh), 0)
            if dx <= margin_px and dy <= margin_px:
                near_marker = True
                break

        # Apply area filters if not near a marker
        if not near_marker:
            if area < 1000:
                continue
            if area > img_area * 0.95:
                continue

        # Skip contour if overlapping any marker by more than 50% area
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
            if debug:
                print(f"[DEBUG] Skipping contour {idx} due to overlap with marker", file=sys.stderr)
            continue

        # Prepare crop and DXF paths
        pad = 5
        x0 = max(x - pad, 0)
        y0 = max(y - pad, 0)
        x1 = min(x + w + pad, img_shape[1])
        y1 = min(y + h + pad, img_shape[0])

        candidates.append({
            "contour": contour,
            "bbox": (x, y, w, h),
            "crop_coords": (y0, y1, x0, x1),
        })

    return candidates


def select_closest_candidate(
    candidates: List[dict],
    marker_box: Tuple[int, int, int, int],
    debug: bool = False
) -> List[dict]:
    """
    Select the candidate closest to the center of the single marker box.
    Returns a list containing only the closest candidate.
    """
    mx, my, mw, mh = marker_box
    marker_cx = mx + mw / 2.0
    marker_cy = my + mh / 2.0

    def dist_to_marker(cand: dict) -> float:
        x, y, w, h = cand["bbox"]
        cx = x + w / 2.0
        cy = y + h / 2.0
        return (cx - marker_cx) ** 2 + (cy - marker_cy) ** 2

    candidates_sorted = sorted(candidates, key=dist_to_marker)
    if debug and candidates_sorted:
        print(f"[DEBUG] Single-marker: selecting closest candidate {candidates_sorted[0]['bbox']}", file=sys.stderr)
    return [candidates_sorted[0]] if candidates_sorted else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect candidate holes from a straightened image")
    parser.add_argument("image", type=Path, help="Input straightened image")
    parser.add_argument("metadata", type=Path, help="Metadata JSON from straighten.py")
    parser.add_argument("output_dir", type=Path, help="Directory to write results")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument(
        "--smooth",
        action="store_true",
        help="Regress contours to smooth vector shape before DXF export",
    )
    parser.add_argument(
        "--measure-error",
        action="store_true",
        help="Calculate mean squared error when using --smooth",
    )
    parser.add_argument(
        "--extrude-height",
        type=float,
        default=10.0,
        help="Extrusion height for generated OpenSCAD files (mm)",
    )
    args = parser.parse_args()

    # Step 1: Load image and metadata
    img = cv2.imread(str(args.image))
    if img is None:
        raise SystemExit(f"Could not read input image: {args.image}")
    meta = load_metadata(args.metadata)
    mm_per_px = meta["result"].get("scale_x_mm_per_px")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Step 2: Detect markers (primary: ArUco; alternative: QR codes)
    marker_boxes = detect_marker_boxes(img)
    if args.debug:
        print(f"[DEBUG] Detected {len(marker_boxes)} marker(s)", file=sys.stderr)

    # Step 3: Detect contours
    contours = detect_contours(img)
    if args.debug:
        print(f"[DEBUG] Detected {len(contours)} contours", file=sys.stderr)

    # Step 4: Filter candidates based on markers and size
    filtered_candidates = filter_candidates(contours, marker_boxes, mm_per_px, img.shape, debug=args.debug)

    # Step 5: In single-marker scenario, select closest candidate
    if len(marker_boxes) == 1:
        filtered_candidates = select_closest_candidate(filtered_candidates, marker_boxes[0], debug=args.debug)

    # Step 6: Output results
    candidates_output = []
    for idx, candidate in enumerate(filtered_candidates):
        contour = candidate["contour"]
        x, y, w, h = candidate["bbox"]
        y0, y1, x0, x1 = candidate["crop_coords"]
        crop = img[y0:y1, x0:x1]

        crop_path = args.output_dir / f"candidate_{idx}.png"
        cv2.imwrite(str(crop_path), crop)

        dxf_path = args.output_dir / f"candidate_{idx}.dxf"
        used_contour = contour_to_dxf(contour, dxf_path, smooth=args.smooth)

        scad_path = args.output_dir / f"candidate_{idx}.scad"
        dxf_to_scad(dxf_path, scad_path, args.extrude_height)

        size_mm = [round(w * mm_per_px, 3), round(h * mm_per_px, 3)] if mm_per_px is not None else None

        cand_record = {
            "image_crop": str(crop_path),
            "dxf_path": str(dxf_path),
            "scad_path": str(scad_path),
            "bbox": [int(x), int(y), int(w), int(h)],
            "size": size_mm,
        }
        if args.measure_error and args.smooth:
            mse = contour_mse(contour, used_contour)
            cand_record["regression_mse"] = round(float(mse), 5)

        candidates_output.append(cand_record)

        if args.debug:
            print(f"[DEBUG] Accepted candidate {idx}, bbox {x},{y},{w},{h}, size {size_mm}", file=sys.stderr)

    summary = {"candidates": candidates_output}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
