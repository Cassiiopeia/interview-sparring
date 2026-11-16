#!/usr/bin/env python3
"""First-run setup and status for prep/ (the personal records folder).

    python3 tutor/scripts/init.py setup --storage private|local|public-encrypted [--language en] [--input typing|voice]
                                        [--remote URL] [--encrypt-secrets] [--untrack-prep]
    python3 tutor/scripts/init.py status          JSON: settings, key, openssl, hook, origin, what is ready, what is still missing
    python3 tutor/scripts/init.py hooks           only switch the privacy and push hooks on (git config core.hooksPath .githooks)
    python3 tutor/scripts/init.py confirm-remote  record the current origin as private (only after the user said so)

setup can be re-run: settings are updated, files already in prep/ are never overwritten.
It creates prep/ from tutor/templates/prep, saves prep/profile/settings.json, enables the privacy and push hooks
(git config core.hooksPath .githooks), and applies the storage mode:
    private           prep/ is committed to a private repository; --encrypt-secrets also creates an encryption key
    local             prep/.gitignore keeps all of prep/ out of git (no backup); files git already tracks under prep/
                      make setup stop, unless --untrack-prep runs `git rm -r --cached prep` (files stay on disk)
    public-encrypted  public repository; creates an encryption key in .env (never printed) so secret/ folders can be committed encrypted
Leaving local storage deletes prep/.gitignore when it is exactly the generated rule (a customised one is kept with a warning).
--remote URL: a template origin is renamed to upstream first, then URL becomes origin (a public URL is refused for private storage).
Every remote that points at the template gets the push URL `no_push`, so a push there fails.
confirm-remote stores the origin URL (credentials removed) in settings.json; remote_guard accepts it for private storage
only for a non-GitHub host (GitHub is always checked by the API, so a GitHub origin is refused here). Setup never confirms anything by itself.
hooks is for a fresh clone (git config is local, so the hooks start off); it changes nothing else and is safe to repeat.
Exit codes: 0 ok, 1 invalid input or unsafe request, 2 prerequisite missing (openssl).
"""

import argparse
import json
import os
import re
import secrets
import shutil
import sys
from datetime import date
from pathlib import Path

import common
import remote_guard
from init_status import build_status_report
from prep_git_state import (
    GIT_HOOKS_PATH,
    PREP_GITIGNORE_LINES,
    is_generated_local_rule,
    is_git_repository,
    list_tracked_prep_files,
    prep_gitignore_path,
)
from prep_settings import (
    INPUT_MODES,
    INPUT_TYPING,
    STORAGE_LOCAL,
    STORAGE_MODES,
    STORAGE_PRIVATE,
    STORAGE_PUBLIC_ENCRYPTED,
    read_settings,
    write_settings,
)
from privacy_check import ENV_FILE_NAME, GitCommandError, run_git
from remote_guard import (
    get_origin_url,
    is_template_lookalike,
    is_template_origin,
    normalize_remote_url,
)
from remote_setup import configure_remotes
from secret_crypt import ENCRYPTION_KEY_ENV_NAME, find_openssl, load_key

# prep/ file templates (next to the scripts, not under the root: the root can be a temp dir)
TEMPLATE_PREP_DIR = Path(__file__).resolve().parent.parent / "templates" / "prep"

# language code: en, ko, pt-BR (BCP 47 style)
LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
DEFAULT_LANGUAGE = "en"

# hook files that must exist in the hooks folder
HOOK_FILE_NAMES = ("pre-commit", "pre-push")

# secrets.token_urlsafe(32) > 43 URL-safe characters (256 bits)
KEY_RANDOM_BYTES = 32
OWNER_ONLY_FILE_MODE = 0o600

EXIT_OK = 0
EXIT_INVALID_INPUT = 1
EXIT_PREREQUISITE_MISSING = 2


class SetupError(Exception):
    """A request that setup refuses before it changes anything"""

    def __init__(self, message, exit_code=EXIT_INVALID_INPUT):
        super().__init__(message)
        self.exit_code = exit_code




def say(message):
    print(f"[init] {message}")


# ---------- setup: validation ----------


def validate_language(language):
    code = language.strip()
    if not LANGUAGE_CODE_PATTERN.match(code):
        raise SetupError(f"--language must be a language code such as en or ko, got {language!r}")
    return code


def validate_remote(remote, storage):
    """--remote: usable URL, not the template, not public for private storage; returns the cleaned URL (None when not given)"""
    if remote is None:
        return None
    url = remote.strip()
    # (a leading "-" would be read by git as an option)
    if not url or url.startswith("-") or any(character.isspace() or ord(character) < 32 for character in url):
        raise SetupError("--remote is not a usable repository URL")
    if is_template_origin(url):
        raise SetupError(
            "--remote is the public template repository: create your own repository and pass its URL"
        )
    if is_template_lookalike(url):
        say("warning: the path ends in the template's name, so pushes there are refused in every mode; rename the repository")
    if storage == STORAGE_PRIVATE:
        remote_visibility = remote_guard.visibility(url)
        if remote_visibility == remote_guard.VISIBILITY_PUBLIC:
            raise SetupError(
                "storage is private but --remote is a public repository: "
                "make it private, or choose public-encrypted storage"
            )
        if remote_visibility == remote_guard.VISIBILITY_UNKNOWN:
            say("note: could not verify that the remote is private; pushing stays blocked until it is confirmed")
    return url


def is_key_requested(storage, is_encrypt_secrets_requested):
    return storage == STORAGE_PUBLIC_ENCRYPTED or (storage == STORAGE_PRIVATE and is_encrypt_secrets_requested)


def check_local_storage_request(root, storage, is_untrack_prep_requested):
    """Local storage while git still tracks prep/ files: stop unless --untrack-prep; returns the tracked paths"""
    if storage != STORAGE_LOCAL or not is_git_repository(root):
        return []
    tracked_paths = list_tracked_prep_files(root)
    if tracked_paths and not is_untrack_prep_requested:
        raise SetupError(
            f"storage local, but git already tracks {len(tracked_paths)} file(s) under prep/ (for example {tracked_paths[0]}): "
            "ignoring does not untrack them, and earlier commits keep the content. "
            "Run `git rm -r --cached prep` (the files stay on disk) and commit, then run setup again, "
            "or pass --untrack-prep to let setup run it"
        )
    return tracked_paths


# ---------- setup: steps ----------


def copy_template_files(prep):
    """Template > prep/ file by file; existing files stay as they are; returns the created relative paths"""
    if not TEMPLATE_PREP_DIR.is_dir():
        raise SetupError(f"template folder not found: {TEMPLATE_PREP_DIR}", EXIT_PREREQUISITE_MISSING)
    created = []
    for template_file in sorted(TEMPLATE_PREP_DIR.rglob("*")):
        if not template_file.is_file():
            continue
        relative_path = template_file.relative_to(TEMPLATE_PREP_DIR)
        target = prep / relative_path
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_file, target)
        created.append(relative_path.as_posix())
    return created


def save_settings(root, storage, language, input_mode):
    """settings.json: the chosen values replace the old ones; the first creation date and other keys stay"""
    settings = read_settings(root) or {}
    settings.update(storage=storage, language=language, input=input_mode)
    settings.setdefault("created", date.today().isoformat())
    write_settings(root, settings)


def apply_prep_gitignore(root, storage):
    """local: write the generated rule; other modes: delete the generated rule, keep and warn about any other file"""
    ignore_file = prep_gitignore_path(root)
    if storage == STORAGE_LOCAL:
        if not ignore_file.exists():
            with ignore_file.open("w", encoding="utf-8", newline="\n") as ignore_stream:
                ignore_stream.write("\n".join(PREP_GITIGNORE_LINES) + "\n")
            say("prep/.gitignore written: prep/ is never committed")
        elif not is_generated_local_rule(ignore_file):
            say("warning: prep/.gitignore has other rules and was left as it is; add `*` and `!.gitignore` to keep prep/ out of git")
    elif is_generated_local_rule(ignore_file):
        ignore_file.unlink()
        say("removed prep/.gitignore (the local storage rule): prep/ can be committed again")
    elif ignore_file.exists():
        say("warning: prep/.gitignore is not the generated local rule and was left as it is; check it hides nothing you want to commit")


def untrack_prep_files(root, tracked_paths):
    """git rm -r --cached prep: the files stay on disk, the removal is staged"""
    run_git(root, "rm", "-r", "--cached", "-q", "--", "prep")
    say(
        f"untracked {len(tracked_paths)} prep/ file(s): they stay on disk; the removal is staged, commit it "
        "(earlier commits keep the content, so pushes are allowed only to a target confirmed private)"
    )


def restrict_to_owner(file_path):
    """chmod 600 where the OS supports it (Windows ignores most permission bits)"""
    try:
        os.chmod(file_path, OWNER_ONLY_FILE_MODE)
    except OSError:
        pass


def ensure_encryption_key(root):
    """Random key appended to {root}/.env unless one exists (file or environment); returns True when created"""
    if load_key(root) is not None:
        return False
    env_file = Path(root) / ENV_FILE_NAME
    key_line = f"{ENCRYPTION_KEY_ENV_NAME}={secrets.token_urlsafe(KEY_RANDOM_BYTES)}\n"
    existing_content = env_file.read_bytes() if env_file.is_file() else b""
    needs_line_break = bool(existing_content) and not existing_content.endswith(b"\n")
    # (owner-only from the first byte: no window where the key is world-readable; O_BINARY: no CRLF rewriting on Windows)
    open_flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    descriptor = os.open(env_file, open_flags, OWNER_ONLY_FILE_MODE)
    with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as env_stream:
        env_stream.write(("\n" if needs_line_break else "") + key_line)
    restrict_to_owner(env_file)
    return True


def configure_encryption_key(root):
    if ensure_encryption_key(root):
        say(
            f"{ENV_FILE_NAME}: new encryption key created (not shown); back it up outside this repository, "
            "a lost key cannot be recovered"
        )
    else:
        say("encryption key already present, kept")


def configure_hooks(root):
    """core.hooksPath = .githooks so the privacy check (commit) and the push gate (push) run"""
    if not is_git_repository(root):
        say("not a git repository: run `git init` (or clone the template), then run setup again to enable the hooks")
        return
    run_git(root, "config", "core.hooksPath", GIT_HOOKS_PATH)
    missing_hooks = [name for name in HOOK_FILE_NAMES if not (Path(root) / GIT_HOOKS_PATH / name).is_file()]
    if missing_hooks:
        say(f"warning: {GIT_HOOKS_PATH}/{', '.join(missing_hooks)} missing, so that protection cannot run")
    else:
        say(f"privacy and push hooks enabled (core.hooksPath = {GIT_HOOKS_PATH})")


def command_hooks(root):
    """Only core.hooksPath = .githooks (a fresh clone has the hooks off); safe to repeat"""
    if not is_git_repository(root):
        raise SetupError("not a git repository: run `git init` (or clone the template) first")
    configure_hooks(root)
    return EXIT_OK


def print_storage_warnings(storage):
    if storage == STORAGE_LOCAL:
        say("warning: storage local keeps no backup; losing this computer loses prep/")
    elif storage == STORAGE_PUBLIC_ENCRYPTED:
        say(
            "warning: everything in prep/ outside secret/ folders is published; "
            "keep private details in secret/ (committed encrypted) or local/ (never committed)"
        )


def command_setup(root, arguments):
    """Validate everything first, then change: prep/ + settings > storage rules > key > hooks > remotes"""
    storage = arguments.storage
    language = validate_language(arguments.language)
    remote_url = validate_remote(arguments.remote, storage)
    tracked_paths = check_local_storage_request(root, storage, arguments.untrack_prep)
    if arguments.encrypt_secrets and storage == STORAGE_LOCAL:
        say("note: --encrypt-secrets ignored: local storage never commits prep/")
    if arguments.untrack_prep and storage != STORAGE_LOCAL:
        say("note: --untrack-prep ignored: only local storage untracks prep/")
    needs_key = is_key_requested(storage, arguments.encrypt_secrets)
    if needs_key and find_openssl() is None:
        raise SetupError(
            "openssl not found: install it (on Windows: Git for Windows), or choose private or local storage",
            EXIT_PREREQUISITE_MISSING,
        )

    created_files = copy_template_files(Path(root) / "prep")
    save_settings(root, storage, language, arguments.input)
    say(f"prep/ ready ({len(created_files)} file(s) created from the template, existing files kept)")
    apply_prep_gitignore(root, storage)
    if tracked_paths:
        untrack_prep_files(root, tracked_paths)
    if needs_key:
        configure_encryption_key(root)
    configure_hooks(root)
    for note in configure_remotes(root, remote_url):
        say(note)
    print_storage_warnings(storage)
    return EXIT_OK


# ---------- status and confirm-remote ----------


def command_status(root):
    print(json.dumps(build_status_report(root, find_openssl()), ensure_ascii=False, indent=2))
    return EXIT_OK


def command_confirm_remote(root):
    """Record the current origin as private. Run only after the user said it is private; setup never does this"""
    settings = read_settings(root)
    if settings is None:
        raise SetupError("setup has not run yet: run setup first")
    origin = get_origin_url(root)
    if origin is None:
        raise SetupError("no origin remote to confirm: add your own repository as origin first")
    if is_template_origin(origin) or is_template_lookalike(origin):
        raise SetupError("origin is (or looks like a copy of) the public template: it cannot be confirmed as private")
    if remote_guard.parse_github_repository(origin) is not None or remote_guard.is_github_host(origin):
        raise SetupError("GitHub remotes are checked automatically; make the repo private")
    settings["confirmed_private_remote"] = normalize_remote_url(origin)
    write_settings(root, settings)
    say(f"origin confirmed as private by the user: {settings['confirmed_private_remote']}")
    return EXIT_OK


# ---------- CLI ----------


def build_parser():
    parser = argparse.ArgumentParser(description="Set up prep/ and report its state")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="create prep/ and apply a storage mode (safe to re-run)")
    setup.add_argument("--storage", required=True, choices=STORAGE_MODES)
    setup.add_argument("--language", default=DEFAULT_LANGUAGE, help="conversation language code (default en)")
    setup.add_argument("--input", default=INPUT_TYPING, choices=INPUT_MODES)
    setup.add_argument("--remote", help="your own repository URL, becomes origin")
    setup.add_argument("--encrypt-secrets", action="store_true", help="private storage: also create an encryption key")
    setup.add_argument(
        "--untrack-prep", action="store_true", help="local storage: run `git rm -r --cached prep` (files stay on disk)"
    )
    commands.add_parser("status", help="print the state as JSON")
    commands.add_parser("hooks", help="switch the privacy and push hooks on (a fresh clone has them off)")
    commands.add_parser("confirm-remote", help="record the current origin as private (after the user confirmed it)")
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    root = common.repo_root()
    try:
        if arguments.command == "setup":
            return command_setup(root, arguments)
        if arguments.command == "confirm-remote":
            return command_confirm_remote(root)
        if arguments.command == "hooks":
            return command_hooks(root)
        return command_status(root)
    except SetupError as error:
        print(f"[init] {error}", file=sys.stderr)
        return error.exit_code
    except (ValueError, GitCommandError) as error:
        # (damaged settings.json, or git failed)
        print(f"[init] {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
