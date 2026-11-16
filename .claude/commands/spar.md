---
description: Open an interview sparring session - init, new, explore, apply, writing, research, mock, debrief, result, deck, update; no argument trains one question
---

# /spar — interview sparring session

Argument: `$ARGUMENTS` (empty = train). Read `CLAUDE.md` and the rules it lists before replying.
On Windows run scripts with `py -3` instead of `python3`.

## 1. Session start (every mode except `update`)

1. `python3 tutor/scripts/init.py status`
   - `"hooks": false` (a fresh clone has the privacy hooks off) > `python3 tutor/scripts/init.py hooks` before anything
     else, and tell the user in one line that the privacy hooks are now on.
   - `"missing": ["setup has not run yet"]` > go to `init` (tutor/rules/modes/init.md), whatever the argument was.
   - Reply in `language`. Voice input (`input: voice`) > tutor/rules/voice.md applies.
2. `has_key: true` > `python3 tutor/scripts/secret_crypt.py decrypt`
   - exit 3: a conflict. Tell the user which file has a `.remote` copy; nothing was overwritten; merge together.
   - exit 4: the key in `.env` does not open these files. Say so; never create a new key over it.
   - exit 2: openssl or key missing. Say which, and continue without the secret files.
   - exit 1: the operation failed. Report its one-line error, continue without the secret files, add a task to fix it.
3. Read `prep/status.md`, `prep/profile/coaching.md`, and for the active interview `directions.md`, `tasks.md` and
   the latest file in `practice/`.
4. A task with a deadline comes first: its next small step is the first question.
5. `python3 tutor/scripts/review.py due` > due cards one at a time (only those tied to submitted material).
6. Say where things stand in one line, then ask **one** question, quoted.

## 2. Modes

| Argument | Do | Rules |
|---|---|---|
| (none) | train: one question, polished answer from the user's words, ask again | modes/train.md |
| `init` | first-time setup through conversation | modes/init.md |
| `new` | create an interview folder: ask organization (short ASCII name), kind (`job` or `oral-exam`), month and date if known, then `python3 tutor/scripts/interview_folder.py new --date YYYY-MM --org NAME --kind KIND [--interview-date YYYY-MM-DD]`, then continue with apply | modes/apply.md |
| `explore` | goal, candidates, calendar, contacts, decide | modes/explore.md |
| `apply` | official notice > checklist > application site field by field | modes/apply.md |
| `writing` | application documents; on "I submitted", copy finals and derive questions | modes/writing.md |
| `research` | understand a concept or the organization before answering | modes/research.md |
| `mock` | full mock interview, no corrections until the end; "record only" for a live mock | modes/mock.md |
| `debrief` | right after a real interview: asked questions, reactions, new facts | modes/debrief.md |
| `result` | outcome and next steps | modes/result.md |
| `deck` | one slide per question (only with a presentation tool) | modes/deck.md |
| `update` | engine update, see §3 | — |

The interview type pack (`tutor/rules/interview-types/<kind>.md`) and language pack
(`tutor/rules/language/<language>.md`) apply in every mode.

## 3. update

1. `python3 tutor/scripts/update.py plan` and show the list (added / changed / removed). Only engine paths change;
   `prep/` is never touched.
2. Ask the user to confirm. On yes: `python3 tutor/scripts/update.py apply --yes`.
   A refusal (uncommitted engine changes, an ignored file in the way) is explained in plain words, not forced.
3. `python3 tutor/scripts/sync_agents.py check`; review the diff; commit `chore: engine update`.

## 4. Session end

Follow tutor/rules/core.md §5: practice log, cards, experience cards, facts (after confirmation), tasks,
`python3 tutor/scripts/interview_folder.py status`, `status.md` next session, then commit with a content-free
message. Push only when `python3 tutor/scripts/remote_guard.py can-push` exits 0; never `--no-verify`.
