#!/usr/bin/env python3
"""Secret folder encryption: each secret/ folder is mirrored into a committed secret-encrypted/ folder.

secret/ stays gitignored; secret-encrypted/ holds one AES-256-CBC .enc file per secret file (openssl).
File names are not secret: only contents are encrypted, so names and folder layout are visible in secret-encrypted/.

    python3 tutor/scripts/secret_crypt.py encrypt   secret/ > secret-encrypted/*.enc (never overwrites a newer .enc)
    python3 tutor/scripts/secret_crypt.py decrypt   secret-encrypted/*.enc > secret/ (never overwrites a local edit)
    python3 tutor/scripts/secret_crypt.py check     JSON status: openssl, key, secret folders, files not encrypted yet

Key: SPARRING_ENCRYPTION_KEY in {root}/.env, else the environment variable.
Key check: {root}/.sparring-keycheck.enc (committed) is verified before every encrypt/decrypt.
Sync state: secret/.sync-state.json keeps the last synced hash per file (base); local, remote and base are
compared three-way, so a change on one side is carried over and a change on both sides is a conflict.
Conflict: the other side is saved as <name>.remote and nothing is overwritten. To resolve, merge into the local file
and delete its .enc then encrypt (keep mine), or copy <name>.remote over the local file then decrypt (take theirs).
Fast-forward: when only the remote changed, the replaced local content is kept as <name>.previous (single slot).
Exit codes: 0 ok, 1 operation failed, 2 openssl or key missing (or bad usage), 3 conflicts, 4 wrong key.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import NamedTuple

import common
from secret_layout import (  # noqa: F401  (encrypted_dir_for is re-exported as part of the public interface)
    PARTIAL_FILE_SUFFIX,
    REMOTE_COPY_SUFFIX,
    encrypted_dir_for,
    encrypted_file_for,
    find_encrypted_dirs,
    find_secret_dirs,
    list_encrypted_files,
    list_secret_files,
    previous_copy_path_for,
    remote_copy_path_for,
    secret_dir_for,
    secret_file_for,
    sync_state_path,
)

# key name in .env and in the openssl child process environment
ENCRYPTION_KEY_ENV_NAME = "SPARRING_ENCRYPTION_KEY"

# {root}/.sparring-keycheck.enc: committed encryption of a fixed marker, proves the key matches the repo
KEYCHECK_FILE_NAME = ".sparring-keycheck.enc"
KEYCHECK_MARKER = b"interview-sparring-keycheck-v1"

# openssl enc options shared by both directions (key read from the child env, never argv)
CIPHER_ARGUMENTS = [
    "-aes-256-cbc",
    "-salt",
    "-pbkdf2",
    "-iter",
    "200000",
    "-pass",
    f"env:{ENCRYPTION_KEY_ENV_NAME}",
]

# Git for Windows ships openssl here when it is not on PATH
WINDOWS_OPENSSL_CANDIDATES = [
    "C:/Program Files/Git/usr/bin/openssl.exe",
    "C:/Program Files/Git/mingw64/bin/openssl.exe",
]

EXIT_OPERATION_FAILED = 1
EXIT_PREREQUISITE_MISSING = 2
EXIT_CONFLICT = 3
EXIT_WRONG_KEY = 4


class SecretCryptError(RuntimeError):
    """openssl missing, wrong key or corrupted file"""


class OpenSslCommandError(SecretCryptError):
    """openssl ran and exited non-zero (typically a wrong key: bad decrypt)"""


class WrongKeyError(SecretCryptError):
    """The key does not match the one that created .sparring-keycheck.enc"""


class EncryptResult(NamedTuple):
    """changed: .enc files written / conflicts: local files whose .enc was left untouched (remote saved as <name>.remote)"""

    changed: list
    conflicts: list


class DecryptResult(NamedTuple):
    """restored: files written from .enc / ahead: local edits not encrypted yet / conflicts: both sides changed"""

    restored: list
    ahead: list
    conflicts: list


class SyncStatus(Enum):
    """local vs remote against the last synced base"""

    IN_SYNC = "in sync"  # local == remote
    REMOTE_AHEAD = "remote ahead"  # local == base, remote changed
    LOCAL_AHEAD = "local ahead"  # remote == base, local changed
    DIVERGED = "diverged"  # both changed differently, or never synced and different


# ---------- openssl and key ----------


def is_windows():
    return sys.platform.startswith("win")


def find_openssl():
    """openssl path: PATH first, then the Git for Windows copies; None if absent"""
    found = shutil.which("openssl")
    if found:
        return found
    if is_windows():
        for candidate in WINDOWS_OPENSSL_CANDIDATES:
            if Path(candidate).is_file():
                return candidate
    return None


def load_key(root):
    """Encryption key: {root}/.env first, then the environment variable; None if unset or empty"""
    env_file = Path(root) / ".env"
    if env_file.is_file():
        key_from_file = read_env_file_value(env_file, ENCRYPTION_KEY_ENV_NAME)
        if key_from_file:
            return key_from_file
    return os.environ.get(ENCRYPTION_KEY_ENV_NAME) or None


def read_env_file_value(env_file, name):
    """Value of NAME=... in a .env file (last one wins; 'export ' prefix and surrounding quotes allowed)"""
    value = None
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line_name, _, line_value = line.partition("=")
        line_name = line_name.strip().removeprefix("export ").strip()
        if line_name != name:
            continue
        line_value = line_value.strip()
        if len(line_value) >= 2 and line_value[0] == line_value[-1] and line_value[0] in "\"'":
            line_value = line_value[1:-1]
        value = line_value
    return value


def run_openssl(key, extra_arguments, input_bytes):
    """Run `openssl enc` on bytes via stdin/stdout (no file paths or key on the command line)"""
    openssl_path = find_openssl()
    if openssl_path is None:
        raise SecretCryptError("openssl not found (install it, or on Windows install Git for Windows)")
    child_environment = {**os.environ, ENCRYPTION_KEY_ENV_NAME: key}
    completed = subprocess.run(
        [openssl_path, "enc", *extra_arguments, *CIPHER_ARGUMENTS],
        input=input_bytes,
        capture_output=True,
        env=child_environment,
    )
    if completed.returncode != 0:
        # stderr never contains the key (it only lives in the child environment)
        reason = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise OpenSslCommandError(reason[0] if reason else f"openssl exited with {completed.returncode}")
    return completed.stdout


def encrypt_bytes(key, plaintext):
    return run_openssl(key, [], plaintext)


def decrypt_bytes(key, ciphertext):
    return run_openssl(key, ["-d"], ciphertext)


def sha256_of(content):
    return hashlib.sha256(content).hexdigest()


# ---------- key check ----------


def keycheck_path(root):
    return Path(root) / KEYCHECK_FILE_NAME


def verify_key(root, key):
    """Key matches this repo? Decrypt the keycheck file and compare the marker; nothing to verify if it is absent"""
    keycheck_file = keycheck_path(root)
    if not keycheck_file.is_file():
        return
    try:
        marker = decrypt_bytes(key, keycheck_file.read_bytes())
    except OpenSslCommandError as error:
        raise WrongKeyError("encryption key does not match this repo") from error
    # CBC can "decrypt" with a wrong key by chance, so the marker comparison is the real check
    if marker != KEYCHECK_MARKER:
        raise WrongKeyError("encryption key does not match this repo")


def create_keycheck_if_missing(root, key):
    """First encrypt of a repo: commit-ready marker file that later runs verify against"""
    keycheck_file = keycheck_path(root)
    if not keycheck_file.is_file():
        write_bytes_atomically(keycheck_file, encrypt_bytes(key, KEYCHECK_MARKER))


def write_bytes_atomically(path, content):
    """Write via an owner-only temp file in the same folder, then rename (a failure never leaves a half-written file)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=".", suffix=PARTIAL_FILE_SUFFIX
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(content)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


# ---------- sync state ----------


def load_sync_state(secret_dir):
    """{relative path: sha256} from secret/.sync-state.json; empty when missing or unreadable (conflicts then stay visible)"""
    state_file = sync_state_path(secret_dir)
    if not state_file.is_file():
        return {}
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return state if isinstance(state, dict) else {}


def save_sync_state(secret_dir, state):
    write_bytes_atomically(
        sync_state_path(secret_dir),
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
    )


def relative_state_key(secret_dir, secret_file):
    return Path(secret_file).relative_to(secret_dir).as_posix()


# ---------- encrypt / decrypt ----------


def compare_three_way(local_hash, remote_hash, base_hash):
    """Hashes of local, remote (decrypted .enc) and the last synced base (None = never synced) > SyncStatus"""
    if local_hash == remote_hash:
        return SyncStatus.IN_SYNC
    if local_hash == base_hash:
        return SyncStatus.REMOTE_AHEAD
    if remote_hash == base_hash:
        return SyncStatus.LOCAL_AHEAD
    return SyncStatus.DIVERGED


def read_remote_plaintext(key, encrypted_file):
    """Decrypted .enc bytes; None when there is no .enc yet"""
    if not encrypted_file.is_file():
        return None
    try:
        return decrypt_bytes(key, encrypted_file.read_bytes())
    except SecretCryptError as error:
        # never overwrite what the current key cannot read (wrong key or corrupted file)
        raise SecretCryptError(
            f"cannot decrypt existing {encrypted_file} with this key: {error} "
            "(wrong key or corrupted file; refusing to overwrite)"
        ) from error


def save_remote_copy(secret_file, remote_plaintext):
    """Conflict: keep the other side next to the local file as <name>.remote"""
    write_bytes_atomically(remote_copy_path_for(secret_file), remote_plaintext)


def save_previous_copy(secret_file, previous_plaintext):
    """Fast-forward: keep the replaced local content as <name>.previous (single slot, overwritten each time)"""
    write_bytes_atomically(previous_copy_path_for(secret_file), previous_plaintext)


def encrypt_all(root, key):
    """Encrypt local changes: verify key > three-way compare > encrypt > atomic write > record base > keycheck

    Per file: no .enc, or remote == base (only local changed) > write .enc; remote == local > nothing;
    otherwise (remote changed, alone or too) > conflict: .enc kept, remote saved as <name>.remote.
    Returns EncryptResult(changed, conflicts); the keycheck file is not listed.
    """
    verify_key(root, key)
    changed = []
    conflicts = []
    for secret_dir in find_secret_dirs(root):
        sync_state = load_sync_state(secret_dir)
        original_state = dict(sync_state)
        try:
            for secret_file in list_secret_files(secret_dir):
                encrypted_file = encrypted_file_for(secret_dir, secret_file)
                state_key = relative_state_key(secret_dir, secret_file)
                plaintext = secret_file.read_bytes()
                local_hash = sha256_of(plaintext)
                remote_plaintext = read_remote_plaintext(key, encrypted_file)
                if remote_plaintext is None:
                    status = SyncStatus.LOCAL_AHEAD
                else:
                    status = compare_three_way(
                        local_hash, sha256_of(remote_plaintext), sync_state.get(state_key)
                    )
                if status in (SyncStatus.REMOTE_AHEAD, SyncStatus.DIVERGED):
                    # .enc changed since the last sync > do not overwrite it
                    save_remote_copy(secret_file, remote_plaintext)
                    conflicts.append(secret_file)
                    continue
                if status is SyncStatus.LOCAL_AHEAD:
                    write_bytes_atomically(encrypted_file, encrypt_bytes(key, plaintext))
                    changed.append(encrypted_file)
                # written or already equal > this content is now the last synced one
                sync_state[state_key] = local_hash
        finally:
            if sync_state != original_state:
                save_sync_state(secret_dir, sync_state)
    # (after the loop: a failed run must not pin a wrong key as the repo key)
    create_keycheck_if_missing(root, key)
    return EncryptResult(changed, conflicts)


def decrypt_all(root, key):
    """Restore remote changes without ever overwriting a local edit: verify key > three-way compare > write

    Per file (remote = decrypted .enc, base = hash at the last encrypt/decrypt):
      local missing                                         > write remote
      local == base (only remote changed)                   > overwrite with remote, old content kept as <name>.previous
      local == remote                                       > nothing
      remote == base (only local changed)                   > keep local, report as ahead (run encrypt)
      both changed, or never synced and different           > conflict: local kept, remote saved as <name>.remote
    Returns DecryptResult(restored, ahead, conflicts).
    """
    verify_key(root, key)
    restored = []
    ahead = []
    conflicts = []
    for encrypted_dir in find_encrypted_dirs(root):
        secret_dir = secret_dir_for(encrypted_dir)
        sync_state = load_sync_state(secret_dir)
        original_state = dict(sync_state)
        try:
            for encrypted_file in list_encrypted_files(encrypted_dir):
                secret_file = secret_file_for(encrypted_dir, encrypted_file)
                state_key = relative_state_key(secret_dir, secret_file)
                remote_plaintext = decrypt_bytes(key, encrypted_file.read_bytes())
                remote_hash = sha256_of(remote_plaintext)
                if not secret_file.is_file():
                    write_bytes_atomically(secret_file, remote_plaintext)
                    restored.append(secret_file)
                    sync_state[state_key] = remote_hash
                    continue
                local_plaintext = secret_file.read_bytes()
                local_hash = sha256_of(local_plaintext)
                status = compare_three_way(local_hash, remote_hash, sync_state.get(state_key))
                if status is SyncStatus.REMOTE_AHEAD:
                    # (old content first: a failed write must not lose it)
                    save_previous_copy(secret_file, local_plaintext)
                    write_bytes_atomically(secret_file, remote_plaintext)
                    restored.append(secret_file)
                elif status is SyncStatus.LOCAL_AHEAD:
                    ahead.append(secret_file)
                elif status is SyncStatus.DIVERGED:
                    save_remote_copy(secret_file, remote_plaintext)
                    conflicts.append(secret_file)
                # in sync, restored: remote content is the new base (local ahead and conflicts keep the old one)
                if status in (SyncStatus.IN_SYNC, SyncStatus.REMOTE_AHEAD):
                    sync_state[state_key] = remote_hash
        finally:
            if sync_state != original_state:
                save_sync_state(secret_dir, sync_state)
    return DecryptResult(restored, ahead, conflicts)


# ---------- CLI ----------


def list_plaintext_without_encrypted(root):
    """Secret files that have no .enc copy yet (they would be lost if committed from another machine)"""
    missing = []
    for secret_dir in find_secret_dirs(root):
        for secret_file in list_secret_files(secret_dir):
            if not encrypted_file_for(secret_dir, secret_file).is_file():
                missing.append(secret_file)
    return missing


def to_relative_text(root, paths):
    return [Path(path).relative_to(root).as_posix() for path in paths]


def command_check(root):
    """Print the state as JSON: openssl, has_key, secret_dirs, plaintext_without_encrypted"""
    report = {
        "openssl": find_openssl(),
        "has_key": load_key(root) is not None,
        "secret_dirs": to_relative_text(root, find_secret_dirs(root)),
        "plaintext_without_encrypted": to_relative_text(root, list_plaintext_without_encrypted(root)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def print_written_files(root, command, written):
    if not written:
        print(f"[secret_crypt] {command}: nothing to do")
        return
    print(f"[secret_crypt] {command}: {len(written)} file(s)")
    for relative_path in to_relative_text(root, written):
        print(f"  {relative_path}")


def print_ahead(root, ahead):
    for relative_path in to_relative_text(root, ahead):
        print(f"[secret_crypt] local ahead: {relative_path} (run encrypt)")


def print_conflicts(root, conflicts):
    for relative_path in to_relative_text(root, conflicts):
        print(
            f"[secret_crypt] conflict: {relative_path} "
            f"(remote saved as {relative_path}{REMOTE_COPY_SUFFIX})",
            file=sys.stderr,
        )


def command_encrypt_or_decrypt(root, command):
    """encrypt / decrypt: prerequisites (openssl, key) > run > list written files, local-ahead files and conflicts"""
    if find_openssl() is None:
        print(
            "[secret_crypt] openssl not found. Install openssl (on Windows: Git for Windows).",
            file=sys.stderr,
        )
        return EXIT_PREREQUISITE_MISSING
    key = load_key(root)
    if key is None:
        print(
            f"[secret_crypt] no encryption key. Put {ENCRYPTION_KEY_ENV_NAME}=... in {root / '.env'} "
            "or set it in the environment.",
            file=sys.stderr,
        )
        return EXIT_PREREQUISITE_MISSING
    ahead = []
    try:
        if command == "encrypt":
            was_keycheck_present = keycheck_path(root).is_file()
            written, conflicts = encrypt_all(root, key)
            if not was_keycheck_present:
                print(f"[secret_crypt] created {KEYCHECK_FILE_NAME} (commit it)")
        else:
            written, ahead, conflicts = decrypt_all(root, key)
    except WrongKeyError as error:
        print(f"[secret_crypt] {error}", file=sys.stderr)
        return EXIT_WRONG_KEY
    except SecretCryptError as error:
        print(f"[secret_crypt] {command} failed: {error}", file=sys.stderr)
        return EXIT_OPERATION_FAILED
    print_written_files(root, command, written)
    print_ahead(root, ahead)
    print_conflicts(root, conflicts)
    return EXIT_CONFLICT if conflicts else 0


def main(argv=None):
    common.use_utf8_console()
    parser = argparse.ArgumentParser(description="Encrypt and decrypt secret/ folders with openssl")
    parser.add_argument("command", choices=["encrypt", "decrypt", "check"])
    arguments = parser.parse_args(argv)
    root = common.repo_root()
    if arguments.command == "check":
        return command_check(root)
    return command_encrypt_or_decrypt(root, arguments.command)


if __name__ == "__main__":
    sys.exit(main())
