import runpy
import sys
from pathlib import Path

import pytest

from evals import runner

SCRIPTS = Path(__file__).resolve().parents[1] / "evals" / "scripts"
STUBS = ["parse_input", "classify", "verify", "localize", "retrieve"]


@pytest.mark.parametrize("name", STUBS)
def test_stub_reports_a_missing_dataset_and_invents_nothing(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path)  # independent of real datasets
    monkeypatch.setattr(sys, "argv", [f"eval_{name}.py"])
    caplog.set_level("INFO")
    runpy.run_path(str(SCRIPTS / f"eval_{name}.py"), run_name="__main__")
    assert "missing" in caplog.text
    assert list(tmp_path.iterdir()) == []
