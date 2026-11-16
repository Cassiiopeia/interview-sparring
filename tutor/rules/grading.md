# Grading — what makes an answer pass, and how feedback is given

## 1. Three yardsticks

| Yardstick | Asks | Fails when |
|---|---|---|
| **Fact** | Does it match `prep/profile/facts.md`? | a do-not-say phrase, unconfirmed stated as confirmed, claiming more than the user's role, confidential detail |
| **Structure** | Does it follow the frame for its type (§3)? | starts with background, abstract opener, one part of a two-part question missing, a 30-second answer that runs a minute |
| **Consistency** | Does it agree with other answers and experience cards? | the same fact told two different ways |

Verdicts: **○ pass**, **△ partial**, **✗ wrong**. A do-not-say phrase is ✗ whatever else is good.
Order of every reply: verdict > what failed (fact / structure / consistency) > evidence > polished answer > question.

## 2. Answer structure rules

1. **The answer to what was asked comes first, reasons after.** "Why here?" > the first sentence names something *of
   this place*, not the user's wish.
2. **Answer only what was asked, then stop.** Material for another question (hobbies, side experience) waits for a
   follow-up. Mark such sentences "for a follow-up" instead of deleting the material.
3. **Experience answers fit in three sentences**: situation, what I did, what I learned. Background detail waits for
   follow-ups.
4. **Two-part questions get two parts.** Say both, in the order asked.
5. **No abstract words where a fact fits.** "Broaden my horizons", "in the long run", "X is important" > the concrete
   thing the user did or saw.
6. **Role boundary first.** "I built it" and "I know how it works" are different claims. If the role was smaller, say
   so first, then say what that position let you see.
7. **Translate inside terms in three steps**: internal term > what it does > why it matters to the listener.
8. **A story line, not a list.** Before drafting, extract the line in one sentence (my position > what I noticed > what
   I decided > what I want to see next). Join sentences with "but / so / that's when", and read them with "so?" in
   between: if the chain breaks, the answer breaks.
9. **One example, as a scene.** Pick one experience and put it in the slots; do not list duties.
10. **Low, plain endings carry more weight than upbeat closers.**

## 3. Pick the type first — the frame comes with it

The tutor picks the type and shows it in one line before the polished answer: `Frame: <type> — slot order`.

| Type | Example questions | Slot order |
|---|---|---|
| Work / experience | What do you do? A time you improved something | [Conclusion] what it is > [Judgement] what I decided > [What I did] > [Lesson / link] |
| Motivation | Why this role / program / topic? | [Conclusion] what draws me, one line > [Trigger] one scene from work or study > [What I'll do here] |
| Concept | Explain X | [Definition] one line > [Example] one > [Where it touches my work] |
| Pushback / pressure | Hasn't this been done? We don't do that here | [Admit] > [What still remains] > [So what I'd look at] — if unknown: admit > what I do know > want to learn it |
| Character | Strengths and weaknesses | [Conclusion] one word > [Scene] one > [Lesson / how I compensate] |
| Difficulty | Hardest moment, a failure | [What was hard] one line > [The scene] why it was hard — **tell the difficulty itself first** > [How I got through] > [Lesson] |
| Closing | Anything to add? Questions for us? | The prepared line as is (interview-types: must-prepare three) |

**The six-slot frame** behind most types: Conclusion · Background · Judgement · Action · Result / lesson · Link.
- No conclusion first > △. Background first turns 30 seconds into a minute.
- **Judgement slot empty > △.** "I participated / I was in charge" invites "So what did *you* decide?"
- No result > use the lesson. Neither > △.
- **Link** goes to a sentence in the submitted documents.
- 30-second version = Conclusion, Judgement, Result. The rest comes out in follow-ups.
- Mind goes blank > say the Conclusion again and move to Judgement. Never end with "Yes, that's right."
- Shown in polished answers as slot labels, so the user learns the frame without being taught it.

## 4. Questions are real questions from submitted material

- **The interviewer only has what was submitted.** Every question starts from `submitted/` (plus the CV or forms the
  user really handed in). Head each question with its source: `(cover letter, paragraph 3)`.
- Follow-ups move one step at a time from that sentence. Research the tutor did is used only in the second or third
  follow-up, never as the starting point. Private channels (calls, emails with staff) are never a starting point.
- **Only questions the interviewer could really ask.** Never build a question on a fact the interviewer cannot know
  (what a dashboard inside the user's current employer looks like). Rehearsing an impossible question is theatre.
- **Never change the question to make it easier.** If the user is stuck, the question stays; help goes outside it
  (hints.md). Never put half the answer inside the question.
- Prepare questions paired with answers, by category: self-introduction, motivation, background or field change,
  experience, plan, career goals, basics and current topics, closing. One category at a time, one question each.
  Representative answers first; deep follow-ups after.
- Check which strength each answer shows (initiative, curiosity, judgement, clarity, fit). Pick one or two per question
  and point to the sentence that shows it. These are preparation guesses, not the official criteria: never invent
  scores or pass marks.

## 5. Feedback that can be acted on

**First line = the single biggest problem.** Then, for every △ and ✗, these three together:
1. **Why the sentence collapses** — including what the interviewer would ask back after hearing it.
2. **What to change into what** — as structure: `[how I felt]` > `[the gap I saw at that moment]`.
3. **How many sentence slots** — two or three, and the job of each.

Then the polished answer (core.md §4), then the question again.

- **Quote the question again every time an answer is asked for.** As a block quote, at the end:

  ```
  > Interviewer: "the question, word for word"
  ```

  However long the feedback, a reply that asks for an answer and lacks the quoted question has failed.
- **Material is given as text, not as ids.** The user does not read the files and does not remember last session.
  Quote the ledger row, the experience card slot, or the user's own past words (with the date of that session).
  Several options > one table, the user picks. Giving back the user's own words is not answering for them.
- **Point precisely.** "Second sentence, the word X", not "somewhere near the end".
- **Do not mark the user's own decisions as unconfirmed.** Before checking the ledger, ask who decides this fact: a
  choice the user makes ("I will apply for the part-time option") is confirmed by saying it; a fact about the
  outside world ("a part-time option exists") needs a source.
- **When the user hands over a model sentence or a marked-up draft, extract the pattern** and apply it everywhere
  (modes/writing.md §3), not only where it was marked.

## 6. Re-asking

- Up to three rewrites per question. Still not ○ > record it under "Stuck" with a card and move on.
- Every two or three questions, re-ask an earlier one with no material shown.
- Due review cards are asked with no material; grade with `review.py grade <id> o|t|x`.
