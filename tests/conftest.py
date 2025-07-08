import os
import json
import shutil
from pathlib import Path

import pytest

try:
    import ezdxf
    from ezdxf.addons.drawing import matplotlib
except Exception:
    ezdxf = None

from jinja2 import Environment, FileSystemLoader


def pytest_configure(config):
    config.proof_enabled = os.getenv("PROOF", "").lower() == "true"
    if config.proof_enabled:
        config.option.exitfirst = True
        config._proof_results = []


@pytest.fixture
def proof_recorder(request):
    enabled = getattr(request.config, "proof_enabled", False)
    results = getattr(request.config, "_proof_results", None)
    def record(data):
        if not enabled or results is None:
            return

        proof_assets = Path("tests/proof/assets")
        proof_assets.mkdir(parents=True, exist_ok=True)

        # Copy source image
        source_path = Path(data.get("source_image", ""))
        if source_path.exists():
            target_source = proof_assets / source_path.name
            shutil.copy(source_path, target_source)
            data["source_image"] = f"assets/{source_path.name}"

        # generate previews and copy crops
        if ezdxf is not None:
            for cand in data.get("phase2", {}).get("candidates", []):
                dxf_path = Path(cand.get("dxf_path", ""))
                if dxf_path.exists():
                    preview = dxf_path.with_stem(f"{dxf_path.stem}_render").with_suffix(".png")
                    try:
                        doc = ezdxf.readfile(str(dxf_path))
                        matplotlib.qsave(doc.modelspace(), str(preview))

                        # Copy preview into the proof assets folder
                        target_preview = proof_assets / preview.name
                        shutil.copy(preview, target_preview)
                        cand["preview_png"] = f"assets/{preview.name}"
                    except Exception:
                        cand["preview_png"] = None

                    # Copy DXF into the proof assets folder
                    target_dxf = proof_assets / dxf_path.name
                    shutil.copy(dxf_path, target_dxf)
                    cand["dxf_file"] = f"assets/{dxf_path.name}"

                # Copy raw crop into the proof assets folder
                crop_path = Path(cand.get("image_crop", ""))
                if crop_path.exists():
                    target_crop = proof_assets / f"{crop_path.stem}_crop{crop_path.suffix}"
                    shutil.copy(crop_path, target_crop)
                    cand["crop_png"] = f"assets/{target_crop.name}"

        results.append(data)
    return record


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if not getattr(config, "proof_enabled", False):
        return
    results = getattr(config, "_proof_results", [])
    proof_dir = Path("tests/proof")
    proof_dir.mkdir(exist_ok=True)
    env = Environment(loader=FileSystemLoader("tests"))
    template = env.get_template("proof_template.html")
    html = template.render(tests=results)
    (proof_dir / "index.html").write_text(html)
    session.config.pluginmanager.get_plugin("terminalreporter").write(
        f"\nProof report written to {proof_dir/'index.html'}\n"
    )
