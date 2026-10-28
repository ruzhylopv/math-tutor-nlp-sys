# math-tutor-nlp-sys

LangGraph math tutor for school algebra: verifies a student's steps with SymPy, finds the first wrong step,
retrieves the misconception and gives graded Socratic hints. Architecture: `docs/architecture.md`.

## Run the app
1. `uv sync`, then copy `.env.example` to `.env` and set `OPENROUTER_API_KEY` and `MODEL_NAME`.
2. Set `LEARNER_DB_PATH` (a SQLite file) to remember mistakes across chats; without it the tutor still works but
   keeps no profile. `CHECKPOINT_DB_PATH` (default `data/checkpoints.db`) holds the saved chats.
3. `uv run streamlit run app.py`

Type a name (it separates people's chats; there is no password). Paste a problem with your steps, or ask a question.
The sidebar shows the hint level, hints used and the profile across all your chats; "New chat" starts a fresh
conversation for the same name. A free model can take a minute per message.
