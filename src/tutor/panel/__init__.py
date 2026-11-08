"""The graph panel's browser component, for `app.py`.

Streamlit raises on a second keyed mount in one script run, and an unkeyed mount is rebuilt each
time. So the graph is mounted once per run under a fixed key, and each update during a turn goes
through a second, hidden, unkeyed component that only hands its data to the first through `window`.
That keeps the page's DOM, so the selection and the spinner live on, and a click never reruns the
script (a rerun would kill the running turn). The files beside this module are the frontend.
"""

import time
from pathlib import Path
from typing import Any

import streamlit as st

_HERE = Path(__file__).parent

_graph = st.components.v2.component(
    "tutor_trace_graph",
    html='<div id="root"></div>',
    css=(_HERE / "panel.css").read_text(encoding="utf-8"),
    js=(_HERE / "panel.js").read_text(encoding="utf-8"),
)
_update = st.components.v2.component(
    "tutor_trace_update",
    js=(_HERE / "update.js").read_text(encoding="utf-8"),
)


def _stamped(view: dict[str, Any]) -> dict[str, Any]:
    """Make each payload unique (an unkeyed repeat raises) and tell the browser which is newest."""
    return {**view, "stamp": time.monotonic_ns()}


def mount_graph(view: dict[str, Any]) -> None:
    """Draw the graph; call once per script run."""
    _graph(key="trace_graph", data=_stamped(view))


def push_update(view: dict[str, Any]) -> None:
    """Send a newer view to the mounted graph; call inside the hidden `st.empty`."""
    _update(data=_stamped(view))
