"""Shared helpers for the per-component eval scripts in evals/scripts/.

Dataset paths, JSONL loading, the --split flag and the result file. The result file layout follows
the run-eval skill: evals/results/<component>/<timestamp>_<git-hash>.json. Dataset formats are
defined by each component, not here.
"""

import argparse
import hashlib
import json
import logging
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("eval")

EVALS_DIR = Path(__file__).resolve().parent
DATASETS_DIR = EVALS_DIR / "datasets"
RESULTS_DIR = EVALS_DIR / "results"
SPLITS = ("dev", "test")


def setup_logging() -> None:
    """Plain message-only logging for eval scripts."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_split(description: str | None, argv: Sequence[str] | None = None) -> str:
    """Parse --split. Defaults to dev; test is only for the final reported numbers."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--split", choices=SPLITS, default="dev")
    return str(parser.parse_args(argv).split)


def dataset_path(component: str, split: str) -> Path:
    """Where a component's dataset for a split lives: datasets/<split>/<component>.jsonl.

    The layout is our convention (CLAUDE.md fixes only the dev/ and test/ split folders).
    """
    return DATASETS_DIR / split / f"{component}.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read one JSON object per non-empty line."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def git_hash() -> str:
    """Short hash of the repo's current commit, or "nogit" if it cannot be read.

    A missing hash must not lose the metrics of a finished eval run.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=EVALS_DIR,
        )
    except (subprocess.CalledProcessError, OSError):
        return "nogit"
    return out.stdout.strip()


def file_hash(path: Path) -> str:
    """Short sha256 of a file, used to record which prompt produced a result."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def write_result(
    component: str,
    split: str,
    n_examples: int,
    metrics: Mapping[str, float],
    *,
    model_name: str | None = None,
    prompt_path: Path | None = None,
    results_dir: Path | None = None,
    commit: str | None = None,
) -> Path:
    """Write the result file for one eval run and return its path.

    LLM nodes must pass `model_name` and `prompt_path` (the run-eval skill requires both in the
    result); deterministic nodes leave them out and the file records null.
    """
    commit = commit or git_hash()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "component": component,
        "split": split,
        "n_examples": n_examples,
        "metrics": dict(metrics),
        "model_name": model_name,
        "prompt_hash": file_hash(prompt_path) if prompt_path else None,
        "git_hash": commit,
        "timestamp": now.isoformat(),
    }
    out_dir = (results_dir or RESULTS_DIR) / component
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_{commit}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def run_eval_stub(
    component: str, milestone: str, description: str | None, argv: Sequence[str] | None = None
) -> None:
    """Body of an eval script whose dataset and metrics do not exist yet.

    Reports a missing dataset and invents no labels; if a dataset appears first it fails loudly.
    """
    setup_logging()
    split = parse_split(description, argv)
    path = dataset_path(component, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    raise NotImplementedError(f"Metrics for {component} are not implemented yet ({milestone}).")
