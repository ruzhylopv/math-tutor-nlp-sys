"""Export the compiled main graph (with the diagnosis subgraph expanded) to Mermaid.

Run: `uv run python scripts/draw_graph.py [--out docs/graph.mmd]`
"""

import argparse
import logging
from pathlib import Path

from tutor.graph import build_main_graph

logger = logging.getLogger("draw_graph")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "graph.mmd"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out: Path = parser.parse_args().out
    mermaid = build_main_graph().get_graph(xray=True).draw_mermaid()
    out.write_text(mermaid, encoding="utf-8")
    logger.info("Wrote %s", out)


if __name__ == "__main__":
    main()
