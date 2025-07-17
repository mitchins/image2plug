from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import os
import platform
from typing import Any, Dict

try:
    import ezdxf
    from ezdxf.addons.drawing import matplotlib
except Exception:  # pragma: no cover - optional dependency
    ezdxf = None

from jinja2 import Environment, FileSystemLoader


def _generate_scad_preview(scad: Path, preview: Path) -> bool:
    """Render a SCAD file to a PNG preview using openscad."""
    if shutil.which("openscad") is None:
        preview.touch()
        return True
    try:
        cmd = [
            "openscad",
            "--autocenter",
            "--viewall",
            "--imgsize=400,300",
            "--camera=0,0,0,45,0,0,200",
            "--render",
            "-o",
            str(preview),
            str(scad),
        ]

        if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
            cmd = ["xvfb-run", "-a"] + cmd

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
        )
        if not preview.exists():
            print(f"⚠️ Warning: OpenSCAD preview was not generated for {scad.name}")
            print("stdout:", result.stdout.decode())
            print("stderr:", result.stderr.decode())
            return False
        return True
    except Exception as e:
        print(f"❌ Error running OpenSCAD on {scad.name}: {e}")
        return False


class ProofingReport:
    """Collects pipeline results and renders an HTML proof report."""

    def __init__(self, output_dir: Path, *, copy_assets: bool = False):
        self.output_dir = Path(output_dir)
        self.copy_assets = copy_assets
        self.records = []

        if self.copy_assets:
            self.assets_dir = self.output_dir / "assets"
            self.assets_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.assets_dir = None

        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = env.get_template("proof_template.html")

    def record(self, data: Dict[str, Any]) -> None:
        """Record a pipeline run.

        The structure of *data* mirrors the dictionaries used in tests.
        """
        source_path = Path(data.get("source_image", ""))
        if source_path.exists():
            if self.copy_assets and self.assets_dir is not None:
                target_source = self.assets_dir / source_path.name
                shutil.copy(source_path, target_source)
                data["source_image"] = f"assets/{source_path.name}"
            else:
                data["source_image"] = os.path.relpath(source_path, self.output_dir)

        if ezdxf is not None:
            for cand in data.get("phase2", {}).get("candidates", []):
                dxf_path = Path(cand.get("dxf_path", ""))
                if dxf_path.exists():
                    preview = dxf_path.with_stem(
                        f"{dxf_path.stem}_2d-preview"
                    ).with_suffix(".png")
                    try:
                        doc = ezdxf.readfile(str(dxf_path))
                        matplotlib.qsave(doc.modelspace(), str(preview))
                        if self.copy_assets and self.assets_dir is not None:
                            target_preview = self.assets_dir / preview.name
                            shutil.copy(preview, target_preview)
                            cand["preview_png"] = f"assets/{preview.name}"
                        else:
                            cand["preview_png"] = os.path.relpath(
                                preview, self.output_dir
                            )
                    except Exception:  # pragma: no cover - optional rendering
                        cand["preview_png"] = None

                    if self.copy_assets and self.assets_dir is not None:
                        target_dxf = self.assets_dir / dxf_path.name
                        shutil.copy(dxf_path, target_dxf)
                        cand["dxf_file"] = f"assets/{dxf_path.name}"
                    else:
                        cand["dxf_file"] = os.path.relpath(dxf_path, self.output_dir)

                scad_path = Path(cand.get("scad_path", ""))
                if scad_path.exists():
                    if self.copy_assets and self.assets_dir is not None:
                        target_scad = self.assets_dir / scad_path.name
                        shutil.copy(scad_path, target_scad)
                        cand["scad_file"] = f"assets/{scad_path.name}"
                    else:
                        cand["scad_file"] = os.path.relpath(scad_path, self.output_dir)

                    preview_scad = scad_path.with_stem(
                        f"{scad_path.stem}_3d-preview"
                    ).with_suffix(".png")
                    if _generate_scad_preview(scad_path, preview_scad):
                        if self.copy_assets and self.assets_dir is not None:
                            target_p = self.assets_dir / preview_scad.name
                            shutil.copy(preview_scad, target_p)
                            cand["scad_preview_png"] = f"assets/{preview_scad.name}"
                        else:
                            cand["scad_preview_png"] = os.path.relpath(
                                preview_scad, self.output_dir
                            )

                crop_path = Path(cand.get("image_crop", ""))
                if crop_path.exists():
                    if self.copy_assets and self.assets_dir is not None:
                        target_crop = (
                            self.assets_dir / f"{crop_path.stem}_crop{crop_path.suffix}"
                        )
                        shutil.copy(crop_path, target_crop)
                        cand["crop_png"] = f"assets/{target_crop.name}"
                    else:
                        cand["crop_png"] = os.path.relpath(crop_path, self.output_dir)

        self.records.append(data)

    def write(self) -> Path:
        """Render the HTML report and return the path to the index file."""
        html = self.template.render(tests=self.records)
        index_path = self.output_dir / "index.html"
        index_path.write_text(html)
        # Also save raw data as JSON
        import json

        json_path = self.output_dir / "proofing_report.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({"tests": self.records}, f, indent=2)
        return index_path
