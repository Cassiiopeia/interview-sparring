# Language pack: Korean (ko)

The single place for Korean speech rules. Applies when `settings.json` `language` is `ko`, to the tutor's replies,
polished answers and grading of spoken answers. Draft check: `draft_check.py --lang ko` with `ko.patterns.txt`
(sentence cap 80 characters, three same endings in a row flagged).

## 1. Sentence shape

- **End each sentence with ~습니다 / ~입니다, and put the reason in the next sentence.**
  ✗ `센서 값을 모았는데 빠진 날이 많아서 정리하고 그래서 기준도 바꿨고…`
  ○ `센서 값을 모았습니다. 빠진 날이 많았습니다. 그래서 처리 기준을 바꿨습니다.`
- Chains of ~는데 / ~고 / ~해서 are the spoken form of a run-on loop: split them. Each link becomes its own sentence.
- **Never ~했던 것 같습니다.** It sounds like the speaker is unsure of their own experience. Say ~했습니다, or say
  `그 부분은 정확히 확인하지 못했습니다` if it really is unsure.
- One idea per sentence; one breath per sentence. Over 80 characters > split.
- Mix sentence lengths. Three sentences ending in the same 4 characters in a row (`했습니다. 했습니다. 했습니다.`)
  read as machine-written: vary the verb or join two.

## 2. Written style is not spoken style

| ✗ written / abstract | ○ spoken |
|---|---|
| `~함으로써` | `~해서` / split into two sentences |
| `~에 있어서` | name the thing directly |
| `~하고자 합니다` | `~하려고 합니다` / `~하고 싶습니다` |
| `~의 중요성을 깨달았습니다` | what you saw, then what you now do differently |
| `관심을 가지게 되었습니다` as a closing | the scene that started it, then what you want to look at |
| `마음에 걸렸습니다` (a feeling never reported) | the observed fact + the question it raised |

The full list lives in `ko.patterns.txt`. A phrase the user rejects goes to `coaching.md` "Rejected phrasing"
(core.md §6). The pattern file is engine-owned: it changes only through an upstream proposal (memory.md §3), never by
editing `*.patterns.txt` in a user's repository.

## 3. Filler and hesitation words

- `음`, `어`, `그`, `약간`, `뭔가`, `좀`, `이제`, `사실` at the start of sentences: point them out only when they appear
  in most sentences of one answer. A few are natural speech.
- In voice input, fillers are dictation artifacts first (voice.md): count them, do not grade each one.
- `네 그렇습니다` as a whole answer under pressure > restate the conclusion and go to the judgement slot
  (grading.md §3).

## 4. Do not polish the user's rough wording

- Fix grammar and facts only. **Keep the user's expressions**, even when they sound plain or a little rough: that
  plainness is what makes the answer theirs and explainable in a follow-up.
- Keep the user's own word for a thing (`빠진 값`) rather than swapping in a formal term (`결측 데이터 처리 체계`),
  unless the formal term is what the interviewer uses.
- Mark surviving user wording in drafts so a later session does not smooth it (hints.md §3).

## 5. Register

- Interview answers: 합쇼체 (~습니다) throughout. No 해요체 mixed in mid-answer.
- Tutor replies to the user: plain and short. In research mode the user may answer in 반말 as if explaining to a friend
  (modes/research.md); the polished interview answer is still 합쇼체.
- Titles: address the interviewer by role (`면접관님`, `교수님`), never by a guessed name.
