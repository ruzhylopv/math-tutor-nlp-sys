"""Shared data shapes: TutorState and the pydantic models used inside it.

Single source of truth for state fields. Design: docs/architecture.md and
docs/plans/design/2026-10-25-tutor-state-outline.md.
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Operation = Literal[
    "expand", "rearrange", "factor", "zero-product", "substitute", "square", "other"
]
# narrows: the line shrinks the solution set to exactly the original problem's own solution set
# (rejecting an extraneous root). Any other narrowing is not_valid.
Relation = Literal["equivalent", "implies", "narrows", "not_valid", "unparsable"]
Action = Literal["ask", "diagnose", "hint", "reply"]
ErrorType = Literal[
    "algebraic_transformation",
    "omission_extraneous_root",
    "reasoning_result_mismatch",
    "other",
]
Stage = Literal["new_message", "diagnosed", "hinted"]
Topic = Literal[
    "Prealgebra",
    "Algebra",
    "Intermediate Algebra",
    "Geometry",
    "Number Theory",
    "Counting & Probability",
    "Precalculus",
]
IN_SCOPE_TOPICS: frozenset[str] = frozenset({"Prealgebra", "Algebra", "Intermediate Algebra"})


class Step(BaseModel):
    """One line of the student's attempt, split into claim and justification."""

    claim: str
    justification: str = ""
    justification_claim: str | None = None
    operation: Operation = "other"


class StepVerdict(BaseModel):
    """SymPy's verdict on one step. Step numbers are 1-based; step 1 follows the problem."""

    step_index: int = Field(ge=1)
    relation: Relation
    justification_claims_ok: bool | None = None
    check_holds: bool | None = (
        None  # for a check line (a closed statement): does it hold? else None
    )
    notes: str = ""


class ParsedInput(BaseModel):
    """What `parse_input` extracts from the student's raw message."""

    problem: str | None = None
    steps: list[Step] = Field(default_factory=list)


class Classification(BaseModel):
    """What `classify` returns: the MATH subject and the MATH difficulty level (1 easiest)."""

    topic: Topic
    level: int = Field(ge=1, le=5)


class ErrorContext(BaseModel):
    """The wrong step, copied at diagnosis time so `hint` does not depend on `student_steps`.

    `parse_input` clears `student_steps` on a message without working (a question after a
    diagnosis), and `focus_step` indexes into them, so `hint` reads this instead.
    """

    step_number: int = Field(ge=1)
    before: str  # the line before the wrong step; the problem for step 1
    after: str  # the claim the student wrote at the wrong step
    correct_steps: list[str] = Field(default_factory=list)  # the claims before it, for praise


class HintText(BaseModel):
    """What `hint` asks the model for: the hint, as text for the student."""

    text: str = Field(min_length=1)


class HintRubric(BaseModel):
    """The eval judge's grades for one hint (see src/tutor/prompts/hint_judge.md)."""

    praises_correct_work: bool  # acknowledges what was right, or encourages when nothing was
    socratic: bool  # leads the student to find the fix instead of stating it
    on_target: bool  # points at the wrong step and the idea behind the mistake
    fits_level: bool  # as direct as the level allows, no more and no less
    reveals_answer: bool  # states the corrected line or the final answer


class Decision(BaseModel):
    """The orchestrator's structured decision for a new student message."""

    action: Action
    reason: str
    reply_text: str | None = None


class Misconception(BaseModel):
    """A misconception from the catalogue, with its retrieval score."""

    id: str
    description: str
    topic: str
    score: float


Category = Literal[
    "signs_negatives",
    "distribution",
    "like_terms_order",
    "fractions",
    "exponents_powers",
    "solving_equations",
    "squaring_extraneous",
    "quadratics",
    "factoring",
    "radicals",
    "absolute_value",
    "inequalities",
    "rational_expressions",
]


class CatalogueEntry(BaseModel):
    """One misconception in the hand-written catalogue (`src/tutor/data/misconceptions.json`)."""

    id: str = Field(pattern=r"^M\d{3}$")
    description: str = Field(min_length=10)  # describes what the student does or believes
    category: Category
    topic: Literal["Prealgebra", "Algebra", "Intermediate Algebra"]  # the in-scope subjects
    correct_rule: str = Field(min_length=1)
    example: str = Field(pattern=r".+ -> .+")  # "previous line -> what the student wrote"


class LearnerProfile(BaseModel):
    """What the learner DB knows about a student (`tools/learner_db.get_profile`)."""

    # topics with recorded mistakes, most first
    weak_topics: list[str] = Field(default_factory=list)
    # misconception id -> times seen
    misconception_counts: dict[str, int] = Field(default_factory=dict)


class MisconceptionRecord(BaseModel):
    """One misconception diagnosed in an attempt, as `record_attempt` stores it."""

    misconception_id: str
    error_type: ErrorType | None = None
    focus_step: int | None = None


class TutorState(TypedDict, total=False):
    """Graph state. Every node returns only the fields it changed."""

    messages: Annotated[list[AnyMessage], add_messages]
    student_id: str
    problem: str
    student_steps: list[Step]
    topic: Topic | None  # None after a new problem, until `classify` runs again
    level: int | None
    is_correct: bool
    step_verdicts: list[StepVerdict]
    first_error_step: int | None
    focus_step: int | None
    error_context: ErrorContext | None
    error_type: ErrorType | None
    misconception_candidates: list[Misconception]
    misconception: Misconception | None
    hint_level: int  # 1-4, capped (see docs/architecture.md)
    hint_text: str
    hint_retries: int
    stage: Stage
    next_action: Action
    reply_text: str
    turns: int
    hints_used: int
    misconceptions_seen: list[str]
    learner_profile: LearnerProfile
