"""What the graph panel shows about a turn: the graph with its progress, and a line per node.

Pure functions without Streamlit, so they can be tested alone. `node_details` is a whitelist: a
new state field stays hidden until it is added here. `hint_text` must never be added, because it
can hold a draft the leak check later rejects, which may contain the answer.
"""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from langchain_core.runnables.graph import Graph

START_NODE = "__start__"
END_NODE = "__end__"
INNER_END_SUFFIX = f":{END_NODE}"

IDLE = "#f3f4f6"
VISITED = "#dbeafe"
ACTIVE = "#22c55e"
FAILED = "#ef4444"
EDGE = "#9ca3af"
TAKEN_EDGE = "#2563eb"
TEXT = "#1f2937"
TEXT_ON_STRONG = "#ffffff"


@dataclass(frozen=True)
class Trace:
    """How far one turn has got. `runs` lists node paths in the order they started."""

    runs: tuple[str, ...] = ()
    active: frozenset[str] = frozenset()
    failed: frozenset[str] = frozenset()
    finished: bool = False

    def start(self, path: str) -> "Trace":
        return replace(self, runs=(*self.runs, path), active=self.active | {path})

    def finish(self, path: str, failed: bool = False) -> "Trace":
        return replace(
            self,
            active=self.active - {path},
            failed=self.failed | {path} if failed else self.failed,
        )

    def end(self, error: bool) -> "Trace":
        """The turn is over; on an error, whatever was still running is what failed."""
        return replace(
            self,
            active=frozenset(),
            failed=self.failed | self.active if error else self.failed,
            finished=not error,
        )


def node_path(namespace: tuple[str, ...], node: str) -> str:
    """A node's id in the drawn graph, for example `diagnosis:verify` (the task id is dropped)."""
    return ":".join([part.partition(":")[0] for part in namespace] + [node])


def _visible_edges(graph: Graph) -> list[tuple[str, str, bool]]:
    """(source, target, conditional), with the subgraph's inner end node joined through."""
    exits: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.source.endswith(INNER_END_SUFFIX):
            exits.setdefault(edge.source, []).append(edge.target)
    visible: list[tuple[str, str, bool]] = []
    for edge in graph.edges:
        if edge.source.endswith(INNER_END_SUFFIX):
            continue
        for target in exits.get(edge.target, [edge.target]):
            visible.append((edge.source, target, edge.conditional))
    return visible


def _name(node: str) -> str:
    return node.rpartition(":")[2].strip("_")


def _label(node: str, count: int) -> str:
    name = _name(node)
    return f"{name} ×{count}" if count > 1 else name


def _fill(node: str, trace: Trace, visited: set[str]) -> str:
    if node in trace.failed:
        return FAILED
    if node in trace.active:
        return ACTIVE
    return VISITED if node in visited else IDLE


def _node_line(node: str, trace: Trace, visited: set[str], count: int) -> str:
    fill = _fill(node, trace, visited)
    font = TEXT_ON_STRONG if fill in (ACTIVE, FAILED) else TEXT
    return f'"{node}" [label="{_label(node, count)}" fillcolor="{fill}" fontcolor="{font}"];'


def _cluster_lines(name: str, lines: list[str], trace: Trace) -> list[str]:
    color = FAILED if name in trace.failed else ACTIVE if name in trace.active else EDGE
    width = 1 if color == EDGE else 2.5
    return [
        f'subgraph "cluster_{name}" {{',
        f'label="{name}"; fontcolor="{EDGE}"; fontsize=10; style=rounded; '
        f'color="{color}"; penwidth={width};',
        *lines,
        "}",
    ]


def _walked(nodes: list[str], trace: Trace) -> tuple[list[str], set[str], set[tuple[str, str]]]:
    """(runs of drawn nodes, the nodes reached, the edges taken) so far in this turn."""
    runs = [path for path in trace.runs if path in nodes]  # drops the `diagnosis` wrapper
    visited = set(runs)
    walk = list(runs)
    if runs:
        visited.add(START_NODE)
        walk.insert(0, START_NODE)
    if trace.finished:
        visited.add(END_NODE)
        walk.append(END_NODE)
    return runs, visited, set(zip(walk, walk[1:], strict=False))


def graph_dot(graph: Graph, trace: Trace) -> str:
    """Graphviz DOT for the compiled graph (`get_graph(xray=True)`) coloured by `trace`."""
    nodes = [node for node in graph.nodes if not node.endswith(INNER_END_SUFFIX)]
    runs, visited, taken = _walked(nodes, trace)
    counts = Counter(runs)

    top: list[str] = []
    clusters: dict[str, list[str]] = {}
    for node in nodes:
        line = _node_line(node, trace, visited, counts[node])
        if ":" in node:
            clusters.setdefault(node.partition(":")[0], []).append(line)
        else:
            top.append(line)
    body = list(top)
    for name, lines in clusters.items():
        body += _cluster_lines(name, lines, trace)
    for source, target, conditional in _visible_edges(graph):
        style = "dashed" if conditional else "solid"
        if (source, target) in taken:
            body.append(
                f'"{source}" -> "{target}" [color="{TAKEN_EDGE}" penwidth=2.5 style={style}];'
            )
        else:
            body.append(f'"{source}" -> "{target}" [style={style}];')
    return "\n".join(
        [
            "digraph {",
            'rankdir=TB; bgcolor="transparent"; nodesep=0.3; ranksep=0.3;',
            'node [shape=box style="rounded,filled" fontname="sans-serif" fontsize=11 '
            "height=0.3 margin=0.08];",
            f'edge [color="{EDGE}" arrowsize=0.7];',
            *body,
            "}",
        ]
    )


class StepRecord(Protocol):
    """A finished node run, as far as the panel needs it (`ui.StepFinished` is one)."""

    @property
    def path(self) -> str: ...
    @property
    def seconds(self) -> float: ...
    @property
    def details(self) -> tuple[str, ...]: ...
    @property
    def failed(self) -> bool: ...


Edge = tuple[str, str, bool]


def _back_edges(edges: list[Edge]) -> set[tuple[str, str]]:
    """The edges that close a cycle, found by walking from the start node."""
    targets: dict[str, list[str]] = {}
    for source, target, _ in edges:
        targets.setdefault(source, []).append(target)
    back: set[tuple[str, str]] = set()
    seen: set[str] = set()
    on_path: set[str] = set()

    def walk(node: str) -> None:
        seen.add(node)
        on_path.add(node)
        for target in targets.get(node, []):
            if target in on_path:
                back.add((node, target))
            elif target not in seen:
                walk(target)
        on_path.discard(node)

    walk(START_NODE)
    return back


def _ranks(nodes: list[str], edges: list[Edge], back: set[tuple[str, str]]) -> dict[str, int]:
    """Each node's row: its longest distance from the start, ignoring the edges that loop back."""
    ranks = dict.fromkeys(nodes, 0)
    forward = [(source, target) for source, target, _ in edges if (source, target) not in back]
    for _ in nodes:
        for source, target in forward:
            ranks[target] = max(ranks[target], ranks[source] + 1)
    return ranks


def _group(node: str) -> str | None:
    return node.partition(":")[0] if ":" in node else None


def _slots(nodes: list[str], ranks: dict[str, int]) -> dict[str, float]:
    """Horizontal place in a row, centred on 0. A group takes the middle and stays in one column."""
    slots: dict[str, float] = {}
    columns: dict[str, float] = {}
    for rank in sorted(set(ranks.values())):
        row = [node for node in nodes if ranks[node] == rank]
        outer = [node for node in row if _group(node) is None]
        middle = (len(outer) + 1) // 2
        ordered = [*outer[:middle], *[n for n in row if _group(n) is not None], *outer[middle:]]
        for index, node in enumerate(ordered):
            slot = index - (len(ordered) - 1) / 2
            group = _group(node)
            slots[node] = slot if group is None else columns.setdefault(group, slot)
    return slots


def _status(node: str, trace: Trace, visited: set[str]) -> str:
    if node in trace.failed:
        return "failed"
    if node in trace.active:
        return "running"
    return "done" if node in visited else "idle"


def _group_status(name: str, members: list[str], trace: Trace, visited: set[str]) -> str:
    """A group shows the worst of its members and of the wrapper node around them."""
    statuses = [_status(node, trace, visited) for node in [name, *members]]
    return next((s for s in ("failed", "running", "done") if s in statuses), "idle")


def panel_view(graph: Graph, trace: Trace, steps: Iterable[StepRecord]) -> dict[str, Any]:
    """Everything the graph panel draws, as JSON-ready data.

    `details` come only from `node_details` through `steps`, so nothing else in the state can
    reach the page.
    """
    nodes = [node for node in graph.nodes if not node.endswith(INNER_END_SUFFIX)]
    _, visited, taken = _walked(nodes, trace)
    edges = _visible_edges(graph)
    back = _back_edges(edges)
    ranks = _ranks(nodes, edges, back)
    slots = _slots(nodes, ranks)
    runs: dict[str, list[dict[str, Any]]] = {node: [] for node in nodes}
    for step in steps:
        if step.path in runs:  # the `diagnosis` wrapper: its steps are listed
            runs[step.path].append(
                {
                    "seconds": round(step.seconds, 2),
                    "failed": step.failed,
                    "details": list(step.details),
                }
            )
    members: dict[str, list[str]] = {}
    for node in nodes:
        if (group := _group(node)) is not None:
            members.setdefault(group, []).append(node)
    started = Counter(path for path in trace.runs if path in nodes)
    return {
        "nodes": [
            {
                "id": node,
                "label": _name(node),
                "group": _group(node),
                "terminal": node in (START_NODE, END_NODE),
                "rank": ranks[node],
                "slot": slots[node],
                "status": _status(node, trace, visited),
                "count": started[node],
                "seconds": round(sum(run["seconds"] for run in runs[node]), 2),
                "runs": runs[node],
            }
            for node in nodes
        ],
        "edges": [
            {
                "source": source,
                "target": target,
                "conditional": conditional,
                "back": (source, target) in back,
                "taken": (source, target) in taken,
            }
            for source, target, conditional in edges
        ],
        "groups": [
            {"id": name, "status": _group_status(name, inner, trace, visited)}
            for name, inner in members.items()
        ],
    }


def _parse_input(update: Mapping[str, Any]) -> list[str]:
    topic = update.get("topic")
    lines = [f"intent: {update.get('intent')}, {len(update.get('student_steps', []))} step(s)"]
    return lines + ([f"topic: {topic}, level {update.get('level')}"] if topic else [])


def _orchestrator(update: Mapping[str, Any]) -> list[str]:
    if update.get("hint_retries"):
        return [f"leak check: rejected, retry {update['hint_retries']}"]
    published = bool(update.get("hints_used"))  # a finished problem resets the count to 0
    lines = (
        ["leak check finished, hint published"]
        if published
        else [f"action: {update.get('next_action')}"]
    )
    if "hint_level" in update and (published or update.get("next_action") == "hint"):
        lines.append(f"hint level: {update['hint_level']}")
    if reason := update.get("decision_reason"):
        lines.append(f"why: {reason}")
    return lines


def _verify(update: Mapping[str, Any]) -> list[str]:
    verdicts = ", ".join(f"{v.step_index} {v.relation}" for v in update.get("step_verdicts", []))
    return [f"answer correct: {update.get('is_correct')}", f"steps: {verdicts or 'none'}"]


def _localize(update: Mapping[str, Any]) -> list[str]:
    return [
        f"first error step: {update.get('first_error_step')}",
        f"focus step: {update.get('focus_step')}",
        f"error type: {update.get('error_type')}",
    ]


def _retrieve(update: Mapping[str, Any]) -> list[str]:
    found = update.get("misconception")
    if found is None:
        return ["no misconception"]
    return [f"{found.id} ({found.score:.2f}): {found.description}"]


def _hint(update: Mapping[str, Any]) -> list[str]:
    moves = update.get("reply_moves_forward")
    return ["draft written"] + ([f"reply moves forward: {moves}"] if moves is not None else [])


_SUMMARIES: dict[str, Callable[[Mapping[str, Any]], list[str]]] = {
    "parse_input": _parse_input,
    "orchestrator": _orchestrator,
    "verify": _verify,
    "localize": _localize,
    "retrieve": _retrieve,
    "hint": _hint,
}


def node_details(node: str, update: Mapping[str, Any]) -> tuple[str, ...]:
    """What the node decided, for the developer view; nothing for an unknown node or no update."""
    summary = _SUMMARIES.get(node)
    return tuple(summary(update)) if summary is not None and update else ()
