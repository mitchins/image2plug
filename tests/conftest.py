import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from proofing import ProofingReport


def pytest_configure(config):
    config.proof_enabled = os.getenv("PROOF", "").lower() == "true"
    if config.proof_enabled:
        config.option.exitfirst = True
        config._proof_report = ProofingReport(Path("tests/proof"))


@pytest.fixture
def proof_recorder(request):
    report = getattr(request.config, "_proof_report", None)

    def record(data):
        if report is not None:
            report.record(data)

    return record


def pytest_sessionfinish(session, exitstatus):
    report = getattr(session.config, "_proof_report", None)
    if report is None:
        return
    index = report.write()
    session.config.pluginmanager.get_plugin("terminalreporter").write(
        f"\nProof report written to {index}\n"
    )
