# Interview type: job interview

Applies to interview folders whose kind is a job interview (`meta.json` kind, or what the user said in `new`).
Grading frames are in grading.md; this pack adds what job interviews always ask.

## 1. Must prepare three

Every job interview folder starts with these tasks (the template adds them; never close them unprepared):
1. **One-minute self-introduction**
2. **Closing remark** ("Anything you'd like to add?") — one prepared sentence
3. **Questions to ask the interviewer** — two or three, about the work, never about things on the public website

## 2. One-minute self-introduction frame

```
[Greeting]        Hello.
[Who]             I'm <name>, applying for <role>.            <- the first sentence ends here
[Now]             I work at <type of company> as <role>, <years>; my main duty is <one duty>.
[What it raised]  Doing that, I kept running into <one concrete question or interest>.
[Here]            Here I want to <what you'd do in this role>.
[Close]           Thank you.
```

- **Main duty only.** Not every task you have ever done. The rest comes out in follow-ups.
- The one-line tagline that ties two backgrounds together is for written documents; spoken, it sounds rehearsed.
- One minute by default; a two-minute version only when asked, by expanding [Now] and [What it raised] with one scene.
- Store it as slot keywords in the experience card, never as a script to memorise.

## 3. Motivation: "Why us?"

- The first sentence names **something of this organization** (product, team, problem, way of working) found in
  `about/` or `research/`, with a source. "You are a great company" is not a reason.
- What the user wants comes last, in one line.
- No source found yet > add a research task; do not let the user improvise a reason that cannot be backed.

## 4. Career or major switch

Tell it as a story in this order, and only as far as the question asks:
1. What originally interested you
2. What you kept doing on the side (projects, study)
3. How you moved over, so the switch sounds natural

Stop at the path. The reasons behind every choice wait for follow-ups.

## 5. Pressure: "We don't do that here" / "That's not what this role is"

Admit, ask, stay curious:
1. Admit the misjudgement plainly: "Then I misread that part."
2. Ask for the real scope: "Could you tell me what the role covers there?"
3. Show you'd learn it: "I'd like to learn that side as well."

Same shape for anything the user does not know: admit > what I do know > want to learn it. Never bluff.

## 6. Strengths and weaknesses

- **One strength as one scene**, not a list of adjectives. Conclusion word > the scene > what it changed.
- A weakness comes with what the user already does about it, as a habit, not a promise.

## 7. Experience questions

- Three sentences: situation, what I did, what I learned (grading.md §2).
- Role boundary first when the user did not own the whole thing.
- Interviewers ask about tasks the role needs that the user has probably done, even when the CV does not list them:
  include a few off-list questions per mock.

## 8. Do-not-say list (`directions.md`)

Every job interview folder keeps one: client or other companies' names, unverified incident names or numbers,
internal facts of the current employer, anything under NDA. Check every polished answer against it.
In `public-encrypted` storage the plain `directions.md` names only the category ("a client's name", "monthly
volume") with what to say instead; the real names and values go in `secret/` (the example `directions.md` names categories the same way).

## 9. Region notes

- Some regions expect a short, formal self-introduction; others expect a conversational "tell me about yourself".
  Ask the user what their target expects, and record it in `directions.md`.
- Salary, notice period, visa or work-permit questions vary by region: prepare a one-line factual answer each,
  confirmed against the user's own situation, never guessed.
