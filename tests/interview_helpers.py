"""Helpers shared by the interview folder and status board tests"""

from datetime import date

import interview_folder

# the date the board tests pretend it is
TODAY = date(2026, 11, 16)

DEFAULT_OPEN_TASKS = [
    "Prepare 1-minute self-introduction",
    "Prepare closing remark",
    "Prepare questions to ask the interviewer",
]


def interviews_folder(root):
    return root / "prep" / "interviews"


def create_interview(root, date_ym="2026-11", org="Acme Corp", kind="job", interview_date=None):
    return interview_folder.new_interview(root, date_ym, org, kind, interview_date)


def write_tasks(interview, open_items=(), done_items=()):
    lines = ["# Tasks", "", "## Open", *[f"- [ ] {item}" for item in open_items], "", "## Done"]
    lines += [f"- [x] 2026-11-01 {item}" for item in done_items]
    (interview / "tasks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_writing_file(interview, relative_path, content="draft"):
    path = interview / "writing" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
