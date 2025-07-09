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
    
    # Get the convex hull of the transformed corners
    hull = cv2.convexHull(original_corners_transformed.astype(np.float32))
    hull_points = hull.reshape(-1, 2)
    
    # Create a mask of the valid region (inside the convex hull)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [hull_points.astype(np.int32)], 255)
    
    # Find the largest inscribed rectangle using a more aggressive approach
    # Start with the full image bounds and shrink inward until we find a valid rectangle
    
    best_area = 0
    best_rect = (0, 0, w, h)  # Start with full image
    
    # Try different rectangle positions and sizes more systematically
    # Use a coarse-to-fine search with smaller steps for better coverage
    
    step_size = max(1, min(w, h) // 100)  # Adaptive step size
    
    for top in range(0, h // 2, step_size):
        for left in range(0, w // 2, step_size):
            for bottom in range(h - 1, h // 2, -step_size):
                for right in range(w - 1, w // 2, -step_size):
                    if right <= left or bottom <= top:
                        continue
                    
                    # Check if all four corners of this rectangle are inside the hull
                    rect_corners = np.array([
                        [left, top], [right, top],
                        [right, bottom], [left, bottom]
                    ], dtype=np.float32)
                    
                    all_inside = True
                    for corner in rect_corners:
                        if cv2.pointPolygonTest(hull_points, tuple(corner), False) < 0:
                            all_inside = False
                            break
                    
                    if all_inside:
                        area = (right - left) * (bottom - top)
                        if area > best_area:
                            best_area = area
                            best_rect = (left, top, right - left, bottom - top)
                            # Early termination if we find a very large rectangle
                            if area > 0.8 * w * h:
                                return best_rect
    
    # If the systematic search didn't find anything good, try a different approach
    # Binary search approach for each edge
    if best_area < 0.1 * w * h:  # If we only found a very small rectangle
        # Find the largest rectangle by binary search on each edge
        def is_rect_valid(x1, y1, x2, y2):
            if x2 <= x1 or y2 <= y1:
                return False
            corners = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
            return all(cv2.pointPolygonTest(hull_points, tuple(corner), False) >= 0 for corner in corners)
        
        # Binary search for optimal bounds
        def binary_search_bound(low, high, axis, direction):
            """Binary search for the optimal boundary"""
            best = low if direction > 0 else high
            while high - low > 1:
                mid = (low + high) // 2
                if axis == 'x':
                    if direction > 0:  # searching for right edge
                        test_valid = is_rect_valid(0, 0, mid, h)
                    else:  # searching for left edge
                        test_valid = is_rect_valid(mid, 0, w, h)
                else:  # axis == 'y'
                    if direction > 0:  # searching for bottom edge
                        test_valid = is_rect_valid(0, 0, w, mid)
                    else:  # searching for top edge
                        test_valid = is_rect_valid(0, mid, w, h)
                
                if test_valid:
                    best = mid
                    if direction > 0:
                        low = mid
                    else:
                        high = mid
                else:
                    if direction > 0:
                        high = mid
                    else:
                        low = mid
            return best
        
        # Find bounds more precisely
        hull_min_x = max(0, int(np.min(hull_points[:, 0])))
        hull_max_x = min(w, int(np.max(hull_points[:, 0])))
        hull_min_y = max(0, int(np.min(hull_points[:, 1])))
        hull_max_y = min(h, int(np.max(hull_points[:, 1])))
        
        # Use the hull bounds as a starting point and try to expand
        best_rect = (hull_min_x, hull_min_y, hull_max_x - hull_min_x, hull_max_y - hull_min_y)
        
        # Try to expand each edge incrementally
        x, y, rect_w, rect_h = best_rect
        
        # Expand left
        while x > 0:
            if is_rect_valid(x - 1, y, x + rect_w, y + rect_h):
                x -= 1
                rect_w += 1
            else:
                break
        
        # Expand right
        while x + rect_w < w:
            if is_rect_valid(x, y, x + rect_w + 1, y + rect_h):
                rect_w += 1
            else:
                break
        
        # Expand up
        while y > 0:
            if is_rect_valid(x, y - 1, x + rect_w, y + rect_h):
                y -= 1
                rect_h += 1
            else:
                break
        
        # Expand down
        while y + rect_h < h:
            if is_rect_valid(x, y, x + rect_w, y + rect_h + 1):
                rect_h += 1
            else:
                break
        
        best_rect = (x, y, rect_w, rect_h)
    
    return best_rect

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

def straighten_image(img, marker_size_mm=30.0, marker_positions=None, camera_matrix=None, dist_coeffs=None):
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
        
        # Improved cropping: find largest rectangle without black borders
        h0, w0 = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w0, 0]], [[w0, h0]], [[0, h0]]], dtype=np.float32)
        pts = cv2.perspectiveTransform(corners_img, M).reshape(-1, 2)
        
        # Use the improved cropping function
        x, y, w, h = find_largest_rotated_crop(warped, pts)
        warped = warped[y:y+h, x:x+w]
        
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
        h, w = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]], dtype=np.float32)
        
        # Compute bounding box in mm coordinates
        pts_mm = cv2.perspectiveTransform(corners_img, H).reshape(-1, 2)
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
        pts_px = cv2.perspectiveTransform(corners_img, H_pix).reshape(-1, 2)
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
        
        # Improved cropping for single marker case
        h0, w0 = img.shape[:2]
        corners_img = np.array([[[0, 0]], [[w0, 0]], [[w0, h0]], [[0, h0]]], dtype=np.float32)
        pts = cv2.perspectiveTransform(corners_img, H_final).reshape(-1, 2)
        
        # Use the improved cropping function
        x, y, w, h = find_largest_rotated_crop(warped, pts)
        warped = warped[y:y+h, x:x+w]
        
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