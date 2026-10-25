"""Eval stub for `parse_input`. The dataset and the metrics are defined in M3."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # run as a script from any folder

from evals.runner import run_eval_stub  # noqa: E402

if __name__ == "__main__":
    run_eval_stub("parse_input", "M3", __doc__ or "parse_input")
