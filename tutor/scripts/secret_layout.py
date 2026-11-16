"""Where secret files live: secret/ <-> secret-encrypted/ discovery and path mapping (no encryption here)"""

import os
from pathlib import Path

SECRET_DIR_NAME = "secret"
# sibling of secret/: committed mirror of its files
ENCRYPTED_DIR_NAME = "secret-encrypted"
ENCRYPTED_SUFFIX = ".enc"

# never scanned: git internals and tool output
TOOL_DIR_NAMES = {".git", ".superpowers"}
# OS junk inside secret/ is not encrypted
IGNORED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
# decrypt conflict copies, fast-forward backups and half-written temp files inside secret/ are not encrypted
REMOTE_COPY_SUFFIX = ".remote"
PREVIOUS_COPY_SUFFIX = ".previous"
PARTIAL_FILE_SUFFIX = ".partial"
IGNORED_FILE_SUFFIXES = (REMOTE_COPY_SUFFIX, PREVIOUS_COPY_SUFFIX, PARTIAL_FILE_SUFFIX)

# secret/.sync-state.json: {relative posix path: sha256 of the plaintext at the last encrypt/decrypt}
SYNC_STATE_FILE_NAME = ".sync-state.json"


def find_dirs_named(root, target_name, skipped_dir_names):
    """Every folder called target_name under root, sorted (prunes skipped_dir_names, never descends into a match)"""
    found = []
    for current, dir_names, _ in os.walk(root):
        dir_names[:] = sorted(name for name in dir_names if name not in skipped_dir_names)
        found.extend(Path(current) / name for name in dir_names if name == target_name)
        dir_names[:] = [name for name in dir_names if name != target_name]
    return found


def find_secret_dirs(root):
    """Every secret/ folder under root (encrypted mirrors are skipped too)"""
    return find_dirs_named(Path(root), SECRET_DIR_NAME, TOOL_DIR_NAMES | {ENCRYPTED_DIR_NAME})


def find_encrypted_dirs(root):
    """Every secret-encrypted/ folder under root"""
    return find_dirs_named(Path(root), ENCRYPTED_DIR_NAME, TOOL_DIR_NAMES)


def encrypted_dir_for(secret_dir):
    """secret/ > sibling secret-encrypted/"""
    return Path(secret_dir).parent / ENCRYPTED_DIR_NAME


def secret_dir_for(encrypted_dir):
    """secret-encrypted/ > sibling secret/"""
    return Path(encrypted_dir).parent / SECRET_DIR_NAME


def is_encryptable_file(secret_dir, path):
    """False for OS junk, conflict copies, temp files, the sync-state file and symlinks"""
    is_sync_state_file = path.parent == secret_dir and path.name == SYNC_STATE_FILE_NAME
    return not (
        path.name in IGNORED_FILE_NAMES
        or path.name.endswith(IGNORED_FILE_SUFFIXES)
        or is_sync_state_file
        or path.is_symlink()
    )


def list_secret_files(secret_dir):
    """Files to encrypt: everything under secret/ that is_encryptable_file accepts"""
    files = []
    for current, dir_names, file_names in os.walk(secret_dir):
        dir_names.sort()
        candidates = (Path(current) / file_name for file_name in sorted(file_names))
        files.extend(path for path in candidates if is_encryptable_file(Path(secret_dir), path))
    return files


def list_encrypted_files(encrypted_dir):
    """Encrypted copies to restore: every *.enc under secret-encrypted/"""
    files = []
    for current, dir_names, file_names in os.walk(encrypted_dir):
        dir_names.sort()
        files.extend(
            Path(current) / name for name in sorted(file_names) if name.endswith(ENCRYPTED_SUFFIX)
        )
    return files


def encrypted_file_for(secret_dir, secret_file):
    """secret/a/b.md > secret-encrypted/a/b.md.enc"""
    relative = Path(secret_file).relative_to(secret_dir)
    return encrypted_dir_for(secret_dir) / relative.parent / (relative.name + ENCRYPTED_SUFFIX)


def secret_file_for(encrypted_dir, encrypted_file):
    """secret-encrypted/a/b.md.enc > secret/a/b.md"""
    relative = Path(encrypted_file).relative_to(encrypted_dir)
    return secret_dir_for(encrypted_dir) / relative.parent / relative.name.removesuffix(ENCRYPTED_SUFFIX)


def remote_copy_path_for(secret_file):
    """secret/a/b.md > secret/a/b.md.remote"""
    return secret_file.with_name(secret_file.name + REMOTE_COPY_SUFFIX)


def previous_copy_path_for(secret_file):
    """secret/a/b.md > secret/a/b.md.previous (single slot: the content a fast-forward decrypt replaced)"""
    return secret_file.with_name(secret_file.name + PREVIOUS_COPY_SUFFIX)


def sync_state_path(secret_dir):
    return Path(secret_dir) / SYNC_STATE_FILE_NAME
