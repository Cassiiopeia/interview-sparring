# interview-sparring

**Don't fork this repository — a fork of a public repository is public, and your interview notes would be too.**
Make your own **private** repository: with **"Use this template"** when your host offers it, or by cloning this
repository and giving `/spar init` an empty private repository of your own.

An AI sparring partner for interview prep that runs in Claude Code (and other agents that read `AGENTS.md`).
You talk; it asks the questions an interviewer would really ask, cuts in on the biggest problem, shows you a polished
answer built from your own words, and makes you answer again. You never edit a file or type a command.

[한국어 README](README.ko.md)

## Quick start

1. Get your own copy, either way:
   - **Use this template** > create a **private** repository > clone it; or
   - if there is no such button: clone this repository > create an **empty private** repository on your host >
     give that URL to `/spar init` (it becomes your `origin`; this repository is kept as `upstream`).
2. Open the folder in Claude Code.
3. Type `/spar init` and answer the questions.

After that, `/spar` alone starts a practice session where you left off.

## What it does

From "where should I apply?" to "what did they ask?" — one folder per interview, and your material carries over to the
next one.

| Stage | Command | What happens |
|---|---|---|
| Explore | `/spar explore` | goal, candidates from official sources, deadline calendar, contact drafts |
| Apply | `/spar new`, `/spar apply` | interview folder, checklist from the notice, the application form field by field (you press submit) |
| Write | `/spar writing` | drafts in your words, edits that keep your voice, finals moved to `submitted/` |
| Practise | `/spar`, `/spar research` | one question at a time from what you submitted; you talk, it polishes and asks again |
| Interview | `/spar mock` | a full mock interview without interruptions, then a debrief; or "record only" while a friend plays the interviewer |
| Debrief | `/spar debrief` | the questions you were really asked, reactions, new facts — ready for the next round |
| Result | `/spar result` | outcome, next steps, what carries over |

How a practice turn looks: you answer freely (rambling is fine) > the tutor arranges your words into answer slots
(`[Conclusion] [Judgement] [What I did] [Lesson]`) > says briefly what changed and why > asks the same question again.
It never invents an experience, a feeling or a number; it checks every answer against your facts ledger.

See `example/en-job/` (a fictional job applicant) and `example/ko-oral-exam/` (a fictional graduate-school applicant,
in Korean) for what the records look like after a few sessions.

## Where your records live — storage modes

`/spar init` asks first. Your records are in `prep/`.

| Mode | What happens | Backup |
|---|---|---|
| **Private repository** (recommended) | `prep/` is committed to your private repository; `secret/` folders can be encrypted too | yes |
| **This computer only** | `prep/` never enters git | **none** |
| **Public repository + encryption** | `secret/` folders are committed encrypted; **everything else in `prep/` is public** | yes |

Inside `prep/`, folder names set the sensitivity: `local/` never leaves your computer (recordings, certificates,
phone numbers), `secret/` is committed only as encrypted `.enc` files (confidential numbers, full submitted
documents), everything else is ordinary.

## Practising by voice

Speaking is closer to the real interview than typing, and the tutor reads dictated text as a transcript (sound-alike
errors in names are not graded; it learns your corrections).

- **Phone keyboard dictation** is accurate for many languages — good for practising away from your desk.
- The Claude Code microphone works at the desk; check its language setting.
- Some desktop or remote agent apps ship an **English-only speech model** by default. Switch to a multilingual model
  before practising in another language.

## Privacy: what is guaranteed and what is not

Guaranteed by the scripts (with tests):
- A pre-commit hook blocks phone numbers, email addresses, resident registration numbers, `.env` files and any
  plaintext from `secret/` or `local/`, and encrypts `secret/` before each commit (AES-256-CBC, PBKDF2, `openssl`).
- A pre-push hook refuses to push your records to the public template, and — in private mode — to a GitHub repository
  that answers as public.

Guaranteed by the tutor's rules (no hook enforces them):
- Commit messages carry no content (`practice: 1 session`).
- Never bypass the hooks (`--no-verify`).

Limits:
- **Encrypted file names and folder layout are visible.** Only contents are encrypted.
- **A lost encryption key cannot be recovered.** Back it up in a password manager.
- Visibility of a non-GitHub remote, or of an SSH host alias that points to GitHub, cannot be checked: it relies on
  your answer when the tutor asks whether the repository is private.
- Pattern checks catch common formats, not everything. Names are your call: keep them in `secret/`.

## Updating the engine

`/spar update` shows what would change and, after you confirm, replaces only the engine's files (`tutor/`,
`example/`, `tests/`, `CLAUDE.md`, `AGENTS.md`, `.claude/commands/`, `.agents/skills/`, the READMEs, `.gitignore`,
`.gitattributes`, `.githooks/`, `.github/`, `pyproject.toml`). Your `prep/` and `.env` are never touched.

## Requirements

- Claude Code (or an agent that reads `AGENTS.md`)
- Python 3.10+ (standard library only) — macOS and Windows
- git; `openssl` for encryption (bundled with macOS and Git for Windows)

## Contributing

- **Don't run `/spar init` or `init.py setup` in your engine checkout.** Setup writes `prep/`, settings, hooks and keys
  meant for a personal copy. Test with a temporary copy instead.
- Rules live in `tutor/rules/` (English). `CLAUDE.md` and `.claude/commands/spar.md` are the sources; after editing
  them run `python3 tutor/scripts/sync_agents.py write` (AGENTS.md and `.agents/skills/` are generated).
- Before a pull request: `python3 -m pytest` and `python3 tutor/scripts/privacy_check.py scan-all`.
- CI (`.github/workflows/test.yml`) runs only in the upstream repository; copies made from the template skip it, so
  run the tests locally there.
- New language: add `tutor/rules/language/<code>.md` and `<code>.patterns.txt`. New interview type: add
  `tutor/rules/interview-types/<kind>.md`.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
