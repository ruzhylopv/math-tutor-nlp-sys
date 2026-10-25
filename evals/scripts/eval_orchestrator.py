"""Eval stub for `orchestrator`. The dataset and the metrics are defined in M6."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.runner import dataset_path, parse_split  # noqa: E402

COMPONENT = "orchestrator"
logger = logging.getLogger(f"eval_{COMPONENT}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    split = parse_split(__doc__ or COMPONENT)
    path = dataset_path(COMPONENT, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    raise NotImplementedError("Metrics are not implemented yet (M6).")


if __name__ == "__main__":
    main()
