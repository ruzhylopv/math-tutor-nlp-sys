# Plan: render math in assistant replies (approved 2026-11-10)

Branch: `feat/latex-rendering`. One PR, one concern (display only).

## Goal
Backtick math fragments in assistant replies show as typeset math (KaTeX, already in Streamlit's
Markdown). The text inside the system stays plain: nodes, prompts and the leakage check do not change.

## Changes
1. `src/tutor/ui.py`: pure `render_math(text: str) -> str`.
   - Escape any `$` already in the prose.
   - Each backtick fragment becomes `$...$`, converted as text only (no SymPy round-trip, so the form
     shown is exactly what the tutor wrote): `^` → `^{...}`, `sqrt(...)` → `\sqrt{...}`,
     `abs(...)` → `\left|...\right|`, `*` → `\cdot`, `+-` → `\pm`, `(a)/(b)` → `\frac{a}{b}`,
     `<=`/`>=`/`!=` → `\le`/`\ge`/`\ne`.
   - A fragment that is not math or cannot be converted stays in backticks.
2. `app.py`: call it where assistant text is shown (the new reply and assistant turns in the history).
   `st.error` messages stay plain.
3. `tests/test_render_math.py`: each rule, `$` escaping, fallback, nested parentheses, prose unchanged.
4. `docs/decisions.md`: display-time conversion; rejected: the LLM writing LaTeX, and `sp.latex`.
5. `docs/crisp_dm_log.md`: short entry. No eval: display only, no LLM calls.

## Out of scope
Student messages, the trace panel, prompts, nodes.
