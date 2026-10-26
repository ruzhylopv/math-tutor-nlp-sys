"""Tag the subject and the difficulty level of the problem (the MATH categories).

The topic is one of the MATH subjects; Prealgebra, Algebra and Intermediate Algebra are in scope,
the others are not. The node only tags: what the orchestrator does with an out-of-scope subject is
not designed yet. The level is MATH's 1-5. If there is no problem, or the model fails twice, the
node changes nothing, so a topic and level from an earlier problem in the same thread survive
(a known open item, see docs/decisions.md).

Reads: problem
Writes: topic, level
Eval metric: topic accuracy / macro-F1; level accuracy and within-one;
    in_scope_accuracy; failure_rate
"""

import logging
from typing import Any

from tutor.state import Classification, TutorState
from tutor.tools import structured

logger = logging.getLogger("tutor.classify")


def classify(state: TutorState) -> dict[str, Any]:
    """Ask the model for the subject and level of the problem."""
    problem = state.get("problem", "").strip()
    if not problem:
        return {}
    result = structured.call_structured("classify", Classification, problem)
    if result is None:
        logger.warning("classify: no valid answer from the model; topic and level stay unknown")
        return {}
    return {"topic": result.topic, "level": result.level}
