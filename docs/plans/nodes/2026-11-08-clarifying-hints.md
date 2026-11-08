# Plan: hints that answer a clarifying question and do not repeat themselves (approved 2026-11-08)

Found in a real chat on `3(x + 2) = 18`, wrong line `3x + 2 = 18`. Three hints went wrong in different ways.

- Level 1 asked what happened to the `+ 2`, which was still there. `hint.md`: the question must be true of what the student wrote
  and point at the part that differs from the line before, with a good and a bad example.
- "What do you mean here?" raised the level and was not passed to `hint`, so the tutor changed method. `orchestrator`: intent
  `explain` after a hint keeps the level. `hint`: gets `Tutor's last message` and `Student's question`; `hint.md`: say the same
  point more simply.
- A correct reply to the counterexample got the same numbers back. `hint`: a reply at level 2 to a message already quoting the
  numbers gets "already used"; `hint.md`: ask about the idea instead.
- `hint.md`: no praise when responding to a reply or a question.

Includes `5343bf9` (a calculation in reply to a hint), which changes the same files and had no PR.

Changed existing test: `test_a_clarifying_question_after_a_diagnosis_still_escalates` asserted the rule the developer asked to change.

Eval: `eval_hint` on the dev split, after the developer agrees the number of model calls. It covers level wording only; its cases
are not replies, so the chat itself is re-sent by hand.
