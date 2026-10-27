"""Replay a multi-turn scenario (evals/scenarios/*.yaml) through the real main graph.

Each turn is one `invoke` with the same `thread_id` on a SQLite checkpointer, so `hint_level` and
`misconceptions_seen` carry over like in the app. The learner DB is a temporary file, seeded with
the scenario's past attempts. Which model answers is the caller's business: the eval script runs
the real one, the unit tests script `structured.call_structured`.

A turn records the nodes visited, the hint level, the published reply, whether a published hint
leaks (`tools/leakage`) and the misconception the diagnosis found, and lists what differed from the
turn's expectations. A wrong misconception is listed apart (retrieval is not the orchestrator's
job) so that a retrieval miss does not fail the routing.
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import yaml
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from tutor.graph import build_main_graph, new_turn
from tutor.state import MisconceptionRecord
from tutor.tools.checkpointer import sqlite_checkpointer
from tutor.tools.leakage import find_leaks
from tutor.tools.learner_db import record_attempt

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


class PastAttempt(BaseModel):
    topic: str
    misconceptions: list[str] = Field(default_factory=list)


class Expect(BaseModel):
    visited: list[str] = Field(default_factory=list)  # nodes that must run in this turn
    not_visited: list[str] = Field(default_factory=list)
    hint_level: int | None = None  # the level of the hint published this turn
    reply_contains: list[str] = Field(default_factory=list)
    misconception: str | None = None  # the id the diagnosis should find


class Turn(BaseModel):
    student: str
    expect: Expect = Field(default_factory=Expect)


class Scenario(BaseModel):
    name: str
    description: str
    student_id: str
    past_attempts: list[PastAttempt] = Field(default_factory=list)
    turns: list[Turn]


class TurnResult(BaseModel):
    student: str
    visited: list[str]
    reply: str
    hint_level: int | None  # only when a hint was published this turn
    leaks: list[str]
    misconception: str | None
    failures: list[str]  # routing, level and reply expectations that did not hold
    misconception_ok: bool | None  # None when the turn expects no misconception


class ScenarioResult(BaseModel):
    name: str
    turns: list[TurnResult]

    @property
    def hints_given(self) -> int:
        return sum(1 for turn in self.turns if turn.hint_level is not None)


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def scenario_paths() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.yaml"))


def _run_turn(graph: Any, scenario: Scenario, turn: Turn, config: RunnableConfig) -> TurnResult:
    visited: list[str] = []
    for _, update in graph.stream(
        new_turn(scenario.student_id, turn.student),
        config,
        stream_mode="updates",
        subgraphs=True,
    ):
        visited.extend(update)
    state = graph.get_state(config).values
    reply = state.get("reply_text", "")
    hinted = "hint" in visited and bool(reply)
    context = state.get("error_context")
    leaks = (
        find_leaks(reply, state.get("problem", ""), context.before if context else "")
        if hinted
        else []
    )
    misconception = state.get("misconception")
    found = misconception.id if misconception and "retrieve" in visited else None

    expect = turn.expect
    failures = [f"did not visit {n}" for n in expect.visited if n not in visited]
    failures += [f"visited {n}" for n in expect.not_visited if n in visited]
    level = state.get("hint_level") if hinted else None
    if expect.hint_level is not None and level != expect.hint_level:
        failures.append(f"hint level {level}, expected {expect.hint_level}")
    failures += [f"reply lacks {w!r}" for w in expect.reply_contains if w not in reply]
    if leaks:
        failures.append(f"hint leaks: {leaks}")
    return TurnResult(
        student=turn.student,
        visited=visited,
        reply=reply,
        hint_level=level,
        leaks=leaks,
        misconception=found,
        failures=failures,
        misconception_ok=None if expect.misconception is None else found == expect.misconception,
    )


def replay(scenario: Scenario) -> ScenarioResult:
    """Run every turn of a scenario on a fresh checkpointer and a fresh learner DB."""
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "learner.db")
        for past in scenario.past_attempts:
            records = [MisconceptionRecord(misconception_id=m) for m in past.misconceptions]
            record_attempt(
                db, scenario.student_id, "past problem", past.topic, 1, 2, 1, True, records
            )
        # the orchestrator reads the DB path through load_config, which also wants the key and
        # model; unit tests that script the model have neither, so a placeholder fills the gap
        env = {"LEARNER_DB_PATH": db}
        for name in ("OPENROUTER_API_KEY", "MODEL_NAME"):
            env.setdefault(name, os.environ.get(name, "unset"))
        with mock.patch.dict(os.environ, env):
            graph = build_main_graph(sqlite_checkpointer(str(Path(tmp) / "checkpoint.db")))
            config: RunnableConfig = {"configurable": {"thread_id": scenario.name}}
            results = [_run_turn(graph, scenario, turn, config) for turn in scenario.turns]
    return ScenarioResult(name=scenario.name, turns=results)
