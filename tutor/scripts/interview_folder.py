#!/usr/bin/env python3
"""Interview folders under prep/interviews/: create from the template, copy submitted files, rebuild the status board.

    python3 tutor/scripts/interview_folder.py new --date YYYY-MM --org NAME --kind KIND [--interview-date YYYY-MM-DD]
    python3 tutor/scripts/interview_folder.py submit FOLDER FILE...
    python3 tutor/scripts/interview_folder.py status

new     prep/interviews/YYYY-MM-org-kind from tutor/templates/interview (+ empty local/ and secret/, + meta.json).
        Folder name: org and kind keep ASCII letters and digits only, lowercase, spaces and underscores become one hyphen.
        A name with nothing ASCII left (a Korean-only name) is refused: give a short romanized or English name.
submit  copies files from FOLDER/writing/ to FOLDER/submitted/ (same relative path). Anything outside writing/ is refused,
        and so is overwriting a submitted file; one refused file copies nothing. FOLDER is a name under prep/interviews/
        or a path to such a folder. A relative FILE is read from the current directory, else from FOLDER.
status  rebuild prep/status.md (interviews with D-day, then the first 3 open tasks) and print it (code: status_board.py).
        Only the part between the board markers is replaced; any text around it stays; damaged markers stop the rebuild.
Exit codes: 0 ok, 1 invalid input or refused request.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import common
from interview_files import (
    META_FILE_NAME,
    InterviewFolderError,
    interviews_dir,
    parse_full_date,
    write_text_file,
)

# re-exported: the status board code lives in status_board.py, callers and tests keep using these names from here
from status_board import (  # noqa: F401
    BOARD_END_MARKER,
    BOARD_START_MARKER,
    format_d_day,
    read_open_tasks,
    rebuild_status,
)

# interview folder template (next to the scripts, not under the root: the root can be a temp dir)
TEMPLATE_INTERVIEW_DIR = Path(__file__).resolve().parent.parent / "templates" / "interview"

WRITING_FOLDER_NAME = "writing"
SUBMITTED_FOLDER_NAME = "submitted"
# gitignored (**/local/, **/secret/), so they cannot ship in the template: created empty with every interview
EMPTY_FOLDER_NAMES = ("local", "secret")

# YYYY-MM (ASCII digits only; fullmatch, so a trailing newline is refused)
YEAR_MONTH_PATTERN = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
# org and kind each, after normalizing (the folder name must stay a short path component)
MAX_NAME_PART_LENGTH = 40

EXIT_OK = 0
EXIT_INVALID_INPUT = 1


def say(message):
    print(f"[interview] {message}")


# ---------- new ----------


def normalize_name_part(text):
    """'Acme Corp_2' > 'acme-corp-2' (ASCII letters and digits, one hyphen between words, nothing else)"""
    ascii_text = "".join(character for character in text if character.isascii()).lower()
    hyphenated = re.sub(r"[\s_]+", "-", ascii_text)
    kept = re.sub(r"[^a-z0-9-]", "", hyphenated)
    return re.sub(r"-{2,}", "-", kept).strip("-")


def normalize_required_name_part(label, text):
    normalized = normalize_name_part(text)
    if not normalized:
        raise InterviewFolderError(
            f"{label} {text!r} has no ASCII letters or digits to build a folder name from: "
            "give a short romanized or English name (for example 'acme-corp')"
        )
    if len(normalized) > MAX_NAME_PART_LENGTH:
        raise InterviewFolderError(
            f"{label} {text!r} becomes {normalized!r} ({len(normalized)} characters): "
            f"the folder name allows at most {MAX_NAME_PART_LENGTH} characters per part, give a shorter name"
        )
    return normalized


def validate_year_month(date_ym):
    if not isinstance(date_ym, str) or not YEAR_MONTH_PATTERN.fullmatch(date_ym):
        raise InterviewFolderError(f"date must be YYYY-MM (month 01-12), got {date_ym!r}")
    return date_ym


def new_interview(root, date_ym, org, kind, interview_date=None):
    """Create prep/interviews/{date_ym}-{org}-{kind}/ from the template; refuses an existing name; returns the folder"""
    # validate everything first (nothing is created for a refused request)
    validated_date_ym = validate_year_month(date_ym)
    org_part = normalize_required_name_part("org", org)
    kind_part = normalize_required_name_part("kind", kind)
    if interview_date is not None:
        parse_full_date(interview_date, "interview date")
    if not TEMPLATE_INTERVIEW_DIR.is_dir():
        raise InterviewFolderError(f"template folder not found: {TEMPLATE_INTERVIEW_DIR}")

    folder = interviews_dir(root) / f"{validated_date_ym}-{org_part}-{kind_part}"
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()
    except FileExistsError as error:
        raise InterviewFolderError(f"interview folder already exists: {folder.name}") from error
    try:
        # template > folder (copytree keeps .gitkeep), empty local/ and secret/, meta.json
        shutil.copytree(TEMPLATE_INTERVIEW_DIR, folder, dirs_exist_ok=True)
        for empty_folder_name in EMPTY_FOLDER_NAMES:
            (folder / empty_folder_name).mkdir(exist_ok=True)
        meta = {"org": org.strip(), "kind": kind.strip(), "date": validated_date_ym, "interview_date": interview_date}
        write_text_file(folder / META_FILE_NAME, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        # (a half-built folder would block the same name next time)
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


# ---------- submit ----------


def require_interview_folder(root, interview):
    """The interview folder as a Path; it must exist and sit directly under prep/interviews/"""
    folder = Path(interview)
    if not folder.is_dir():
        raise InterviewFolderError(f"interview folder not found: {interview}")
    if folder.resolve().parent != interviews_dir(root).resolve():
        raise InterviewFolderError(f"{folder} is not a folder under prep/interviews/")
    return folder


def locate_source_file(interview_folder, file_path):
    """Existing file for a path as given: absolute as is; relative from the current directory, else from the interview folder"""
    candidates = [file_path] if file_path.is_absolute() else [Path.cwd() / file_path, interview_folder / file_path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise InterviewFolderError(f"file not found: {file_path}")


def relative_path_inside(path, folder):
    """Path relative to folder (both resolved); None when path is not inside folder"""
    try:
        return path.relative_to(folder)
    except ValueError:
        return None


def plan_submission(interview_folder, files):
    """[(source, destination)] for every file; any refusal raises before a single file is copied"""
    writing_folder = (interview_folder / WRITING_FOLDER_NAME).resolve()
    submitted_folder = interview_folder / SUBMITTED_FOLDER_NAME
    resolved_submitted_folder = submitted_folder.resolve()
    plan = []
    planned_relative_paths = set()
    for file_path in files:
        source = locate_source_file(interview_folder, Path(file_path))
        # (resolved: a ".." path or a symlink cannot smuggle a file in from outside writing/)
        relative_path = relative_path_inside(source.resolve(), writing_folder)
        if relative_path is None:
            raise InterviewFolderError(f"{file_path} is not inside writing/: only files from writing/ can be submitted")
        if not source.resolve().is_file():
            raise InterviewFolderError(f"{file_path} is not a file")
        if relative_path in planned_relative_paths:
            continue
        planned_relative_paths.add(relative_path)
        destination = submitted_folder / relative_path
        if relative_path_inside(destination.parent.resolve(), resolved_submitted_folder) is None:
            raise InterviewFolderError(f"{relative_path.as_posix()} would land outside submitted/")
        if os.path.lexists(destination):
            raise InterviewFolderError(f"already submitted: {relative_path.as_posix()} (never overwritten)")
        plan.append((source, destination))
    return plan


def submit(root, interview, files):
    """Copy files from writing/ to submitted/ keeping the relative path; refuses an overwrite; returns the copies"""
    interview_folder = require_interview_folder(root, interview)
    plan = plan_submission(interview_folder, files)
    copied_paths = []
    for source, destination in plan:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # (exclusive create: a file that appeared after the check still is not overwritten)
            with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
                shutil.copyfileobj(source_stream, destination_stream)
        except FileExistsError as error:
            raise InterviewFolderError(f"already submitted: {destination.name} (never overwritten)") from error
        shutil.copystat(source, destination)
        copied_paths.append(destination)
    return copied_paths


# ---------- CLI ----------


def display_path(root, path):
    """Path as shown to the user: relative to the repo root with '/', else the path itself"""
    resolved_path = Path(path).resolve()
    try:
        return resolved_path.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def resolve_interview_argument(root, text):
    """A folder name under prep/interviews/, else a path to a folder (current directory based); always absolute"""
    is_plain_name = Path(text).name == text and text not in (".", "..")
    named_folder = interviews_dir(root) / text
    if is_plain_name and named_folder.is_dir():
        return named_folder.resolve()
    return Path(text).resolve()


def command_new(root, arguments):
    folder = new_interview(root, arguments.date, arguments.org, arguments.kind, arguments.interview_date)
    say(f"created {display_path(root, folder)}")
    try:
        rebuild_status(root)
    except (InterviewFolderError, OSError) as error:
        # (the folder is kept: it is complete, only the board is stale)
        print(f"[interview] {folder.name} was created, but status could not be rebuilt: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    say("prep/status.md rebuilt")
    return EXIT_OK


def command_submit(root, arguments):
    interview = resolve_interview_argument(root, arguments.folder)
    copied_paths = submit(root, interview, [Path(file_name) for file_name in arguments.files])
    for copied_path in copied_paths:
        say(f"submitted {display_path(root, copied_path)}")
    return EXIT_OK


def command_status(root):
    print(rebuild_status(root), end="")
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(description="Interview folders, submitted files and the status board")
    commands = parser.add_subparsers(dest="command", required=True)
    new_command = commands.add_parser("new", help="create prep/interviews/YYYY-MM-org-kind from the template")
    new_command.add_argument("--date", required=True, help="YYYY-MM")
    new_command.add_argument("--org", required=True, help="organization, short English or romanized name")
    new_command.add_argument("--kind", required=True, help="kind of interview, short English name (job, oral-exam, ...)")
    new_command.add_argument("--interview-date", help="YYYY-MM-DD, when the interview is (for the D-day)")
    submit_command = commands.add_parser("submit", help="copy files from writing/ to submitted/")
    submit_command.add_argument("folder", help="interview folder name (under prep/interviews/) or path")
    submit_command.add_argument("files", nargs="+", help="files inside the interview's writing/ folder")
    commands.add_parser("status", help="rebuild prep/status.md and print it")
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    root = common.repo_root()
    try:
        if arguments.command == "new":
            return command_new(root, arguments)
        if arguments.command == "submit":
            return command_submit(root, arguments)
        return command_status(root)
    except (InterviewFolderError, OSError) as error:
        # (OSError: disk full, no permission, locked file: one line instead of a traceback)
        print(f"[interview] {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
