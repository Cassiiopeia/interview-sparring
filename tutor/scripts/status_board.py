"""Status board: read each interview's open tasks and D-day, write the board block into prep/status.md.

The board lives between BOARD_START_MARKER and BOARD_END_MARKER so the tutor's own notes around it survive a rebuild.
Interview order: upcoming (today included) soonest first, then past ones latest first, then no date; ties by folder name.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from interview_files import (
    META_FILE_NAME,
    InterviewFolderError,
    interviews_dir,
    parse_full_date,
    read_utf8_text,
    replace_text_file,
)

STATUS_FILE_NAME = "status.md"
TASKS_FILE_NAME = "tasks.md"

# tasks.md: `## Open` holds `- [ ] text` lines in priority order
OPEN_SECTION_TITLE = "Open"
# status board: open tasks shown across all interviews
TOP_TASK_COUNT = 3

# the board lives between these markers so the tutor's own Goal / Stage / Next session notes survive a rebuild
BOARD_START_MARKER = "<!-- sparring:board:start -->"
BOARD_END_MARKER = "<!-- sparring:board:end -->"
NEW_STATUS_FILE_HEADING = "# Status"

# `- [ ] text` or `* [ ] text`, any indentation (a nested item counts as a task too)
OPEN_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[ \]\s+(?P<text>\S.*?)\s*$")
# `# Title` or `## Title` (a `###` line is not a section end)
SECTION_HEADING_PATTERN = re.compile(r"^#{1,2}\s+(?P<title>.+?)\s*#*\s*$")

NO_DATE_LABEL = "no date"
UNREADABLE_META_NOTE = "meta.json unreadable"
INVALID_TASKS_TEXT_NOTE = "tasks.md has invalid characters"


@dataclass(frozen=True)
class InterviewSummary:
    name: str
    interview_date: date | None
    # False when meta.json is missing, damaged, or holds an interview_date that is not YYYY-MM-DD
    is_meta_readable: bool
    open_tasks: list
    # False when tasks.md is not valid UTF-8 (read with replacement characters, the board says so)
    is_tasks_text_valid: bool = True


def read_tasks_text(tasks_file):
    """(text, is_valid): a tasks.md that is not UTF-8 is read with replacement characters instead of failing; missing > ("", True)"""
    tasks_path = Path(tasks_file)
    if not tasks_path.is_file():
        return "", True
    raw_bytes = tasks_path.read_bytes()
    try:
        return raw_bytes.decode("utf-8-sig"), True
    except UnicodeDecodeError:
        return raw_bytes.decode("utf-8-sig", errors="replace"), False


def parse_open_tasks(tasks_text):
    """Texts of the `- [ ]` lines under `## Open`, in file order"""
    open_tasks = []
    is_in_open_section = False
    for line in tasks_text.splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            is_in_open_section = heading.group("title") == OPEN_SECTION_TITLE
            continue
        task = OPEN_TASK_PATTERN.match(line)
        if is_in_open_section and task:
            open_tasks.append(task.group("text"))
    return open_tasks


def read_open_tasks(tasks_file):
    """Open task texts of a tasks.md; [] when the file is missing (invalid characters are replaced, not fatal)"""
    tasks_text, _ = read_tasks_text(tasks_file)
    return parse_open_tasks(tasks_text)


def read_interview_date(folder):
    """(interview date or None, is_meta_readable): a date that is not a real YYYY-MM-DD makes meta unreadable"""
    try:
        meta = json.loads((folder / META_FILE_NAME).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        # (ValueError covers broken JSON and a file that is not UTF-8)
        return None, False
    if not isinstance(meta, dict):
        return None, False
    raw_interview_date = meta.get("interview_date")
    if raw_interview_date is None:
        return None, True
    try:
        return parse_full_date(raw_interview_date, "interview_date"), True
    except InterviewFolderError:
        return None, False


def list_interviews(root):
    """Every visible folder directly under prep/interviews/, as summaries sorted by folder name"""
    folder_root = interviews_dir(root)
    if not folder_root.is_dir():
        return []
    summaries = []
    for folder in sorted(folder_root.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        interview_date, is_meta_readable = read_interview_date(folder)
        tasks_text, is_tasks_text_valid = read_tasks_text(folder / TASKS_FILE_NAME)
        summaries.append(
            InterviewSummary(
                folder.name, interview_date, is_meta_readable, parse_open_tasks(tasks_text), is_tasks_text_valid
            )
        )
    return summaries


def order_by_urgency(summaries, today):
    """Upcoming (today included) soonest first, then past ones latest first, then no date; ties by folder name"""

    def sort_key(summary):
        if summary.interview_date is None:
            return 2, 0, summary.name
        days_left = (summary.interview_date - today).days
        if days_left >= 0:
            return 0, days_left, summary.name
        return 1, -days_left, summary.name

    return sorted(summaries, key=sort_key)


def format_d_day(interview_date, today):
    """None > 'no date'; 12 days ahead > 'D-12'; today > 'D-day'; 3 days ago > 'D+3'"""
    if interview_date is None:
        return NO_DATE_LABEL
    days_left = (interview_date - today).days
    if days_left == 0:
        return "D-day"
    return f"D-{days_left}" if days_left > 0 else f"D+{-days_left}"


def describe_interview(summary, today):
    """'- 2026-11-acme-mock: D-12 (2026-11-28)', '- name: no date', '- name: no date (meta.json unreadable)', '... (tasks.md has invalid characters)'"""
    label = format_d_day(summary.interview_date, today)
    if summary.interview_date is not None:
        line = f"- {summary.name}: {label} ({summary.interview_date.isoformat()})"
    else:
        meta_note = "" if summary.is_meta_readable else f" ({UNREADABLE_META_NOTE})"
        line = f"- {summary.name}: {label}{meta_note}"
    # (tasks shown on the board may be garbled: say so instead of failing the whole rebuild)
    return line if summary.is_tasks_text_valid else f"{line} ({INVALID_TASKS_TEXT_NOTE})"


def build_board_block(summaries, today):
    """The generated block, markers included: interviews with D-day, then the first TOP_TASK_COUNT open tasks"""
    ordered_summaries = order_by_urgency(summaries, today)
    lines = [BOARD_START_MARKER, "## Interviews", ""]
    if ordered_summaries:
        lines += [describe_interview(summary, today) for summary in ordered_summaries]
    else:
        lines.append("No interviews yet.")
    lines += ["", "## Top tasks", ""]
    top_tasks = [(summary.name, task) for summary in ordered_summaries for task in summary.open_tasks][:TOP_TASK_COUNT]
    if top_tasks:
        lines += [f"{number}. [{name}] {task}" for number, (name, task) in enumerate(top_tasks, start=1)]
    else:
        lines.append("No open tasks.")
    lines += [
        "",
        f"Rebuilt {today.isoformat()} from prep/interviews (text between the markers is replaced on every rebuild).",
        BOARD_END_MARKER,
    ]
    return "\n".join(lines)


def locate_board_block(status_text):
    """(start, end) of the existing block; None when there is none; damaged markers raise (nothing is guessed)"""
    start_count = status_text.count(BOARD_START_MARKER)
    end_count = status_text.count(BOARD_END_MARKER)
    if start_count == 0 and end_count == 0:
        return None
    if start_count == 1 and end_count == 1:
        start = status_text.index(BOARD_START_MARKER)
        end = status_text.index(BOARD_END_MARKER)
        if start < end:
            return start, end
        raise InterviewFolderError("status.md board markers are damaged: the end marker comes before the start marker")
    raise InterviewFolderError(
        f"status.md board markers are damaged: found {start_count} start and {end_count} end marker(s), "
        "expected none, or one start before one end"
    )


def merge_board_into_status(existing_text, board_block):
    """Replace the old board block; a file without one gets the block appended; nothing else is touched"""
    block_location = locate_board_block(existing_text)
    if not existing_text.strip():
        return f"{NEW_STATUS_FILE_HEADING}\n\n{board_block}\n"
    if block_location is None:
        return existing_text.rstrip("\n") + "\n\n" + board_block + "\n"
    start, end = block_location
    return existing_text[:start] + board_block + existing_text[end + len(BOARD_END_MARKER):]


def rebuild_status(root, today=None):
    """Write prep/status.md (board between the markers, other text kept) and return the whole file text"""
    today = today or date.today()
    status_file = Path(root) / "prep" / STATUS_FILE_NAME
    existing_text = read_utf8_text(status_file) if status_file.is_file() else ""
    # (everything is read and validated before the file is touched)
    status_text = merge_board_into_status(existing_text, build_board_block(list_interviews(root), today))
    status_file.parent.mkdir(parents=True, exist_ok=True)
    replace_text_file(status_file, status_text)
    return status_text
