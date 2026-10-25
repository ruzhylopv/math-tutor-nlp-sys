"""Eval stub for `retrieve`. The dataset and the metrics are defined in M4."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # run as a script from any folder

from evals.runner import run_eval_stub  # noqa: E402

if __name__ == "__main__":
    run_eval_stub("retrieve", "M4", __doc__ or "retrieve")
