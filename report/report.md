---
title: Homework 1 -- A Socratic algebra tutor that finds the wrong step
author: Ruzhylo Pavlo
course: Natural Language Processing · UCU
date: 2026-11-10
---

## Summary

<!-- layer 6: the one-paragraph summary, links to the repository, the demo video and the requirement checklist -->

## 1. Business understanding

### The problem

A student solving an algebra problem rarely needs the answer: it is usually at the back of the book. What they need
is to know **where their own working went wrong and why**. A typical case:

$$
3(x + 2) = 15 \;\Rightarrow\; 3x + 2 = 15 \;\Rightarrow\; 3x = 13 \;\Rightarrow\; x = \tfrac{13}{3}
$$

Every line after the first follows correctly from the line before it. The error is in step 1, which multiplies only
the first term in the bracket. A useful tutor points at step 1, recognises the misconception and asks a question that
lets the student find it. It does not write `3x + 6` for them.

### Goal and scope

The system is **not a general math assistant and not a solver**. Its single job is this: take a problem and the
student's own step-by-step attempt, and help the student **repair** it. Concretely, it:

1. checks every step symbolically and finds the first step that does not follow (or the type of error when no single
   step is wrong, such as an extraneous root that was never rejected);
2. names the most likely misconception behind that step;
3. gives graded Socratic hints (level 1 is a question, level 4 is the most direct) that **never reveal the answer or
   the corrected line**;
4. remembers each student's recurring misconceptions across chats.

In scope: school algebra (MATH Prealgebra, Algebra and Intermediate Algebra: linear equations, brackets, quadratics,
factoring, radical and rational equations). Out of scope: calculus, geometry, proofs and other languages. A student
who has a problem but no working gets one guiding question, not a lesson. A student who sends only an answer is asked
for their steps.

### Why a pipeline and not one prompt

A strong chat model with a careful prompt can do much of this in one call, and this project is partly an exercise in
splitting an NLP task into parts that can each be measured. The split still pays for itself, for four reasons:

- **Locating an error is the hard part for LLMs.** Tyen et al. show that models are poor at *finding* reasoning
  mistakes but good at *correcting* them once the location is given [1]. ProcessBench defines exactly this task
  ("identify the earliest erroneous step, or say all steps are correct") and finds it hard for current models [2].
  Daheim et al. find the same for student solutions specifically, and show that verifying first and then generating
  gives better-targeted tutor replies [3]. Here verification is done by a symbolic engine (SymPy), so it is exact for
  the algebra it covers. The LLM never checks algebra.
- **Tutors trade student success against revealing the solution.** MathDial measures this trade-off in human-teacher
  dialogues [4]. A prompt instruction such as "never give the answer" is a soft constraint. Here a deterministic
  leakage check in code rejects any hint that states the answer or the corrected line before the student sees it.
- **Prompt discipline erodes.** Over a long chat a model drifts from a Socratic structure, and a student can simply
  ask for the answer. The hint ladder, its levels and the leakage check live in the graph, so they cannot be talked
  out of.
- **Each stage can be evaluated on its own** (section 5), as the assignment requires.

The retrieval step is not vanilla RAG: it answers "which misconception explains this wrong step?" over a
misconception catalogue, inside a verified diagnosis pipeline. The Eedi "Mining Misconceptions in Mathematics" Kaggle
competition (2024) framed a similar ranking task (match a wrong answer to a misconception, scored with MAP@k) [5].

### Success criteria

- **Diagnosis:** the first wrong step and the error type match the label. The misconception is in the top 5
  retrieved.
- **Hints:** no answer leakage, numbers used only from SymPy, and each hint fits its level.
- **Conversation:** an answer without working is asked for steps, a question escalates the hint level, a correct
  solution is recorded in the student's profile.

## 2. Data understanding and preparation

### What exists, and what was checked

| Source | Checked for | Outcome |
|---|---|---|
| MATH [6], via the `math_splits` files of PRM800K [7] | problems, human-written solutions, subject and level labels | **used** (MIT licence); raw files stay outside the repo, only derived sets are committed |
| PRM800K step ratings [7] | first-error labels | **not used**: solutions are prose plus LaTeX with no converter to plain-text steps, and its `-1` rating means "inaccurate, weird or off-topic", not "algebraically invalid" |
| ProcessBench [2], MathEDU, MR-GSM8K, ErrorRadar, Cognitive Tutor logs | error-step labels and error taxonomies | found in a literature search, not downloaded; as described, none labels our `omission_extraneous_root` or `reasoning_result_mismatch` types, and most are word problems or competition math |
| Eedi misconceptions [5] | a misconception catalogue | **could not be downloaded**, so a catalogue was written instead |
| messy student messages with a known parse | input-layer labels | **none found**, so messages are rendered from mined chains with a known parse |

### What each component is evaluated on

Each set has a fixed **dev** split (all iteration) and a **test** split (final numbers only, write-protected for the
coding agent). Origins: *as-is* = labels taken unchanged from MATH; *mined* = lines extracted from MATH solutions;
*generated* = produced by a rule-based script with a seed; *hand-written* = written and labelled by the coding agent,
with a sample for the developer to spot-check.

| Set (component) | Dev | Test | Origin and where the label comes from |
|---|---|---|---|
| `verify_steps` (verify) | 1,621 | 671 | **mined** consecutive line pairs from MATH Algebra levels 1-3, labelled `equivalent` by the MATH author and kept only where SymPy agrees (787 / 331); **generated** single-token corruptions labelled `not_valid`, kept only if an exact witness point proves them wrong (781 / 317); **hand-written** cases for the rare relations `implies`, `narrows`, `unparsable` (53 / 23) |
| `verify_chains` (verify) | 14 | – | **hand-written** whole solutions with definitions and prose lines |
| `classify` (parse_input topic and level) | 420 | 420 | **as-is** MATH subject and level labels, 60 problems per subject |
| `parse_input` | 185 | 159 | **generated** messages (150 / 150): a mined step chain, sometimes with one wrong step, rendered in 4 layouts and 4 notations (plain, LaTeX, unicode, spoken) with chatty frames and typos in words, so the expected parse is known by construction; **hand-written** messages (20 / 9) and hand-written replies to the tutor (15 / –) |
| `localize` | 78 | 77 | **generated** mined chains with one corrupted step (60 / 60); **hand-written** attempts for every error type (18 / 17), split by problem so no problem is in both |
| misconception catalogue (retrieve) | – | – | **hand-written**: 119 school-algebra misconceptions in 13 categories, each with a description, the correct rule and an example |
| `retrieve` | 324 | 300 | **generated** from 99 mechanical wrong rules, each wrong line confirmed wrong by SymPy (204 / 192); the same rules **wrapped** in a larger expression so the shape differs from the catalogue example (100 / 90); **hand-written** queries (20 / 18). Catalogue entries alternate between splits |
| `hint` | 60 | – | **derived** from `retrieve` queries plus a hint level 1-4, with the gold misconception |
| scenarios A and B (end to end) | 2 | – | **hand-written** multi-turn chats; also the demo script |
| routing turns (orchestrator) | 32 drafts | – | **hand-written**, *unlabelled*: labelling is left to the developer, not the agent |

### Preparation decisions and caveats

- **Dev and test are separated by problem**, not by line, so no problem's steps appear in both. One exception is
  known: 12 identical `verify` pairs from different problems ended up in both splits.
- **Generated data is easier than real students.** Corruptions are single-token edits (a sign, a number, a dropped
  term), and about 5 of 6 mined chains are arithmetic or simplification, not equations. Results are therefore always
  reported **per source**, and the hand-written cases are the discriminating ones.
- **Several sets are high by construction.** Mined positives were kept only where SymPy agreed with the human author,
  and generated `localize` chains were selected with `verify`. These sets act as regression suites. The independent
  check is the build report: SymPy agrees with the MATH author on 1,118 of 1,127 parseable pairs (99.2%) and parses
  90.1% of 1,251 mined pairs.
- **The retrieval data is circular.** The same agent wrote the catalogue and the queries, and 89 of 99 plain
  generated queries have the same shape as their catalogue example. The wrapped and hand-written queries are the
  honest numbers.
- **No dataset example is used in a prompt**, a rule in the agent instructions.
- **Plain-text math is the internal format.** Every claim is stored as plain text that SymPy parses (`x^2`,
  `sqrt(...)`, `(a)/(b)`). `parse_input` converts LaTeX, unicode and spoken math into it. The full data card, with
  field definitions and limits, is in `evals/datasets/README.md`.

## 3. System architecture

<!-- layer 4: data-flow diagram, components (purpose, input, output), model calls and tool calls, a walkthrough of
one input through the system -->

## 4. Development plan

<!-- layer 4: milestones M1-M7, the flexible-input redesign, polishing; timeline -->

## 5. Evaluation

<!-- layer 5: metric choice per component, results on dev and test, charts, why scores are not higher, debt -->

## 6. Deployment and demo

<!-- layer 6: how to run the app, the demo-video outline -->

## 7. Agentic development setup

<!-- layer 6: CLAUDE.md, skills, subagents, hooks and permissions, the review/fix loop, stacked PRs, the
/address-review GitHub workflow, reflection -->

## 8. Limitations and future work

<!-- layer 6 -->

## 9. Requirement checklist

<!-- layer 6: every item of the assignment mapped to a section -->

## References

1. G. Tyen, H. Mansoor, V. Cărbune, P. Chen, T. Mak. *LLMs cannot find reasoning errors, but can correct them given
   the error location.* Findings of ACL 2024. [arXiv:2311.08516](https://arxiv.org/abs/2311.08516)
2. C. Zheng et al. *ProcessBench: Identifying Process Errors in Mathematical Reasoning.* 2024.
   [arXiv:2412.06559](https://arxiv.org/abs/2412.06559)
3. N. Daheim, J. Macina, M. Kapur, I. Gurevych, M. Sachan. *Stepwise Verification and Remediation of Student
   Reasoning Errors with Large Language Model Tutors.* EMNLP 2024. [arXiv:2407.09136](https://arxiv.org/abs/2407.09136)
4. J. Macina et al. *MathDial: A Dialogue Tutoring Dataset with Rich Pedagogical Properties Grounded in Math Reasoning
   Problems.* Findings of EMNLP 2023. [arXiv:2305.14536](https://arxiv.org/abs/2305.14536)
5. Eedi, Vanderbilt University, The Learning Agency Lab. *Eedi – Mining Misconceptions in Mathematics.* Kaggle
   competition, 2024. Organiser's write-up:
   [eedi.com/blog](https://eedi.com/blog/from-wrong-answers-to-real-insights-how-we-used-a-kaggle-challenge-to-map-student-misconceptions)
6. D. Hendrycks et al. *Measuring Mathematical Problem Solving With the MATH Dataset.* NeurIPS 2021 Datasets and
   Benchmarks. [arXiv:2103.03874](https://arxiv.org/abs/2103.03874)
7. H. Lightman et al. *Let's Verify Step by Step.* 2023 (PRM800K).
   [arXiv:2305.20050](https://arxiv.org/abs/2305.20050)
