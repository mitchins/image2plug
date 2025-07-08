import os
import json
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
        # generate previews
        if ezdxf is not None:
            for cand in data.get("phase2", {}).get("candidates", []):
                dxf_path = Path(cand.get("dxf_path", ""))
                if dxf_path.exists():
                    preview = dxf_path.with_suffix(".png")
                    try:
                        doc = ezdxf.readfile(str(dxf_path))
                        matplotlib.qsave(doc.modelspace(), str(preview))
                        cand["preview_png"] = str(preview)
                    except Exception:
                        cand["preview_png"] = None
        results.append(data)
    return record


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if not getattr(config, "proof_enabled", False):
        return
    results = getattr(config, "_proof_results", [])
    proof_dir = Path("tests/proof")
    proof_dir.mkdir(exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(proof_dir)))
    template = env.get_template("template.html")
    html = template.render(tests=results)
    (proof_dir / "index.html").write_text(html)
    session.config.pluginmanager.get_plugin("terminalreporter").write(
        f"\nProof report written to {proof_dir/'index.html'}\n"
    )
