"""Shared script helpers: repo root, prep dir, UTF-8 console"""

import os
import sys
from pathlib import Path, PurePosixPath

# overrides the repo root (test isolation)
ROOT_ENV_NAME = "SPARRING_ROOT"


def repo_root():
    """Repo root: env override first, else two levels above tutor/scripts"""
    override = os.environ.get(ROOT_ENV_NAME)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent


def prep_dir():
    """Personal records dir: {root}/prep (any local/ or secret/ folder is gitignored, not prep itself)"""
    return repo_root() / "prep"


def use_utf8_console():
    """Switch output to UTF-8 so Windows consoles (cp949) do not garble text"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def has_symlink_component(base, relative_path, include_last=True):
    """A part of base/relative_path (below base) is a symlink (include_last=False: the file itself may be one)"""
    parts = PurePosixPath(relative_path).parts
    if not include_last:
        parts = parts[:-1]
    current = Path(base)
    for part in parts:
        current = current / part
        if current.is_symlink():
            return True
    return False
