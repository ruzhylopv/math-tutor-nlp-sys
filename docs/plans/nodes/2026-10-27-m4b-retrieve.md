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
  grows. `numpy` is already installed (a transitive dependency) and becomes a declared dependency (rejected: relying on it
  being pulled in by sentence-transformers).
- **Catalogue entry**: `id`, `description` (in the student's voice: "believes that (a+b)^2 = a^2+b^2"), `category`,
  `topic` (a MATH subject in scope), `correct_rule`, and `example` (a wrong step as text, "(a+b)^2 -> a^2 + b^2"),
  because an embedding model reads the structure of a wrong rewrite better from an example than from prose alone. The
  text that is embedded is the description plus the example. The `example` field adds to the circularity: the agent
  writes the catalogue and the wrong rules from the same mental list, so a rule-generated rewrite can match its
  entry's example almost by construction. File: `src/tutor/data/misconceptions.json`, loaded by `tools/catalogue.py`.
  The catalogue embeddings are computed once and cached (in memory for the process), not per query.
- **State models**: `Misconception` in `state.py` stays as it is (id, description, topic, score). The catalogue entry
  is a separate model, `CatalogueEntry`, in `state.py`, with its loader in `tools/catalogue.py`; `hint` can look an
  entry up by id from the loader when it needs the correct rule.
- **Query** (built by the node, plain text): topic, error type, the previous line (or the problem for step 1) and the
  line the student wrote at `focus_step`. The query is the raw math strings only, as text (rejected: wrapping them in a
  template sentence or LaTeX; there is no evidence it helps). Top 5 go to `misconception_candidates` with their cosine
  score; the top 1 goes to `misconception`. v1 always returns the top 5 and sets the top 1 as `misconception`; there is
  no score threshold (abstention is an open item).
- `retrieve` returns no candidates and no misconception when `error_type` is None or `other` (nothing to retrieve for),
  or when `focus_step` is None. Every other error type gets retrieval with the same focus line. For
  `omission_extraneous_root` and `reasoning_result_mismatch` the focus line may not carry the misconception (the
  fault is a missing check or a justification that does not match, not a wrong rewrite), so retrieval for those two is
  weaker; a known limit, shown by Recall@1 per error type if the eval has such queries.
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` by default; one alternative (`BAAI/bge-small-en-v1.5`)
  is compared on the dev split and the better one is kept (MiniLM is the default for size and speed; bge-small is the
  one alternative compared; larger models are rejected for a catalogue this small). The weights download from the Hugging Face Hub at first
  use (about 100 MB); unit tests never load a model (they patch one function, `tools/embedding.embed`, like
  `structured.call_structured`).
- **Metrics (dev split)**: Recall@1, @3, @5, MAP@5 (one relevant misconception per query, so it equals the mean
  reciprocal rank cut at 5), per-source (generated and hand-written reported separately, never only blended) and
  per-category, and a random-ranking baseline for context.
- No LLM re-ranking of the candidates in v1. If Recall@5 is good and Recall@1 is not, a structured-output re-rank over
  the top 5 is the next step.

## Data
- **Catalogue**: about 120 entries across: signs and negatives, distributing over brackets, fractions, exponents and
  powers, solving equations, squaring and extraneous roots, factoring, radicals, absolute value, inequalities.
- **Eval queries**: (a) generated from about 40 mechanical wrong rules: a rule is applied to a correct step with random
  numbers and variables, and SymPy confirms the result is really different, so the true misconception is known by
  construction (like the corrupted steps for `verify` and `localize`); `topic` of a generated pair is the entry's topic
  and `error_type` is `algebraic_transformation`; the queries do not copy the catalogue's example text (a weak
  mitigation, since the structure is the same); (b) hand-written queries for the entries that are not mechanical (and
  some paraphrases), with the expected misconception worked out by reading. The generated queries cover the entries
  that have a mechanical wrong rule (about 100 of 119), the hand-written ones cover the rest. An entry with no query
  is never scored. Dev and test splits as for the other datasets; the dataset files are written by the developer's own run
  of the builder (the test split is protected).
- **Honest limits**: the agent writes both the catalogue and the queries, so Recall@k is optimistic and mostly shows
  the pipeline works; the `example` field makes it worse (see the catalogue entry); generated queries are single-rule
  rewrites, easier than a student's real work. Recall@k is reported for generated and hand-written queries separately,
  and the hand-written number is the more honest one.

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
- A confidently wrong top-1 misleads the `hint` node: cosine scores of an uncalibrated model are not probabilities, so
  a high score does not mean a right match. It is measured by Recall@1 per category; abstention (a score threshold)
  is the mitigation and an open item.
