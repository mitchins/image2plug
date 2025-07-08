import argparse
import cv2
import os
from PIL import Image


def generate_marker(out_path: str, size_mm: float = 30.0, dpi: int = 300) -> None:
    marker_length_pixels = int(round(size_mm / 25.4 * dpi))
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 0, marker_length_pixels)
    marker_rgb = cv2.cvtColor(marker, cv2.COLOR_GRAY2RGB)
    img = Image.fromarray(marker_rgb)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, dpi=(dpi, dpi))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a 30mm ArUco marker.")
    parser.add_argument(
        "-o", "--output", default="assets/aruco_marker_30mm.png", help="Path to save the marker image.",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="Image resolution in DPI. Used for physical print size.",
    )
    parser.add_argument(
        "--size-mm", type=float, default=30.0, help="Marker size in millimetres.",
    )
    args = parser.parse_args()
    generate_marker(args.output, args.size_mm, args.dpi)


if __name__ == "__main__":
    main()
