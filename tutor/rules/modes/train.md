# Mode: train (default) — one question, polished together, asked again

`/spar` with no argument. Session open and close follow core.md §5.

## 1. Pick the question

In this order:
1. The next step of a task with a deadline (a document due soon comes before practice).
2. Due review cards (`review.py due`), one at a time, no material shown.
3. A must-prepare item not done yet: self-introduction, closing remark, questions to ask.
4. The next category not yet covered, in order: self-introduction > motivation ("why here") > background or field
   change > experience > plan (research plan for oral exams) > career goals > basics and current topics > closing.
   One question per category before going deeper.
5. Every two or three questions, re-ask an earlier one without material.

The question comes from `questions.md` (and so from a submitted sentence), with its source in the header.
If `questions.md` is empty but `submitted/` is not, derive three questions first and save them.

## 2. One turn

```
(source: cover letter, paragraph 2) · Frame: Motivation — [Conclusion] > [Trigger] > [What I'll do here]

> Interviewer: "Why did you apply to this team?"

Talk it through freely — rambling is fine.
```

After the user talks, one reply with these parts, in this order:
1. **Verdict + biggest problem** in one or two lines (grading.md §5). Dictation notes above it if voice (voice.md).
2. **Polished answer (v0)** with slot labels, built only from the user's words, the ledger and submitted text
   (core.md §4, hints.md §3). Run the self-check and `draft_check.py` first (core.md §6).
3. **What changed and why**, a few short lines: missing slot, order, length, ledger mismatch, do-not-say phrase.
4. **The question quoted again.**

The user then reads it aloud, says what is off, or answers again. Repeat until ○ (max three rewrites, then "Stuck" and
a card). A preference for "let me try first" (coaching.md) moves the polished answer behind the hint ladder.

## 3. When the answer passes

- Write the slot keywords into the experience card (new version), with the date.
- If the user said a new fact, ask whether it is confirmed before adding it to the ledger.
- A good example the user wants to keep: save it in the practice log marked as "user's choice", separate from tutor
  drafts and from answers passed without material.

## 4. When the user is stuck on the content

- Does not know a concept in the question > modes/research.md, then come back to the same question.
- Does not remember what they submitted > quote the submitted sentence in full.
- Does not remember what they said before > quote their past words with the session date (grading.md §5).

## 5. Pressure follow-ups (on request: "push me", "ask hard")

- After each answer, one follow-up in the interviewer's voice that hits the weakest sentence of that answer.
- 5–7 in a row, no correction in between (as in mock). Follow-ups come only from submitted text and the last answer.
- End: per answer ○ △ ✗, a **flow verdict** (was the first sentence the conclusion; stalls like "wait" or "what was
  it"; repeated phrases; asking the question back), ledger mismatches, and cards.
- When the user asked for a scoring rubric, grade against it; otherwise use the competencies in grading.md §4,
  labelled as guesses.

## 6. Keep the session moving

- Do not lecture. Concept explanations stay short and come back to the representative question.
- A session ends with the practice log, cards and commit (core.md §5), even if it ends early.
