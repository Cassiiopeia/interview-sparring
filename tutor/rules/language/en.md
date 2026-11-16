# Language pack: English (en)

Applies when `settings.json` `language` is `en`, and as the fallback pack. Draft check: `draft_check.py --lang en` with `en.patterns.txt`
(sentence cap 30 words, three sentences ending in the same word in a row flagged).

## 1. Sentence shape

- **Short declarative sentences.** One idea, one breath. Over 30 words > split.
  ✗ "The tracking page was slow every evening and support got tickets so I looked at the cache and changed it."
  ○ "The tracking page was slow every evening. I measured it first. The cache was the cause, so I changed it."
- Put the reason in the next sentence, not in a "which ... because ... so" chain.
- Vary sentence length; avoid three sentences that end on the same word.

## 2. No hedging

| ✗ | ○ |
|---|---|
| "I believe that..." / "I feel like..." | state it: "The cause was X." |
| "I think that maybe I helped..." | the real scope: "I wrote the parser; the team lead reviewed it." |
| "kind of / sort of" | drop it, or give the exact amount |
| "I'm not 100% sure but..." for something unchecked | "I haven't checked that. What I know is up to X." |

## 3. No clichés or buzzwords

"passionate about", "in today's fast-paced world", "leverage synergies", "think outside the box", "proven track
record", "hit the ground running", "dynamic environment", "wear many hats", "taught me the importance of",
"sparked my interest", "plays a crucial role", "delve into", "a testament to".
They answer nothing and invite "such as?". Replace each with the concrete scene. The full list lives in
`en.patterns.txt`. A phrase the user rejects goes to `coaching.md` "Rejected phrasing" (core.md §6). The pattern file
is engine-owned: it changes only through an upstream proposal (memory.md §3), never by editing `*.patterns.txt` in a
user's repository.

## 4. Do not polish the user's rough wording

- Fix grammar and facts only; keep the user's expressions and their own word for things.
- Contractions are fine in speech ("I didn't", "that's").
- Never close a paragraph with a feeling the user did not report ("It really moved me"). Close with what was observed
  and the question it raised.

## 5. Register

- Plain professional spoken English. First person, active voice: "I decided", not "it was decided".
- Address interviewers by role or as they introduced themselves; never guess a name or title.
