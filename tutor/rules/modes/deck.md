# Mode: deck (optional) — one question per slide, practised aloud

`/spar deck`. Only when a presentation tool is available to the agent (for example a slide or presentation skill).
Without one, say so and use train mode; nothing in the engine requires it.

The deck lives in `interviews/<x>/practice/deck/`: one slide per question, each with the question, keyword cards in
answer-frame order, and a script.

## 1. Every turn gives four things

1. **The slide** — the question slide being practised (create it if the question has no slide yet).
2. **The example script (v0)** — the user's words arranged in the answer frame, with slot labels, sent in full in chat
   (core.md §4). Never "unchanged, see above".
3. **Feedback** — short, biggest problem first.
4. **The question quoted again.**

The user reads, says "no" where it is wrong, and reads again. When the user reads a script aloud, the reply is not
just a verdict: it is the next version of the script built from what they said, saved and shown in full.

## 2. Slide and script rules

- The slide's keyword cards use the same slot names and order as the script.
- **One script per slide: the one being practised now.** Older versions go to a separate file; other questions'
  scripts never pile up under it.
- Before writing a script, read the slide notes **and** the linked research or experience card where the user already
  settled the key reason. A general-purpose script that ignores what the user settled is wrong.
- Build the story line first (grading.md §2) and order the cards by it.
- Fix the files first, then show or capture the slide, so slide and script never disagree.

## 3. Staying on the slide

- While one slide is being practised, no other question (not even a follow-up) is opened. New material is checked
  against the ledger and parked.
- A fact request covers only what this slide needs: one table, which card it belongs to, then back to the slide.
- "This should be added" = change the slide's cards and notes now; chat says only "slide N changed — what changed —
  read it".
- End each reply with where to read: "Read the script on slide 3."
