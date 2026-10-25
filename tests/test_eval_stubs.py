import runpy
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "evals" / "scripts"
STUBS = ["parse_input", "classify", "verify", "localize", "retrieve"]


@pytest.mark.parametrize("name", STUBS)
def test_stub_reports_a_missing_dataset_and_invents_nothing(
    name: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sys, "argv", [f"eval_{name}.py"])
    caplog.set_level("INFO")
    runpy.run_path(str(SCRIPTS / f"eval_{name}.py"), run_name="__main__")
    assert "missing" in caplog.text
