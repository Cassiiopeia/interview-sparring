# Mode: init — first-time setup through conversation

`/spar init`, or any session where `init.py status` shows `"missing": ["setup has not run yet"]`.
The user answers questions; the tutor runs every command. One question at a time.

## 0. Before anything

- `python3 tutor/scripts/init.py status` (Windows: `py -3 ...`). Read `storage`, `origin`, `origin_is_template`,
  `openssl`, `ready`, `missing`.
- `origin_is_template: true` and the user says they are working on the engine itself > stop. Setup never runs in the
  engine's own checkout (privacy.md §5).
- Language: answer in the language of the user's first message and confirm it in one line ("I'll continue in Korean;
  tell me if you prefer another language"). That code goes into `--language`.

## 1. Storage mode (first question)

Explain the three in one small table and ask which one:

| Choice | Means |
|---|---|
| Private repository (recommended) | records are backed up in your own private repo |
| This computer only | nothing leaves this computer; no backup |
| Public repository + encryption | the repo is public; only `secret/` folders are encrypted, everything else in `prep/` is public |

- Private: ask for the URL of their own **private** repository (they create it; never the template). If it is not on
  GitHub, ask "Is this repository private?" and run `init.py confirm-remote` only after a clear yes.
- Private and they want encrypted secrets too > `--encrypt-secrets`.
- Public + encryption: **first** say a lost key cannot be recovered. `openssl` missing (`"openssl": null`) > this mode
  is not available; offer the other two.
- This computer only, and git already tracks files under `prep/` > explain, then `--untrack-prep` only with their yes.

Run: `python3 tutor/scripts/init.py setup --storage <mode> --language <code> --input <typing|voice> [--remote URL]
[--encrypt-secrets] [--untrack-prep]`. Setup can be re-run; it never overwrites files in `prep/`.
When a key was created: tell the user where it is (`.env`), that it is never shown, and suggest a password manager
backup they copy themselves.

## 2. What they are preparing for

One at a time:
1. Kind: job interview or oral exam / admission interview (sets the interview-type pack).
2. Where, and the date if known. Not decided yet > modes/explore.md instead of creating a folder.
3. Create the folder: `python3 tutor/scripts/interview_folder.py new --date YYYY-MM --org <short-ascii-name>
   --kind <job|oral-exam> [--interview-date YYYY-MM-DD]`. Names are ASCII; a Korean-only name needs a romanized short
   name (ask the user which one).
4. Notice or job posting: ask them to paste it or give the link; save it in `about/` with source and date, fill
   `checklist.md` (modes/apply.md).

## 3. Documents

- Already submitted something? Ask them to paste it; save under `submitted/` (or `secret/` when the storage mode needs
  it), then derive the first lines of `questions.md` from it (grading.md §4).
- Still writing? Save drafts under `writing/`; the writing mode takes it from there.
- CV or forms: only the facts that were submitted (role, dates, certificates).

## 4. Facts ledger draft

From what they pasted and said, propose ledger rows **one at a time**: "Your current role is X since Y — confirmed?"
- Confirmed > `confirmed`. Not sure > `unconfirmed` with a task to check.
- Ask which topics must never be said in the interview > `do-not-say` rows and the folder's `directions.md`.
  In `public-encrypted` storage, plain files hold only the category ("a client's name"); real names and values go in
  `secret/`.
- Confidential numbers > `confidential`, stored per privacy.md.
- One or two big experiences > first experience cards with Background and Action only (memory.md §4). The user's
  judgement and lessons come in practice.

## 5. Practice style

- Typing or voice? Voice > tell them about dictation tools (voice.md §4) and set `--input voice` (re-run setup).
- Example answers first (default), or "let me try first"? Record the choice in `coaching.md` > Rules from you.

## 6. Finish

- `python3 tutor/scripts/interview_folder.py status` to build the board in `status.md`; fill Goal, Stage, Next session.
- Show a two-column table: **ready / still empty** (from `init.py status` plus what the conversation filled).
- Commit (`prep: init`), push only per privacy.md §5.
- Then ask the first question: the self-introduction, or the next step of a deadline task if one is open.
