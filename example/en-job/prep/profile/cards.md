# Recall cards

Weak spots, slipped phrasing and pressure questions from practice pile up here and come back on schedule.
**Never write the answer** — only the question and its source. Seeing the answer turns recall into rereading.

`stage` counts correct answers. Stage 0 -> 1 day, 1 -> 3 days, 2 -> 7 days, 3 -> 21 days, 4 -> 60 days until the next review.
A wrong answer resets it to 0. `area` is a free label such as a story, a question set, vocab or facts (e.g. story-01, vocab).

`tutor/scripts/review.py` reads and writes this table. Hand edits are fine, but keep the column count.


| id | area | question | source | stage | next_review | history |
|---|---|---|---|---|---|---|
| story01-01 | story-01 | "So the team built it — what did you decide yourself?" First sentence? | experiences/01-tracking-cache.md, Action | 0 | 2030-03-11 | 2030-03-10:x |
| motivation-01 | motivation | "Why Acme and not a bigger logistics company?" | cover letter paragraph 1 | 1 | 2030-03-13 | 2030-03-10:o |
