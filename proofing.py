from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

try:
    import ezdxf
    from ezdxf.addons.drawing import matplotlib
except Exception:  # pragma: no cover - optional dependency
    ezdxf = None

from jinja2 import Environment, FileSystemLoader


class ProofingReport:
    """Collects pipeline results and renders an HTML proof report."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / "assets"
        self.records = []

        self.assets_dir.mkdir(parents=True, exist_ok=True)
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = env.get_template("proof_template.html")

    def record(self, data: Dict[str, Any]) -> None:
        """Record a pipeline run.

        The structure of *data* mirrors the dictionaries used in tests.
        """
        source_path = Path(data.get("source_image", ""))
        if source_path.exists():
            target_source = self.assets_dir / source_path.name
            shutil.copy(source_path, target_source)
            data["source_image"] = f"assets/{source_path.name}"

        if ezdxf is not None:
            for cand in data.get("phase2", {}).get("candidates", []):
                dxf_path = Path(cand.get("dxf_path", ""))
                if dxf_path.exists():
                    preview = dxf_path.with_stem(f"{dxf_path.stem}_render").with_suffix(".png")
                    try:
                        doc = ezdxf.readfile(str(dxf_path))
                        matplotlib.qsave(doc.modelspace(), str(preview))
                        target_preview = self.assets_dir / preview.name
                        shutil.copy(preview, target_preview)
                        cand["preview_png"] = f"assets/{preview.name}"
                    except Exception:  # pragma: no cover - optional rendering
                        cand["preview_png"] = None

                    target_dxf = self.assets_dir / dxf_path.name
                    shutil.copy(dxf_path, target_dxf)
                    cand["dxf_file"] = f"assets/{dxf_path.name}"

                crop_path = Path(cand.get("image_crop", ""))
                if crop_path.exists():
                    target_crop = self.assets_dir / f"{crop_path.stem}_crop{crop_path.suffix}"
                    shutil.copy(crop_path, target_crop)
                    cand["crop_png"] = f"assets/{target_crop.name}"

        self.records.append(data)

    def write(self) -> Path:
        """Render the HTML report and return the path to the index file."""
        html = self.template.render(tests=self.records)
        index_path = self.output_dir / "index.html"
        index_path.write_text(html)
        return index_path
