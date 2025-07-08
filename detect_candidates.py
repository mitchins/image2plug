import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import ezdxf


def load_metadata(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def detect_contours(img: np.ndarray):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
    args = parser.parse_args()

    img = cv2.imread(str(args.image))
    if img is None:
        raise SystemExit(f"Could not read input image: {args.image}")

    meta = load_metadata(args.metadata)
    mm_per_px = meta["result"].get("scale_x_mm_per_px")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    contours = detect_contours(img)
    img_area = img.shape[0] * img.shape[1]

    candidates = []
    for idx, c in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
        area = cv2.contourArea(c)
        if area < 1000:
            continue
        if area > img_area * 0.95:
            continue
        x, y, w, h = cv2.boundingRect(c)
        pad = 5
        x0 = max(x - pad, 0)
        y0 = max(y - pad, 0)
        x1 = min(x + w + pad, img.shape[1])
        y1 = min(y + h + pad, img.shape[0])

        crop = img[y0:y1, x0:x1]
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

    summary = {"candidates": candidates}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
