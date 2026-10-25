"""Last node of the diagnosis subgraph: mark the diagnosis as finished.

Reads: (none)
Writes: stage
Eval metric: none (exempt from the eval-script rule; unit tests only)
"""

from typing import Any

from tutor.state import TutorState


def finish_diagnosis(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"stage": "diagnosed"}
