# Privacy — where personal data may go, and what the tutor never does

The engine may live in a public repository and `prep/` may be pushed. One leaked name or number in a commit stays in
history forever. When unsure, choose the safer place.

## 1. Folder name = sensitivity

| Folder | Rule | Examples |
|---|---|---|
| `**/local/` | never in git (`.gitignore`) | recordings, transcripts of private calls, certificates, exam tickets, phone numbers, addresses |
| `**/secret/` | plaintext never in git; `secret_crypt.py` writes one `.enc` per file into `secret-encrypted/`, which is committed | confidential numbers, full submitted documents, real names |
| anything else | ordinary | rules, questions, research, tasks, practice logs |

- The tutor picks the folder when it saves. Ambiguous > the safer one.
- Encrypted **file names and folder layout stay visible**: name files inside `secret/` without content
  (`notes-1.md`, not the person's name).
- Contacts (phone, email, address) go to `local/` only. `contacts.md` keeps a summary, never the address.

## 2. Storage modes (`prep/profile/settings.json` → `storage`)

| Mode | What happens |
|---|---|
| `private` | `prep/` is committed to the user's private repository. Encrypting `secret/` is optional |
| `local` | all of `prep/` is kept out of git (`prep/.gitignore`). No backup: say so plainly |
| `public-encrypted` | public repository. `secret/` must be encrypted; **everything else in `prep/` is public** |

In `public-encrypted` mode, route names of people and organizations, do-not-say facts, confidential numbers and
contacts into `secret/` or `local/`. Ordinary files carry roles ("the hiring manager"), not names.
Folder names are visible too: use a neutral short name in `interview_folder.py new --org` (`company-a`), and
keep the real name inside `secret/`.

## 3. Encryption key

- `SPARRING_ENCRYPTION_KEY` in the root `.env` (never committed). `init.py setup` creates it; it is never printed.
- Before creating one, warn first: **a lost key cannot be recovered**. Then suggest a backup place (a password
  manager, or a repository secret) and let the user do the copying.
- New computer: the user puts the key in `.env`; the session start runs `secret_crypt.py decrypt`.
- Decrypt exit codes 1/2/3/4 (failure, prerequisite missing, conflict, wrong key) and what to do for each:
  `.claude/commands/spar.md` §1 step 2. A wrong key never gets a new key created over it.

## 4. Commits

- The pre-commit hook (`privacy_check.py hook`) encrypts `secret/`, stages only `.enc` files, and blocks phone numbers,
  emails, resident numbers, `.env` files, and any plaintext from `secret/` or `local/`.
- **Commit messages carry no content.** `practice: 1 session`, `prep: facts updated`, `writing: draft 2`. Never a
  name, organization, question text or score.
- Stage only the paths the tutor changed in this session.
- **Deleting a secret file is just deleting the plaintext** in `secret/` (not the `secret/` folder: its sync record goes
  with it). The hook removes the encrypted copy and stages the removal. If git says "nothing to commit", the hook has
  already staged the removal: commit again.
- Before publishing anything: `python3 tutor/scripts/privacy_check.py scan-all`.

## 5. Things the tutor never does

- Never `git push --no-verify`, never `git commit --no-verify`, never a force push.
- Push only when `python3 tutor/scripts/remote_guard.py can-push` exits 0. A refusal is reported to the user as is,
  not worked around.
- Run `init.py confirm-remote` only after the user has said in their own words that the remote is private. Never
  infer it. A remote that looks like a GitHub alias on another host (an SSH host alias) is checked only by the user's
  answer: ask plainly.
- Never run `init.py setup` inside the engine's own development checkout (the template repository itself). If
  `init.py status` shows `origin_is_template: true` and the user is working on the engine, stop and say so.
- Never print the encryption key, a token, or a credential in a URL.
- Never put full call transcripts in ordinary files: the raw transcript goes to `local/`, the debrief keeps only
  questions and reactions.
- Never copy material about third parties mentioned in passing (someone else's story, another candidate).

## 6. Sending anything outside

Upstream issues or suggestions (memory.md §3) are drafted with every personal detail removed and sent only after the
user approves the exact text.
