# Plan: M4a `localize`, rules on SymPy's verdicts (approved 2026-10-27)

Goal: find where a wrong attempt goes wrong and what kind of error it is, using only what `verify` already
computed. No LLM and no new dependency in this part. M4b (`retrieve`, Eedi, embeddings) is a separate plan.
Roadmap: `docs/plans/design/2026-10-25-roadmap.md`.

## Decisions (from the developer)
- M4 is split: M4a `localize` first, M4b `retrieve` after. For M4b the developer agreed to the PyTorch /
  sentence-transformers / FAISS dependency and will download the Eedi dataset (Kaggle terms are theirs to accept).
- Error types: the three we have plus a fallback `other`, so cases the three do not cover are visible in the eval
  and not forced into a wrong type.
- Data for the `localize` eval combines generated cases, hand-written cases and, as a second opinion, PRM800K step
  labels (see "Data" for what v1 does with the last).

## Decisions (agent defaults, for review in the PR)
Rules, in this order. The node scans the steps once, in order; the first step with a problem decides.
1. `not_valid` step: `first_error_step` = `focus_step` = that step; `error_type` = `algebraic_transformation`.
   A step that is both `not_valid` and has a false justification claim is `algebraic_transformation`.
2. `unparsable` step: `first_error_step` = None (SymPy could not judge it), `focus_step` = that step (so the tutor
   can ask the student to rewrite it); `error_type` = `other`.
3. A valid step (equivalent / implies / narrows) whose `justification_claims_ok` is False: `first_error_step` =
   `focus_step` = that step; `error_type` = `reasoning_result_mismatch`.
4. No such step, but `is_correct` is False and some step is `implies` (a non-reversible step such as squaring):
   `first_error_step` = None, `focus_step` = the first `implies` step; `error_type` = `omission_extraneous_root`.
5. No such step, `is_correct` False, no `implies` step (for example a lost solution through a `narrows` step, or an
   incomplete answer): `first_error_step` = None, `focus_step` = None, `error_type` = `other`.
6. A clean state (nothing found): `first_error_step`, `focus_step` and `error_type` are all None. The graph does not
   call `localize` then; the node is still defined for it. `error_type` becomes optional in `TutorState`.
- A check line that fails (`check_holds` False) is information, not an error (it is how a student rejects an
  extraneous root); `localize` does not blame it. Known limit: a wrong arithmetic claim written as a check line is
  not flagged.
- Several errors in one solution: only the first is reported (`first_error_step` names one step). Known limit.
- Eval metrics (dev split): `first_error_step` accuracy, `focus_step` accuracy, `error_type` accuracy with
  per-type recall, precision and confusion counts, and the mismatch detection rate (recall of
  `reasoning_result_mismatch`). The eval runs `verify` and then `localize` on each case, since `localize` reads
  `verify`'s verdicts; both are deterministic, so there is no model, no cache and `model_name` is null.
- `src/tutor/prompts/localize.md` stays as the stub it is: the architecture assigns an LLM interpretation of
  justifications to this node, which a later iteration may add if the eval shows the rules miss it. It is not read.

## Data
- Generated: a mined MATH equation chain (first line = problem, the rest = steps) with one step made wrong by
  `evals/builders/corrupt.py` (a witnessed single-token edit). The first wrong step is known by construction, so the
  label is `algebraic_transformation` at that index. Only chains where `verify` finds every uncorrupted step valid
  are kept (the selection uses the code under test, as in the `verify` dataset; noted in the README).
- Hand-written, with the expected values worked out by reading each case: `omission_extraneous_root` (squaring
  without checking), `reasoning_result_mismatch` (right math, wrong stated sum), unparsable steps, a lost solution,
  several errors, a correct answer reached through an invalid step, a failed check line that rejects a root.
  The developer spot-checks a sample.
- PRM800K human step labels as a second opinion: not in v1. Its prose-and-LaTeX solutions need a conversion to
  plain-text steps that does not exist yet, and its `-1` means "everything else", not "algebraically invalid"
  (`docs/decisions.md`, M2). Revisit after the first eval, as a separate decision.
- Dev and test splits as for the other datasets; the dataset files are written by the developer's own run of the
  builder (the test split is protected).

## Stack
0. `chore/m4a-plan`: this plan, the decisions, the architecture error-type update.
1. `feat/localize-rules`: `ErrorType` gets `other`, `error_type` becomes optional, the node and its unit tests.
2. `feat/localize-eval`: the dataset builder, the hand-written cases, the eval script, the datasets and the first
   eval result with its CRISP-DM entry.

## Open
- Whether the LLM interpretation of justifications is added to `localize` (decide from the eval).
- PRM800K as a second opinion (see Data).
- The OPEN items inherited from M3 (the `student_steps` reset vs the hint path; stale `topic` and `level`;
  out-of-scope subjects) are not touched here.

## Risks
- The generated errors are single-token edits, easier than student errors; the hand-written cases are the
  discriminating ones.
- Chains selected by `verify` make part of the generated dataset depend on the code under test (circularity).
