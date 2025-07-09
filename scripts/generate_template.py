import argparse
import os
from pathlib import Path
from typing import Tuple

import cv2
from PIL import Image
import qrcode

PAPER_SIZES = {
    "A4": (210.0, 297.0),
    "letter": (215.9, 279.4),
}


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def generate_template(
    out_path: Path,
    paper: str = "A4",
    dpi: int = 300,
    marker_size_mm: float = 30.0,
    margin_mm: float = 10.0,
    include_qr: bool = False,
) -> Tuple[float, float]:
    if paper not in PAPER_SIZES:
        raise ValueError(f"Unsupported paper size: {paper}")

    width_mm, height_mm = PAPER_SIZES[paper]
    width_px = mm_to_px(width_mm, dpi)
    height_px = mm_to_px(height_mm, dpi)
    img = Image.new("RGB", (width_px, height_px), "white")

    marker_size_px = mm_to_px(marker_size_mm, dpi)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    markers = []
    for mid in range(3):
        m = cv2.aruco.generateImageMarker(dictionary, mid, marker_size_px)
        m = cv2.cvtColor(m, cv2.COLOR_GRAY2RGB)
        markers.append(Image.fromarray(m))

    margin_px = mm_to_px(margin_mm, dpi)
    base_y = height_px - margin_px - marker_size_px // 2
    left_x = margin_px + marker_size_px // 2
    right_x = width_px - margin_px - marker_size_px // 2
    top_y = margin_px + marker_size_px // 2
    center_x = width_px // 2

    positions = [
        (left_x - marker_size_px // 2, base_y - marker_size_px // 2),
        (right_x - marker_size_px // 2, base_y - marker_size_px // 2),
        (center_x - marker_size_px // 2, top_y - marker_size_px // 2),
    ]

    for pos, mk in zip(positions, markers):
        img.paste(mk, (int(pos[0]), int(pos[1])))

    h_mm = (right_x - left_x) * 25.4 / dpi
    v_mm = (base_y - top_y) * 25.4 / dpi

    if include_qr:
        qr_data = f"{h_mm:.2f},{v_mm:.2f}"
        qr = qrcode.QRCode(border=0)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = qr_img.resize((marker_size_px, marker_size_px), Image.LANCZOS)
        qr_pos = (center_x - marker_size_px // 2, base_y - marker_size_px // 2 - marker_size_px - margin_px)
        qr_pos = (max(0, int(qr_pos[0])), max(0, int(qr_pos[1])))
        img.paste(qr_img, qr_pos)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".pdf":
        img.save(out_path, "PDF", resolution=dpi)
    else:
        img.save(out_path, dpi=(dpi, dpi))
    return h_mm, v_mm


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a printable marker template")
    parser.add_argument("-o", "--output", default="template_a4.pdf", help="Output file path (.png or .pdf)")
    parser.add_argument("--paper", choices=PAPER_SIZES.keys(), default="A4", help="Paper size")
    parser.add_argument("--dpi", type=int, default=300, help="Output resolution")
    parser.add_argument("--marker-size-mm", type=float, default=30.0, help="Marker size in mm")
    parser.add_argument("--margin-mm", type=float, default=10.0, help="Page margin in mm")
    parser.add_argument("--qr", action="store_true", help="Include QR code with distances")
    args = parser.parse_args()

    generate_template(Path(args.output), args.paper, args.dpi, args.marker_size_mm, args.margin_mm, args.qr)


if __name__ == "__main__":
    main()
