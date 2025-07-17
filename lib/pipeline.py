import json
import cv2
from pathlib import Path
from typing import Dict, Any, List

from straighten import straighten_image
from detect_candidates import (
    detect_marker_boxes,
    detect_contours,
    filter_candidates,
    select_closest_candidate,
    contour_to_dxf,
    dxf_to_scad,
    contour_mse,
)


def run_pipeline(
    image_path: Path,
    out_dir: Path,
    *,
    smooth: bool = False,
    measure_error: bool = False,
    border_mode: str = "tight",
) -> Dict[str, Any]:
    """Run the full image2plug pipeline on *image_path*.

    Results and intermediate files are written to *out_dir*.
    Returns a dictionary mirroring the CLI JSON output.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    phase1 = straighten_image(img)
    corrected = phase1["image"]
    corrected_path = out_dir / "corrected.png"
    cv2.imwrite(str(corrected_path), corrected)

    size_px = [corrected.shape[1], corrected.shape[0]]
    mm_per_px = phase1.get("scale_x_mm_per_px")
    meta = {
        "source": {
            "path": str(image_path),
            "size_px": [img.shape[1], img.shape[0]],
        },
        "result": {
            "path": str(corrected_path),
            "size_px": size_px,
            "scale_x_mm_per_px": mm_per_px,
            "scale_y_mm_per_px": mm_per_px,
            "rotation_degrees": phase1.get("rotation_degrees", 0.0),
            "transform": (
                phase1.get("transform").tolist()
                if hasattr(phase1.get("transform"), "tolist")
                else phase1.get("transform")
            ),
            "method": phase1.get("method"),
        },
        "size_mm": [round(mm_per_px * s, 3) for s in size_px] if mm_per_px else None,
        "notes": phase1.get("notes", []),
    }

    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta))

    cand_dir = out_dir / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)

    marker_boxes = detect_marker_boxes(corrected)
    contours = detect_contours(corrected, border_mode=border_mode)
    filtered = filter_candidates(contours, marker_boxes, mm_per_px, corrected.shape)
    if len(marker_boxes) == 1:
        filtered = select_closest_candidate(filtered, marker_boxes[0])

    candidates_out: List[Dict[str, Any]] = []
    for idx, cand in enumerate(filtered):
        contour = cand["contour"]
        x, y, w, h = cand["bbox"]
        y0, y1, x0, x1 = cand["crop_coords"]
        crop = corrected[y0:y1, x0:x1]

        crop_path = cand_dir / f"candidate_{idx}.png"
        cv2.imwrite(str(crop_path), crop)

        dxf_path = cand_dir / f"candidate_{idx}.dxf"
        used_contour = contour_to_dxf(contour, dxf_path, smooth=smooth)

        scad_path = cand_dir / f"candidate_{idx}.scad"
        dxf_to_scad(dxf_path, scad_path, 10.0)

        size_mm = (
            [round(w * mm_per_px, 3), round(h * mm_per_px, 3)] if mm_per_px else None
        )

        mse_val = None
        if measure_error and smooth:
            try:
                mse_val = contour_mse(contour, used_contour)
            except Exception:
                mse_val = None

        candidates_out.append(
            {
                "image_crop": str(crop_path),
                "dxf_path": str(dxf_path),
                "scad_path": str(scad_path),
                "bbox": [int(x), int(y), int(w), int(h)],
                "size": size_mm,
                **({"mse": mse_val} if mse_val is not None else {}),
            }
        )

    return {
        "corrected": meta,
        "candidates": {
            "border_mode": border_mode,
            "candidates": candidates_out,
        },
    }
