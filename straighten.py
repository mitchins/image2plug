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


def _rectify_from_markers(img: np.ndarray, corners, marker_size_mm: float):
    """Warp the image using detected ArUco markers.

    The first marker defines the world orientation.
    Returns warped image, homography matrix, mm_per_pixel and rotation angle.
    """

    ref = corners[0][0].astype("float32")
    marker_width_px = np.linalg.norm(ref[0] - ref[1])
    mm_per_px = float(marker_size_mm / marker_width_px)

    # Orientation of the reference marker
    vec_x = ref[1] - ref[0]
    angle = np.arctan2(vec_x[1], vec_x[0])
    cos_a = np.cos(-angle)
    sin_a = np.sin(-angle)
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
    origin = ref[0]

    src_pts = []
    dst_pts_mm = []
    for c in corners:
        pts = c[0].astype("float32")
        for p in pts:
            src_pts.append(p)
            vec = p - origin
            rot = R @ vec
            dst_pts_mm.append(rot * mm_per_px)
    src_pts = np.array(src_pts)
    dst_pts_mm = np.array(dst_pts_mm)
    min_xy = dst_pts_mm.min(axis=0)
    dst_pts_mm -= min_xy

    dst_pts_px = dst_pts_mm / mm_per_px

    H, _ = cv2.findHomography(src_pts, dst_pts_px)

    # Transform full image corners to determine canvas size
    img_h, img_w = img.shape[:2]
    img_corners = np.array(
        [[0, 0], [img_w - 1, 0], [img_w - 1, img_h - 1], [0, img_h - 1]], dtype=np.float32
    )
    trans_corners = []
    for p in img_corners:
        vec = p - origin
        rot = R @ vec
        trans_corners.append(rot * mm_per_px - min_xy)
    trans_corners = np.array(trans_corners)
    trans_corners_px = trans_corners / mm_per_px
    width = int(np.ceil(trans_corners_px[:, 0].max()))
    height = int(np.ceil(trans_corners_px[:, 1].max()))

    warped = cv2.warpPerspective(img, H, (width, height))
    return warped, H, mm_per_px, angle


def straighten_image(img, marker_size_mm=30.0):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(gray)

    notes = []
    transform = None
    rotation_degrees = 0.0

    if ids is not None and len(corners) >= 3:
        warped, M, mm_per_pixel, angle = _rectify_from_markers(img, corners, marker_size_mm)
        rotation_degrees = float(np.degrees(angle))
        transform = np.array(M, dtype=float).tolist()
        method = "aruco_3d"
    else:
        if ids is not None and len(ids) > 0:
            c = corners[0][0]
            marker_width_px = np.linalg.norm(c[0] - c[1])
            mm_per_pixel = marker_size_mm / marker_width_px
        else:
            mm_per_pixel = None
            notes.append("Aruco marker not detected; size may be inaccurate")
        warped = img
        method = "identity"

    scale_x_mm_per_px = mm_per_pixel if mm_per_pixel is not None else None
    scale_y_mm_per_px = mm_per_pixel if mm_per_pixel is not None else None

    result = {
        "image": warped,
        "mm_per_pixel": mm_per_pixel,
        "scale_x_mm_per_px": scale_x_mm_per_px,
        "scale_y_mm_per_px": scale_y_mm_per_px,
        "rotation_degrees": round(rotation_degrees, 3),
        "transform": transform,
        "method": method,
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
            "scale_x_mm_per_px": res["scale_x_mm_per_px"],
            "scale_y_mm_per_px": res["scale_y_mm_per_px"],
            "rotation_degrees": res["rotation_degrees"],
            "transform": res["transform"],
            "method": res["method"],
        },
        "size_mm": size_mm,
        "notes": notes,
    }

    print(json.dumps(report))


if __name__ == "__main__":
    main()
