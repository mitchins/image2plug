"""
straighten.py

This module performs metric perspective correction of an input image using a printed marker template generated
by generate_template.py. The template consists of three 40×40 mm ArUco markers arranged in a triangle:
  - Two markers at the bottom-left and bottom-right of the page.
  - One marker at the top-center of the page.
If called with --qr, generate_template.py also adds two QR codes:
  - Encodes the horizontal and vertical distances (h_mm, v_mm) between the bottom markers and the top marker.
  - Each QR code is a 40×40 mm square placed adjacent to its corresponding marker.

Key assumptions:
  - All markers (ArUco and QR) are exactly marker_size_mm (default 30 or 40 mm) on each side.
  - The QR payload is a comma-separated "X,Y" string in millimeters relative to the origin ArUco at (0,0).
  - The ArUco marker with ID 0 defines the origin (0,0) in the template coordinate system.
  - Three non-collinear markers (one ArUco + two QR-derived positions) provide sufficient correspondences
    to solve a full homography for 1 px = 1 mm metric mapping.
  - If only a single ArUco marker is detected, the code falls back to a single-marker correction that flattens and scales based on that marker alone.

Usage:
  Call `straighten_image(img, marker_size_mm, marker_positions, ...)` to detect markers, merge QR data,
  and compute a homography that warps the image into a metric coordinate frame. Falls back to single-marker
  or identity flows when fewer markers are detected. It explicitly supports single-marker correction when only one marker is found.
"""
import os
from pathlib import Path
import argparse
import cv2
import numpy as np
from pathlib import Path
import json
import sys


# QR detection pre-processing (tunable)
QR_HIST_EQUALIZE = True
QR_ADAPTIVE_THRESH = True
QR_BLUR_KERNEL = (5, 5)
QR_THRESH_BLOCKSIZE = 51
QR_THRESH_C = 5


# --- QR Preprocessing Helper ---
def preprocess_qr(gray: np.ndarray, mode: str) -> np.ndarray:
    """
    Preprocess a grayscale image for QR detection.
    mode: 'raw', 'eq', 'thresh', or 'all'
    """
    proc = gray
    if mode in ("eq", "all"):
        proc = cv2.equalizeHist(proc)
    if mode in ("thresh", "all"):
        blur = cv2.GaussianBlur(proc, QR_BLUR_KERNEL, 0)
        proc = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            QR_THRESH_BLOCKSIZE,
            QR_THRESH_C
        )
    return proc

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

def find_largest_rotated_crop(image, original_corners_transformed):
    """
    Find the largest axis-aligned rectangle that fits inside the transformed image
    and excludes black border regions created by rotation.
    
    Args:
        image: The warped image
        original_corners_transformed: The corners of the original image after transformation
    
    Returns:
        (x, y, w, h): Crop rectangle coordinates
    """
    h, w = image.shape[:2]

    # Get convex hull of transformed corners and build a mask
    hull = cv2.convexHull(original_corners_transformed.astype(np.float32)).reshape(-1, 2).astype(np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [hull], 255)
    mask = mask.astype(bool)

    # Use histogram-based maximal rectangle in binary matrix (O(hw))
    heights = np.zeros(w, dtype=int)
    best_area = 0
    best_rect = (0, 0, 0, 0)

    for i in range(h):
        # update histogram heights
        row = mask[i]
        heights = heights + 1
        heights[~row] = 0

        # stack algorithm to find largest rectangle in histogram
        stack = []
        for j in range(w + 1):
            curr_h = heights[j] if j < w else 0
            while stack and curr_h < heights[stack[-1]]:
                height = heights[stack.pop()]
                width = j if not stack else j - stack[-1] - 1
                area = height * width
                if area > best_area:
                    best_area = area
                    # compute rectangle coords
                    right = j
                    left = 0 if not stack else stack[-1] + 1
                    bottom = i + 1
                    top = bottom - height
                    best_rect = (left, top, width, height)
            stack.append(j)

    if best_rect[2] <= 0 or best_rect[3] <= 0:
        return 0, 0, w, h
    return best_rect

def _rectify_from_markers(img: np.ndarray, corners, ids, marker_size_mm: float, marker_positions: dict):
    """Warp the image using all detected ArUco markers.
    Uses all markers to solve a homography for better 3D correction.
    Returns warped image, homography matrix, mm_per_pixel and rotation angle.
    """
    # Order markers consistently: bottom-left, bottom-right, top for a triangle
    if len(corners) >= 3:
        centers = [c[0].mean(axis=0) for c in corners]
        idx = list(range(len(corners)))
        sorted_by_y = sorted(idx, key=lambda i: centers[i][1], reverse=True)
        bottom = sorted_by_y[:2]
        top_idx = sorted_by_y[2]
        bottom.sort(key=lambda i: centers[i][0])
        order = [bottom[0], bottom[1], top_idx]
        corners = [corners[i] for i in order]
        if ids is not None:
            ids = [ids[i] for i in order]

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
    
    # Determine output image size in mm based on destination points
    # Compute bounding box in mm
    min_x = np.min(dst_pts[:,0])
    min_y = np.min(dst_pts[:,1])
    max_x = np.max(dst_pts[:,0])
    max_y = np.max(dst_pts[:,1])
    width = max_x - min_x
    height = max_y - min_y

    # Translate mm-coordinates so bounding box starts at (0,0)
    T_mm = np.array([
        [1, 0, -min_x],
        [0, 1, -min_y],
        [0, 0, 1]
    ], dtype=np.float32)

    # Estimate pixel-per-mm scale from first marker's edge in original image
    ref_pts = corners[0][0]
    pixel_edge = np.linalg.norm(ref_pts[1] - ref_pts[0])
    px_per_mm = pixel_edge / marker_size_mm

    # Build scaling matrix to convert mm units to pixels
    S = np.array([
        [px_per_mm, 0,         0],
        [0,         px_per_mm, 0],
        [0,         0,         1]
    ], dtype=np.float32)

    # Compose the final homography for pixel warp (with mm translation)
    H_pix = S @ T_mm @ H

    # Compute output pixel dimensions
    out_w = int(np.ceil(width * px_per_mm))
    out_h = int(np.ceil(height * px_per_mm))

    # Apply perspective warp with pixel scaling
    warped = cv2.warpPerspective(img, H_pix, (out_w, out_h))

    # Return warped, H_pix, mm_per_pixel, angle (angle=0.0 for now)
    return warped, H_pix, 1/px_per_mm, 0.0

def straighten_image(img, marker_size_mm=30.0, marker_positions=None, camera_matrix=None, dist_coeffs=None, qr_mode="all"):
    """
    Perform perspective correction using ArUco markers.
    Flow paths:
      - 3d_template: If three or more markers are detected, uses a hardcoded template triangle
        in TEMPLATE_MARKER_POSITIONS to compute a full-plane homography.
      - 3d_single_marker: If exactly one marker is detected, computes a homography based on that
        marker's square to flatten and scale the image (1 px = 1 mm).
      - identity: If no markers are detected, returns the original image and logs a note.
    The selected method is returned in the 'method' field of the result metadata.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    proc_qr = preprocess_qr(gray, qr_mode)
    # Debug: save pre-processed QR image
    debug_path = Path("debug_proc_qr.png")
    cv2.imwrite(str(debug_path), proc_qr)

    # --- Marker detection ---
    # 1) Detect only ArUco origin marker (ID 0)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    corners_all, ids_all, _ = cv2.aruco.detectMarkers(gray, dictionary)
    if ids_all is not None:
        ids_all = ids_all.flatten().tolist()
    else:
        ids_all = []

    # --- Triple-ArUco A4 template mode (IDs 0,1,2) ---
    template_ids = [0, 1, 2]
    if all(id_val in ids_all for id_val in template_ids):
        # Extract corners in the order [0,1,2]
        corners_tri = [corners_all[ids_all.index(i)] for i in template_ids]
        ids_tri = [[i] for i in template_ids]
        # Known A4 template positions in mm: marker_size_mm apart
        # A4: margin 10mm, marker center offset = marker_size_mm/2
        # Horizontal half-spacing = (210 - 2*10 - marker_size_mm)/2
        half_h = (210.0 - 20.0 - marker_size_mm) / 2.0
        v = 297.0 - 10.0 - marker_size_mm/2.0  # vertical distance from origin to bottom markers
        marker_positions_template = {
            0: (0.0,        0.0),
            1: (-half_h,    v),
            2: ( half_h,    v),
        }
        # Perform rectification
        warped, M, mm_per_pixel, angle = _rectify_from_markers(
            img, corners_tri, ids_tri, marker_size_mm, marker_positions_template
        )
        rotation_degrees = float(np.degrees(angle))
        transform = M
        method = "aruco_3d"
        print("[DEBUG] using triple-ArUco A4 template branch", file=sys.stderr)

        # Validate scale consistency versus single-marker reference
        # Compute pixel-per-mm from origin marker only
        ref_pts0 = corners_tri[0][0].astype(np.float32)
        edge_px = float(np.linalg.norm(ref_pts0[1] - ref_pts0[0]))
        single_px_per_mm = edge_px / marker_size_mm
        if abs(single_px_per_mm - mm_per_pixel) / single_px_per_mm > 0.05:
            print("[DEBUG] triple-ArUco scale deviates >5%; falling back to single-marker", file=sys.stderr)
            # Fall back to single-marker correction
            method = "3d_single_marker"
            # Compute single-marker homography and warp at max resolution
            # (replicate single-marker flow here)
            # Get single-marker H_pix and warped image
            dst = np.array([
                [0, 0],
                [marker_size_mm, 0],
                [marker_size_mm, marker_size_mm],
                [0, marker_size_mm]
            ], dtype=np.float32)
            H_single, _ = cv2.findHomography(ref_pts0, dst)
            # mm bounding box
            corners_img = np.array([[[0, 0]], [[img.shape[1], 0]], [[img.shape[1], img.shape[0]]], [[0, img.shape[0]]]], dtype=np.float32)
            pts_mm = cv2.perspectiveTransform(corners_img, H_single).reshape(-1, 2)
            min_x, min_y = pts_mm.min(axis=0)
            max_x, max_y = pts_mm.max(axis=0)
            width_mm, height_mm = max_x - min_x, max_y - min_y
            # compute pixel homography
            S = np.array([[single_px_per_mm,0,0],[0,single_px_per_mm,0],[0,0,1]],dtype=np.float32)
            T_mm = np.array([[1,0,-min_x],[0,1,-min_y],[0,0,1]],dtype=np.float32)
            H_pix_sm = S @ T_mm @ H_single
            out_w = int(np.ceil(width_mm * single_px_per_mm))
            out_h = int(np.ceil(height_mm * single_px_per_mm))
            warped = cv2.warpPerspective(img, H_pix_sm, (out_w, out_h))
            transform = H_pix_sm
            mm_per_pixel = 1 / single_px_per_mm
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
                "notes": [],
                "marker_positions": marker_positions_template,
            }
            return result

        # Build and return result immediately
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
            "notes": [],
            "marker_positions": marker_positions_template,
        }
        return result

    # Keep only the origin ArUco marker (ID 0)
    origin_corners = []
    if corners_all is not None and ids_all:
        for idx, mid in enumerate(ids_all):
            if mid == 0:
                origin_corners.append(corners_all[idx])
    # Debug origin detection
    print(f"[DEBUG] ArUco origin found: {len(origin_corners)} marker(s) with ID 0", file=sys.stderr)

    # Fallback: if no ID-0 marker, but other ArUco markers exist, pick the topmost as origin
    if not origin_corners and corners_all is not None and ids_all:
        # compute centers
        centers = [c[0].mean(axis=0) for c in corners_all]
        top_idx = int(np.argmin([pt[1] for pt in centers]))
        origin_corners = [corners_all[top_idx]]
        ids = [[ids_all[top_idx]]]
        print(f"[DEBUG] Fallback ArUco origin: id={ids_all[top_idx]} center={centers[top_idx]}", file=sys.stderr)
    else:
        # maintain ids list corresponding to origin_corners
        ids = [[0]] * len(origin_corners) if origin_corners else []

    # 2) Detect QR code corners and decode (always attempt, even if decode fails)
    qr_detector = cv2.QRCodeDetector()
    retval, decoded_info, qr_corners, _ = qr_detector.detectAndDecodeMulti(proc_qr)
    qr_info = []
    if qr_corners is not None and len(qr_corners) > 0:
        for data, corner in zip(decoded_info, qr_corners):
            qr_info.append((data, corner))
    # Debug QR raw detection
    print(f"[DEBUG] QR candidates found: {len(qr_info)}", file=sys.stderr)

    # 3) Merge valid QR decodes
    corners = origin_corners.copy()
    # ids already set above (may be fallback or standard)
    marker_positions = {} if marker_positions is None else marker_positions
    qr_count = 0
    for data, corner in qr_info:
        if data:
            try:
                x_mm, y_mm = map(float, data.strip().split(","))
                synthetic_id = 1000 + qr_count
                marker_positions[synthetic_id] = (x_mm, y_mm)
                corners.append(np.array([corner], dtype=np.float32))
                ids.append([synthetic_id])
                qr_count += 1
                print(f"[DEBUG] QR decoded: id={synthetic_id}, pos=({x_mm},{y_mm})", file=sys.stderr)
            except ValueError:
                print(f"[DEBUG] QR decode invalid: '{data}'", file=sys.stderr)
        else:
            print(f"[DEBUG] QR decode failed for corners: {corner.tolist()}", file=sys.stderr)

    # Final debug summary
    print(f"[DEBUG] Total markers: origin={len(origin_corners)}, qr_valid={qr_count}, corners={len(corners)}, ids={ids}", file=sys.stderr)

    notes = []
    transform = None
    rotation_degrees = 0.0

    # Choose correction path
    if len(corners) >= 3:
        # three-marker flow
        warped, M, mm_per_pixel, angle = _rectify_from_markers(
            img, corners, ids, marker_size_mm, marker_positions
        )
        rotation_degrees = float(np.degrees(angle))
        transform = M
        method = "aruco_3d"
        print("[DEBUG] using 3d_template branch", file=sys.stderr)

        # For robustness, return the original image when the warped output is too small
        if warped.shape[1] < 0.75 * img.shape[1] or warped.shape[0] < 0.75 * img.shape[0]:
            warped = img

    elif len(corners) == 1:
        # single-marker flow
        ref_pts = corners[0][0].astype(np.float32)
        pixel_width = float(np.linalg.norm(ref_pts[0] - ref_pts[1]))
        mm_per_pixel = marker_size_mm / pixel_width
        dst = np.array([
            [0, 0],
            [marker_size_mm, 0],
            [marker_size_mm, marker_size_mm],
            [0, marker_size_mm]
        ], dtype=np.float32)
        H, _ = cv2.findHomography(ref_pts, dst)
        h, w = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]], dtype=np.float32)
        pts_mm = cv2.perspectiveTransform(corners_img, H).reshape(-1, 2)
        min_x_mm, min_y_mm = pts_mm.min(axis=0)
        max_x_mm, max_y_mm = pts_mm.max(axis=0)
        T_mm = np.array([
            [1, 0, -min_x_mm],
            [0, 1, -min_y_mm],
            [0, 0, 1]
        ], dtype=np.float32)
        S_px = np.array([
            [1/mm_per_pixel, 0, 0],
            [0, 1/mm_per_pixel, 0],
            [0, 0, 1]
        ], dtype=np.float32)
        H_pix = S_px @ T_mm @ H
        pts_px = cv2.perspectiveTransform(corners_img, H_pix).reshape(-1, 2)
        min_x_px, min_y_px = pts_px.min(axis=0)
        max_x_px, max_y_px = pts_px.max(axis=0)
        out_w_px = int(np.ceil(max_x_px - min_x_px))
        out_h_px = int(np.ceil(max_y_px - min_y_px))
        T_px = np.array([
            [1, 0, -min_x_px],
            [0, 1, -min_y_px],
            [0, 0, 1]
        ], dtype=np.float32)
        H_final = T_px @ H_pix
        warped = cv2.warpPerspective(img, H_final, (out_w_px, out_h_px))
        h0, w0 = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w0, 0]], [[w0, h0]], [[0, h0]]], dtype=np.float32)
        pts = cv2.perspectiveTransform(corners_img, H_final).reshape(-1, 2)
        x, y, w, h = find_largest_rotated_crop(warped, pts)
        warped = warped[y:y+h, x:x+w]
        transform = H_final
        method = "3d_single_marker"
        print("[DEBUG] using 3d_single_marker branch", file=sys.stderr)
    else:
        # identity
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
    parser.add_argument(
        "--qr-mode",
        choices=["raw", "eq", "thresh", "all"],
        default="raw",
        help="QR pre-processing mode: raw=no preprocess; eq=hist equalization only; thresh=adaptive threshold only; all=both"
    )
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    img = cv2.imread(str(input_path))
    if img is None:
        raise SystemExit(f"Could not read input image: {input_path}")
    
    res = straighten_image(img, marker_size_mm=args.marker_size_mm, qr_mode=args.qr_mode)
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