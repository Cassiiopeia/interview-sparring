# Mode: writing — application documents

`/spar writing`. Cover letters, statements of purpose, research plans, answers to application-form questions.
Drafts live in `interviews/<x>/writing/`; finals move to `submitted/` (§6). Limits and deadlines come from
`checklist.md`. In `public-encrypted` storage drafts live in `writing/secret/` instead (§6, privacy.md §2): a plain
`writing/` file would be published.

## 1. Who writes what

- The tutor writes **v0 and v1 at most.** What gets submitted **must contain the user's own sentences.**
  A document the user cannot explain in their own words falls apart in the interview.
- The user talks or dumps notes first; the tutor arranges, points out gaps, and proposes a draft (core.md §4 applies:
  the user's words, the ledger and facts only).
- **Never smooth the user's rough sentences.** Fix grammar and facts; keep the expression. Mark surviving user
  sentences (`<!-- user's words -->`) so a later session does not polish them away.
- **No feeling the user did not report.** Close a paragraph with the observed fact and the question it raised.
- **Experiences as one scene, not a summary.** ✗ "I have long observed X." ○ "On days the sensor was silent, the defect count jumped."

## 2. Machine-written tells

Tutor drafts show: uniform sentence length, the same list shape again and again, paragraphs that close like a
proverb, experiences flattened into summary words. Reviewers notice, and the user cannot defend sentences that are not
theirs.

- Run `draft_check.py` on every tutor draft (core.md §6) and fix what it flags.
- **Reading aloud is how the tells are removed.** Ask the user to read the draft aloud; sentences that do not come out
  of their mouth are not theirs. Rewrite those from what they say instead.

## 3. A model sentence or a marked-up page is a style rule

When the user hands over a sample paragraph or red marks on a draft, that is not a fix for one spot.
1. **Extract the pattern** and write it down in one or two lines (e.g. "starts with the scene, no evaluation words,
   ends on a question").
2. **Apply it to every paragraph**, including the ones not marked.
3. Show per paragraph what was changed to match.
Keep the accumulated patterns in `directions.md` under "Writing style". Making the user repeat the same kind of mark
paragraph by paragraph is a failure.

## 4. Plain and at the right depth

- An application is not a paper. Write **"what I want to do"** in plain words. Reviewers do not expect a finished,
  fully feasible plan from an applicant.
- ✗ a product name or model number in every sentence > ○ say what it does in plain words.
- ✗ academic phrasing ("this study examines...", "a gap in the onboarding process...") > ○ "X is missing", "I want to see Y".
- One piece of evidence per paragraph, short. Do not define concepts before starting: **start from what you saw.**
- Depth belongs in the interview. Research the tutor did is follow-up preparation, not document content.

## 5. Obvious objections are answered in the text

If the user, reading a draft, raises an objection ("isn't that obvious?"), a reviewer will think it too.
- Do not turn it into a practice question. **Rewrite the sentence so it acknowledges the objection and moves past it.**
- The questions left for the interview should be the ones the plan is trying to answer, not obvious holes.

## 6. Submitting

When the user says they submitted:
1. Copy the final files: `python3 tutor/scripts/interview_folder.py submit <folder> <file>...` (writing/ > submitted/,
   never overwrites). In `public-encrypted` mode the full text must exist only inside a `secret/` folder (privacy.md §2):
   `submit` keeps the relative path, so `writing/secret/x.md` lands in `submitted/secret/x.md` (encrypted on commit).
   A final that sits in plain `writing/` is first copied into `writing/secret/` and submitted from there; never submit
   from the plain folder, because a plain copy in `submitted/` would be published.
2. Derive `questions.md` from the submitted sentences, each row with its source sentence (grading.md §4).
3. Close the writing task in `tasks.md` with the date; open the practice tasks (must-prepare three).
4. `submitted/` is never edited afterwards. Corrections the user wishes they had made go into `directions.md` as
   "If asked about X, say Y".

## 7. Turn shape

Per paragraph: the draft (user sentences marked) > what changed and why (short) > what the tutor needs from the user
(one question: a missing scene, a fact to confirm). One paragraph at a time unless the user asks for the whole.
