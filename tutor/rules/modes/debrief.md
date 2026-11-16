# Mode: debrief — right after a real interview or meeting

`/spar debrief`. Same day if possible, while memory is fresh. The user pours out whatever they remember, in any
order; the tutor sorts it.

## 1. Collect

Ask, one at a time, only for what is still missing:
1. The questions they remember (rough wording is fine).
2. How the other side reacted (nodding, follow-ups, a pause, a correction).
3. What they answered, roughly, and where they got stuck.
4. Anything new they learned (schedule, format, next steps, what the team or program looks for).

A recording or full transcript > saved raw in `local/` only (voice.md §3).

## 2. Write it down

- `interviews/<x>/asked.md`: one row per question — question, the user's answer in brief, the reaction, how it went
  (○ △ ✗ by the user's own feel).
- New facts > ask whether confirmed, then `facts.md`. Schedule or format news > `about/` (as a dated note) and
  `checklist.md`, and tasks for any new deadline.
- Stuck places > cards (`review.py add`).
- Questions that came up and were not in `questions.md` > add them with type `asked`.

## 3. Carry it forward

- If there is a next stage (second interview, faculty meeting, exam), update its question list: what was asked here
  is likely to be followed up there.
- Advice the user received about how to answer > `directions.md` or `coaching.md` (memory.md §1 decides which).
- `status.md`: stage moves forward, next session written.
- Commit (`debrief: 1 session`).

## 4. Tone

The user may be tired or upset after a real interview. Keep it short, no verdict on the outcome, no speculation
about the result.
