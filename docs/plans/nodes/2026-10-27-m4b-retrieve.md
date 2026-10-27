# Plan: M4b `retrieve`, a hand-written misconception catalogue and embedding search (awaiting approval)

Goal: name the misconception behind the wrong step, so `hint` can aim at it. `retrieve` searches a catalogue of
school-algebra misconceptions and returns the best matches. Roadmap: `docs/plans/design/2026-10-25-roadmap.md`.
M4a (`localize`) is merged; this node reads its `focus_step` and `error_type`.

## Decisions (from the developer)
- The catalogue is hand-written by the agent (about 120 entries, school algebra), not Eedi: the Eedi download did not
  work for the developer. Eedi stays possible later as a second, independent test set.
- Retrieval uses sentence-transformers embeddings (PyTorch). The developer approved PyTorch and FAISS for this node.
- The developer spot-checks a sample (about 20%) of the entries and of the generated eval pairs before they are frozen.

## Decisions (agent defaults, for review in the PR)
- **No FAISS: plain numpy cosine similarity.** The catalogue has about 120 vectors, so an index library adds a
  dependency and nothing else. This is narrower than the developer's approval; FAISS can be added if the catalogue
  grows. `numpy` is already installed (a transitive dependency) and becomes a declared dependency.
- **Catalogue entry**: `id`, `description` (in the student's voice: "believes that (a+b)^2 = a^2+b^2"), `category`,
  `topic` (a MATH subject in scope), `correct_rule`, and `example` (a wrong step as text, "(a+b)^2 -> a^2 + b^2"),
  because an embedding model reads the structure of a wrong rewrite better from an example than from prose alone. The
  text that is embedded is the description plus the example. File: `src/tutor/data/misconceptions.json`, loaded by
  `tools/catalogue.py`.
- **Query** (built by the node, plain text): topic, error type, the previous line (or the problem for step 1) and the
  line the student wrote at `focus_step`. Top 5 go to `misconception_candidates` with their cosine score; the top 1
  goes to `misconception`. No score threshold in v1 (a wrong top-1 is better than none only if the eval says so;
  abstention is an open item).
- `retrieve` returns no candidates and no misconception when `error_type` is None or `other` (nothing to retrieve for),
  or when `focus_step` is None.
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` by default; one alternative (`BAAI/bge-small-en-v1.5`)
  is compared on the dev split and the better one is kept. The weights download from the Hugging Face Hub at first
  use (about 100 MB); unit tests never load a model (they patch one function, `tools/embedding.embed`, like
  `structured.call_structured`).
- **Metrics (dev split)**: Recall@1, @3, @5, MAP@5 (one relevant misconception per query, so it equals the mean
  reciprocal rank cut at 5), per-source and per-category, and a random-ranking baseline for context.
- No LLM re-ranking of the candidates in v1. If Recall@5 is good and Recall@1 is not, a structured-output re-rank over
  the top 5 is the next step.

## Data
- **Catalogue**: about 120 entries across: signs and negatives, distributing over brackets, fractions, exponents and
  powers, solving equations, squaring and extraneous roots, factoring, radicals, absolute value, inequalities.
- **Eval queries**: (a) generated from about 40 mechanical wrong rules: a rule is applied to a correct step with random
  numbers and variables, and SymPy confirms the result is really different, so the true misconception is known by
  construction (like the corrupted steps for `verify` and `localize`); the queries do not copy the catalogue's example
  text; (b) hand-written queries for the entries that are not mechanical, with the expected misconception worked out
  by reading. Dev and test splits as for the other datasets; the dataset files are written by the developer's own run
  of the builder (the test split is protected).
- **Honest limits**: the agent writes both the catalogue and the queries, so Recall@k is optimistic and mostly shows
  the pipeline works; generated queries are single-rule rewrites, easier than a student's real work.

## Stack
0. `chore/m4b-plan`: this plan and the decisions.
1. `feat/misconception-catalogue`: the entry model, the loader, the catalogue file, tests (valid schema, unique ids,
   every category and topic used, no duplicate descriptions).
2. `feat/retrieve`: `tools/embedding.py`, the dependencies (`sentence-transformers`, `numpy`; needs `uv.lock`), the
   `retrieve` node, unit tests with a fake embedder.
3. `feat/retrieve-eval`: the wrong-rule generators, the hand-written queries, the dataset builder, the eval script,
   the datasets, the first eval result and its CRISP-DM entry.

## Open
- Abstention: a score threshold below which `retrieve` returns no misconception.
- LLM re-ranking of the top 5 (decide from the eval).
- Eedi as a second test set, if the developer can get it later.
- The OPEN items inherited from M3 (the `student_steps` reset vs the hint path; stale `topic` and `level`;
  out-of-scope subjects) are not touched here.

## Risks
- A text embedding model is weak on bare math strings; the `example` field and the textual query are the mitigation,
  and the dev eval will show if it is enough.
- PyTorch is a large install (a few GB); about 19 GB of disk is free on this machine.
- The catalogue is the agent's draft of well-known misconceptions, not teacher-validated.
