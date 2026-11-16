#!/usr/bin/env python3
"""Privacy check: keeps personal data out of commits (this repo may be public).

    python3 tutor/scripts/privacy_check.py hook       pre-commit: encrypt secret/ > stage .enc copies > scan staged files
    python3 tutor/scripts/privacy_check.py scan-all   scan every tracked or untracked-not-ignored text file (CI, before publishing)

What is detected and masked lives in privacy_patterns.py (phone numbers, emails, resident registration numbers).
Never scanned: secret/ and local/ folders (personal by design, gitignored), binary files.
Violations by themselves: a file inside secret/ or local/, a .env or .env.* file, a non-.enc file inside
secret-encrypted/, and a .enc file that is not openssl output (no Salted__ header).
The hook stages only .enc files, never anything else that sits in secret-encrypted/.
Output never contains a full match: the middle is masked (010-****-5678).
Exit codes: 0 clean, 1 blocked or findings.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import common
from privacy_patterns import Finding, scan_text  # noqa: F401  (re-exported: the public interface lives here)
from secret_crypt import (
    ENCRYPTION_KEY_ENV_NAME,
    KEYCHECK_FILE_NAME,
    SecretCryptError,
    WrongKeyError,
    encrypt_all,
    find_openssl,
    has_pending_secret_deletions,
    keycheck_path,
    load_key,
)
from secret_layout import (
    ENCRYPTED_DIR_NAME,
    ENCRYPTED_SUFFIX,
    REMOTE_COPY_SUFFIX,
    SECRET_DIR_NAME,
    find_encrypted_dirs,
    find_secret_dirs,
    list_encrypted_files,
    list_secret_files,
)

LOCAL_DIR_NAME = "local"
# folders that hold personal data by design: never committed, never scanned
PRIVATE_DIR_NAMES = {SECRET_DIR_NAME, LOCAL_DIR_NAME}
# holds the encryption key: .env and .env.* are never committed
ENV_FILE_NAME = ".env"

# `openssl enc -salt` output starts with this magic, so a .enc file without it is not encrypted content
OPENSSL_SALTED_HEADER = b"Salted__"

# git's own binary heuristic: a NUL byte in the first 8000 bytes
BINARY_PROBE_BYTES = 8000

DECRYPT_COMMAND = "python3 tutor/scripts/secret_crypt.py decrypt"

EXIT_CLEAN = 0
EXIT_BLOCKED = 1


class GitCommandError(RuntimeError):
    """git is missing or exited non-zero"""


# ---------- git ----------


def run_git(root, *arguments):
    """git -C root ... > stdout bytes (the hook environment, e.g. GIT_INDEX_FILE, is inherited on purpose)"""
    try:
        completed = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True)
    except OSError as error:
        raise GitCommandError(f"git not available: {error}") from error
    if completed.returncode != 0:
        reason = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GitCommandError(f"git {arguments[0]} failed: {reason}")
    return completed.stdout


def split_nul_separated_paths(output):
    """git -z output > list of repo-relative posix paths"""
    return [os.fsdecode(raw_path) for raw_path in output.split(b"\0") if raw_path]


def list_staged_paths(root):
    """Staged additions and changes (deletions are not content)"""
    output = run_git(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT")
    return split_nul_separated_paths(output)


def read_staged_content(root, path):
    """What would be committed for path (index content, not the working copy); None when git cannot show it"""
    try:
        return run_git(root, "show", f":{path}")
    except GitCommandError:
        # (gitlinks and similar entries have no blob to read)
        return None


# ---------- path and content rules ----------


def is_key_file_name(file_name):
    return file_name == ENV_FILE_NAME or file_name.startswith(ENV_FILE_NAME + ".")


def is_encrypted_path(path):
    return path.endswith(ENCRYPTED_SUFFIX)


def is_encrypted_copy_path(path):
    """A .enc file inside a secret-encrypted/ folder"""
    return ENCRYPTED_DIR_NAME in PurePosixPath(path).parts[:-1] and is_encrypted_path(path)


def private_path_reason(path):
    """Reason text when path must never be committed (private folder, key file, plaintext in the mirror); None otherwise"""
    parts = PurePosixPath(path).parts
    folder_names, file_name = parts[:-1], parts[-1]
    if any(name in PRIVATE_DIR_NAMES for name in folder_names) or is_key_file_name(file_name):
        return (
            f"{path}: personal file must never be committed "
            f"(secret/ and local/ folders and {ENV_FILE_NAME} files stay on this machine); "
            f"unstage it with `git rm --cached -- {path}`"
        )
    if ENCRYPTED_DIR_NAME in folder_names and not is_encrypted_path(path):
        return (
            f"{path}: only {ENCRYPTED_SUFFIX} files may be committed in {ENCRYPTED_DIR_NAME}/ "
            f"(a plaintext copy must never be committed); unstage it with `git rm --cached -- {path}`"
        )
    return None


def decode_text(content):
    """Bytes > text; None for binary content"""
    if b"\0" in content[:BINARY_PROBE_BYTES]:
        return None
    return content.decode("utf-8", errors="replace")


def inspect_content(path, content):
    """Problem lines for one file: .enc must be openssl output, text must hold no personal data, binary is skipped"""
    if is_encrypted_path(path):
        if content.startswith(OPENSSL_SALTED_HEADER):
            return []
        return [
            f"{path}: not an openssl-encrypted file (no Salted__ header); "
            f"{ENCRYPTED_SUFFIX} files must come from secret_crypt.py encrypt"
        ]
    text = decode_text(content)
    if text is None:
        return []
    return [f"{path}:{finding.line}: {finding.kind} {finding.excerpt}" for finding in scan_text(text)]


def check_staged(root: Path) -> list[str]:
    """Block reasons for the staged files: private paths, bad .enc files, personal data in staged content (empty = may commit)"""
    reasons = []
    for path in list_staged_paths(root):
        private_reason = private_path_reason(path)
        if private_reason:
            reasons.append(private_reason)
            continue
        content = read_staged_content(root, path)
        if content is not None:
            reasons.extend(inspect_content(path, content))
    return reasons


def scan_all(root):
    """Problems in every tracked or untracked-not-ignored file (working copy content); private paths are reported, not read"""
    root = Path(root)
    listed = run_git(root, "ls-files", "-co", "--exclude-standard", "-z")
    reasons = []
    for path in sorted(set(split_nul_separated_paths(listed))):
        private_reason = private_path_reason(path)
        if private_reason:
            reasons.append(private_reason)
            continue
        file_path = root / path
        # (tracked files deleted from disk are listed too)
        if not file_path.is_file() or file_path.is_symlink():
            continue
        reasons.extend(inspect_content(path, file_path.read_bytes()))
    return reasons


# ---------- hook ----------


def list_plaintext_secret_files(root):
    return [secret_file for secret_dir in find_secret_dirs(root) for secret_file in list_secret_files(secret_dir)]


def list_deleted_encrypted_copy_paths(root):
    """Tracked .enc copies in secret-encrypted/ folders that no longer exist on disk"""
    deleted = split_nul_separated_paths(run_git(root, "ls-files", "--deleted", "-z"))
    return [path for path in deleted if is_encrypted_copy_path(path)]


def list_encrypted_copy_paths(root):
    """Exactly the paths the hook may stage: .enc files on disk, deleted tracked .enc files, the keycheck file"""
    paths = [
        encrypted_file.relative_to(root).as_posix()
        for encrypted_dir in find_encrypted_dirs(root)
        for encrypted_file in list_encrypted_files(encrypted_dir)
    ]
    paths.extend(list_deleted_encrypted_copy_paths(root))
    if keycheck_path(root).is_file():
        paths.append(KEYCHECK_FILE_NAME)
    return paths


def stage_encrypted_files(root):
    """git add the .enc copies by explicit literal paths (never a folder: other files next to them stay unstaged)"""
    paths = list_encrypted_copy_paths(root)
    if paths:
        run_git(root, "add", "--", *(f":(literal){path}" for path in paths))


def encrypt_secret_files(root):
    """secret/ plaintext > .enc copies written; returns block reasons (empty = done)"""
    key = load_key(root)
    if key is None:
        return [
            "secret/ files exist but there is no encryption key: run `/spar init` to create one, "
            f"or add {ENCRYPTION_KEY_ENV_NAME}=... to {ENV_FILE_NAME} (the key from your other machine)"
        ]
    if find_openssl() is None:
        return ["openssl not found: install it (on Windows: Git for Windows) so secret/ files can be encrypted"]
    try:
        result = encrypt_all(root, key)
    except WrongKeyError as error:
        return [
            f"{error}: fix {ENCRYPTION_KEY_ENV_NAME} in {ENV_FILE_NAME}, then run `{DECRYPT_COMMAND}` first"
        ]
    except SecretCryptError as error:
        return [f"secret/ files could not be encrypted: {error}"]
    if result.conflicts:
        conflict_lines = [
            f"{conflict.relative_to(root).as_posix()}: differs from its encrypted copy "
            f"(the other side is saved as {conflict.name}{REMOTE_COPY_SUFFIX})"
            for conflict in result.conflicts
        ]
        return conflict_lines + [f"run `{DECRYPT_COMMAND}` first, resolve the conflicts, then commit again"]
    if result.changed:
        print(f"[privacy_check] encrypted {len(result.changed)} secret file(s)")
    if result.deleted:
        print(f"[privacy_check] removed {len(result.deleted)} encrypted copy(ies) of deleted secret file(s)")
    return []


def run_hook(root: Path) -> int:
    """Pre-commit: encrypt secret/ > stage .enc copies > scan staged files; 0 pass, 1 block"""
    root = Path(root)
    try:
        # secret/ work: plaintext to encrypt, or a deleted file whose .enc must go (neither = no key needed)
        has_secret_work = bool(list_plaintext_secret_files(root)) or has_pending_secret_deletions(root)
        reasons = encrypt_secret_files(root) if has_secret_work else []
        if not reasons:
            # (staged whether or not plaintext exists: a pulled or hand-fixed .enc must not be left out)
            stage_encrypted_files(root)
            reasons = check_staged(root)
    except GitCommandError as error:
        reasons = [str(error)]
    if reasons:
        print_problems("commit blocked", reasons)
        return EXIT_BLOCKED
    return EXIT_CLEAN


# ---------- CLI ----------


def print_problems(title, reasons):
    print(f"[privacy_check] {title}: {len(reasons)} problem(s)", file=sys.stderr)
    for reason in reasons:
        print(f"  {reason}", file=sys.stderr)
    print(
        "Move personal data into a secret/ folder (encrypted for you on commit), "
        "or replace it with a placeholder such as 010-0000-0000 or example@example.com.",
        file=sys.stderr,
    )


def command_scan_all(root):
    try:
        reasons = scan_all(root)
    except GitCommandError as error:
        reasons = [str(error)]
    if reasons:
        print_problems("personal data found", reasons)
        return EXIT_BLOCKED
    print("[privacy_check] scan-all: clean")
    return EXIT_CLEAN


def main(argv=None):
    common.use_utf8_console()
    parser = argparse.ArgumentParser(description="Keep personal data out of commits")
    parser.add_argument("command", choices=["hook", "scan-all"])
    arguments = parser.parse_args(argv)
    root = common.repo_root()
    if arguments.command == "hook":
        return run_hook(root)
    return command_scan_all(root)


if __name__ == "__main__":
    sys.exit(main())
