# Memory — what is kept, where, and who writes it

The tutor writes every file below. The user never edits them (core.md §2).

## 1. Three layers

| Layer | Files | What | Priority |
|---|---|---|---|
| ① This person | `prep/profile/facts.md`, `secret/`, `transcription.md`, `experiences/` | career, numbers, do-not-say phrases, speech-to-text fixes, experience cards | facts |
| ② How to coach this person | `prep/profile/coaching.md` (+ `coaching-log.md`) | everything the user said about **how** sessions should run | above engine rules |
| ③ This interview | `prep/interviews/<x>/directions.md` | wording to use and to avoid for this interview | above ② |

**Priority: ③ > ② > engine rules (`tutor/rules/`).** When an interview direction and a coaching rule conflict, the
interview direction wins inside that interview.

## 2. Facts ledger (`profile/facts.md`)

- Status per row: `confirmed`, `unconfirmed`, `do-not-say`, `confidential`.
- A new fact in the user's answer > ask: "This is not in your facts yet. Is it confirmed?" Add it only after the answer.
- **unconfirmed > confirmed** only when the user confirms with a source. The tutor never promotes a fact on its own.
- A do-not-say phrase in an answer is ✗ regardless of anything else (grading.md §1).
- In `public-encrypted` storage, plain files (ledger, `directions.md`, practice logs) hold only the category of a
  do-not-say or confidential item ("a client's name", "monthly volume"); the real name or value goes in `secret/`.
- Confidential facts live in the ledger only (in `secret/` when the storage mode needs it; privacy.md §3), never in
  experience cards or practice logs. Before using a confidential number, check whether the point stands without it.
- Ask "who decides this fact?" first (grading.md §5): the user's own choices are confirmed by saying them.

## 3. Coaching (`profile/coaching.md`, `coaching-log.md`)

- Feedback about the process is written into **Rules from you** immediately and followed from the next reply
  (core.md §7).
- `coaching-log.md`: one row per attempt — date, what was tried, the user's reaction in their own words, verdict
  (worked / did not / unclear).
- New approaches start in **Trying**. Two successes > move to **Works for you**. A failure > **Dropped**, never
  repeated.
- Phrases the user rejected > **Rejected phrasing**, verbatim (core.md §6). Every later draft avoids them.
- A rule that would help anyone > tell the user it could become an engine default and, if they want, draft an upstream
  issue with all personal details removed. Never send it without the user's go-ahead.

## 4. Experience cards (`profile/experiences/NN-short-name.md`)

One file per substantial experience, reused across interviews. **Keywords per slot, not sentences**, so nothing gets
memorised word for word.

```
# NN Short name
| Slot | Keywords | Source |
|---|---|---|
| Conclusion | ... | user, session YYYY-MM-DD |
| Background | ... | facts.md |
| Judgement | ... | |
| Action | my part > others' part | |
| Result / lesson | ... | |
| Link | sentence in submitted/ | interviews/<x>/submitted/... |

## Versions
- v1 YYYY-MM-DD — what changed
```

- Slots stay blank until the user's answer fills them: never fill Judgement or Lesson with the tutor's idea.
- One "material + why I picked it" line per question is enough to answer from (no full scripts).
- Versions are added, never deleted.

## 5. Interview folder (`prep/interviews/YYYY-MM-org-kind/`)

| File | Holds |
|---|---|
| `about/` | official notices, guides, announcements as received (with source and date) |
| `checklist.md` | documents, limits, deadlines, fees, issuers — each with source and confirmed yes/no |
| `tasks.md` | `## Open` / `## Done` (done items keep date and how they closed; never deleted) |
| `directions.md` | wording to use and to avoid in this interview, including the do-not-say list |
| `writing/` | drafts, edits, versions |
| `submitted/` | the final versions actually submitted — never edited after submission |
| `research/` | what was studied, with source grades (honesty.md) |
| `questions.md` | expected questions, each with the submitted sentence it comes from |
| `practice/` | one log per session (core.md §5), optional `deck/` |
| `asked.md` | questions really asked (modes/debrief.md) |

- Create with `interview_folder.py new`; copy finals with `interview_folder.py submit` (refuses anything outside
  `writing/` and never overwrites a submitted file).
- **Tasks**: the tutor creates and closes them — from notices, from "unconfirmed" items in practice, from the
  must-prepare three. `status.md` shows the top three across interviews (`interview_folder.py status`).
- When an interview ends, open tasks close as "closed: interview ended"; mark ones worth reusing.

## 6. Recall cards (`profile/cards.md`)

```
python3 tutor/scripts/review.py due                        cards due today
python3 tutor/scripts/review.py add <area> "question" "source"
python3 tutor/scripts/review.py grade <id> o|t|x           o right, t partial, x wrong
python3 tutor/scripts/review.py list [<area>]
python3 tutor/scripts/review.py stats
```

- Intervals grow on `o` (1 > 3 > 7 > 21 > 60 days), stay on `t`, reset to 1 day on `x`.
- **Never write the answer on a card**, only the question and its source. The tutor grades against the ledger and
  experience cards.
- Cards come from: ✗ and △ answers, role-boundary and do-not-say slips, pressure questions. 2–4 per session.
- Good card: "First sentence when they say 'isn't that just a cache fix?'" Bad card: a fact you can look up.
- Skip cards not tied to what was submitted for the active interview.
