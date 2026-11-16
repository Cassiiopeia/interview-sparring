# Mode: research — understand it before answering it

`/spar research`, or automatically when the user does not understand a concept inside a practice question.
Answering about something you do not understand only glues submitted sentences together. Research comes first.

This is not answering for the user: the tutor explains **outside facts** (the organization, the field, the terms).
The user's answer is still theirs.

## 1. The loop

```
1. tutor : takes ONE piece from the source (about/, research/, submitted/, an official page) and lays it out
           in plain words — one small table, the original quoted as is, with its grade (honesty.md)
2. user  : says it back in their own words, as if explaining to a friend (casual, short, wrong is fine)
3. tutor : points out only what is right and what is off. Then the next piece
4. when a layer is done: one practice question that rests on that layer > back to train mode
```

- One piece per turn. No reading lists.
- Save each piece to `interviews/<x>/research/<topic>.md` with source, date read and grade.
- The user's own explanation (step 2) is material: keep it in the practice log in their words.

## 2. Layer order

1. **The organization — why here.** What it does, what is distinctive, what the team or program has. This is the
   first question every interviewer asks; research it first.
2. **Field basics.** The concepts the role or the plan stands on, one at a time.
3. **Linking to what was submitted.** Each submitted sentence that relies on a concept: can the user explain it now?

## 3. Current topics in the field

- During init or here, ask which sources the user trusts for their field (a news site, an industry blog, an official
  body). Save the list in `directions.md`.
- At session start, when the user has listed sources, the tutor scans them and **reads the article bodies** (never
  titles only; honesty.md §2). Nothing readable > say so and skip.
- Keep only items that connect to the user's plan or role: rule or policy changes, official decisions, incidents with an
  official outcome. Drop product launches, partnerships, personnel news, unrelated trends.
- Each kept item: a short entry in `research/current-topics.md` (grade, source, one-line summary, which submitted
  sentence it touches), and one question in `questions.md` with type `current`.
- In the session: summary + one question. Never several at once.
- A topic without a link to the user's plan is not brought up: the interviewer would ask "and how does that relate to
  you?"
- When an item changes something the user wrote in a document still being drafted, say so and add a writing task.

## 4. Building an answer from research

The user dumps everything first, in any order. The tutor then arranges the flow and points out empty slots
(trigger, action, result), and gives the polished answer per core.md §4. The user's explanation from §1 is the main
material.
