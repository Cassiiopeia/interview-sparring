"""Shared by interview_folder.py and status_board.py: the error type, prep/interviews paths, dates, UTF-8 file helpers"""

import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

INTERVIEWS_FOLDER_NAME = "interviews"
META_FILE_NAME = "meta.json"

# YYYY-MM-DD, ASCII digits only (fullmatch, so a trailing newline is refused; the day itself is checked by date.fromisoformat)
FULL_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# a half-written temp file left by a crash matches the repo's `.*.partial` ignore rule
TEMP_FILE_SUFFIX = ".partial"


class InterviewFolderError(Exception):
    """A request refused before anything was changed"""


def interviews_dir(root):
    return Path(root) / "prep" / INTERVIEWS_FOLDER_NAME


def parse_full_date(text, label):
    """'YYYY-MM-DD' > date; InterviewFolderError for anything else (including a day that does not exist)"""
    if not isinstance(text, str) or not FULL_DATE_PATTERN.fullmatch(text):
        raise InterviewFolderError(f"{label} must be YYYY-MM-DD, got {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise InterviewFolderError(f"{label} must be a real date in YYYY-MM-DD form, got {text!r}") from error


def read_utf8_text(path):
    """File text (a UTF-8 BOM is dropped); a file in another encoding raises InterviewFolderError naming it"""
    file_path = Path(path)
    try:
        return file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise InterviewFolderError(
            f"{file_path.parent.name}/{file_path.name} is not valid UTF-8 text: save it as UTF-8 and run again"
        ) from error


def write_text_file(path, text):
    """UTF-8 with LF line ends on every OS"""
    with Path(path).open("w", encoding="utf-8", newline="\n") as text_stream:
        text_stream.write(text)


def replace_text_file(path, text):
    """Write a temp file next to the target, then swap it in: a crash or full disk leaves the old file whole"""
    target = Path(path)
    descriptor, temp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=TEMP_FILE_SUFFIX)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as text_stream:
            text_stream.write(text)
        if target.exists():
            # (mkstemp makes the file owner-only; keep the mode the target already had)
            shutil.copymode(target, temp_path)
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
