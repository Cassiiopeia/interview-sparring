# Voice practice — reading dictated answers

On when `settings.json` has `"input": "voice"`, or whenever the text clearly came from speech-to-text. Practising out
loud is closer to the real interview than typing, so voice is a first-class mode.

## 1. Read the text as a transcript

- **Sound-alike errors in names and proper nouns are not graded.** Above the verdict add one line:
  `Read as dictation: "<heard>" = <meant>`.
- New sound-alike errors go into `prep/profile/transcription.md` (heard > actual) and are read correctly from then on.
- **Fact words are still pointed out**, even when they may be a dictation error: if a term changed into a different
  term, that is what the interviewer would hear too.
- Asides inside the answer ("is there a better word for this?", "I don't like this sentence") are requests to the
  tutor, not part of the answer. Lift them out and answer them separately.
- Restarts and repeated phrases are a sign of real speaking. Treat them as sentence splitting and length issues only,
  never as factual errors.

## 2. Keep replies short

- Dictated answers are long and loose; feedback is short. Biggest problem first (core.md §1), then the polished answer.
- **End with the question quoted again.** The user is often on a phone, reading aloud, and does not scroll back.
- Never write "unchanged, see above". If the polished answer is the same, send it again in full.
- Long polished answers are sent slot by slot so each fits one screen.

## 3. Recordings of real conversations

- A transcript of a real call or interview (just after it ended) is saved raw in `local/` only.
- The debrief keeps the questions, the other side's reactions and new facts — not the full transcript, and nothing
  about third parties mentioned in passing.
- When the transcript mixes two speakers, separate question and answer before using it.

## 4. Tools the user can dictate with (tell them during init)

| Tool | Notes |
|---|---|
| Phone keyboard microphone | accurate for many languages; good when practising away from the desk |
| Claude Code microphone (desktop) | convenient at the desk; check the language setting |
| Remote or desktop agent apps | some ship an English-only speech model by default: switch to a multilingual model before practising in another language |

Do not promise accuracy for a tool the tutor has not seen working for this user. Ask how the first dictated answer
looked and add fixes to `transcription.md`.
