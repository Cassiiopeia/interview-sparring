"""Tests for status_board.py (and its re-exports from interview_folder): temp dirs as repo roots, today's date injected"""

import json
import os
import stat
import sys
from datetime import date

import pytest

import interview_folder
import status_board
from interview_helpers import TODAY, create_interview, interviews_folder, write_tasks


# ---------- tasks.md ----------


def test_read_open_tasks_takes_open_items_in_order_and_ignores_done_and_other_sections(tmp_root):
    tasks_file = tmp_root / "tasks.md"
    tasks_file.write_text(
        "# Tasks\n\nFormat: open `- [ ] text`.\n\n## Open\n"
        "- [ ] first\n- [x] 2026-11-01 already done but listed here\n* [ ] second\n  - [ ] nested third\n- [ ]\n"
        "### Sub heading stays in the section\n- [ ] fourth\n\n## Done\n- [ ] not open: it sits under Done\n",
        encoding="utf-8",
    )

    assert status_board.read_open_tasks(tasks_file) == ["first", "second", "nested third", "fourth"]


def test_read_open_tasks_is_empty_for_a_missing_file(tmp_root):
    assert status_board.read_open_tasks(tmp_root / "nope.md") == []


# ---------- rebuild_status ----------


@pytest.mark.parametrize(
    "interview_date, expected_label",
    [
        (None, "no date"),
        (date(2026, 11, 28), "D-12"),
        (date(2026, 11, 16), "D-day"),
        (date(2026, 11, 13), "D+3"),
    ],
)
def test_format_d_day(interview_date, expected_label):
    assert status_board.format_d_day(interview_date, TODAY) == expected_label


def test_rebuild_status_lists_every_interview_with_its_d_day(tmp_root):
    create_interview(tmp_root, org="Alpha", kind="mock", interview_date="2026-11-28")
    create_interview(tmp_root, org="Beta", kind="mock")

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert "2026-11-alpha-mock: D-12 (2026-11-28)" in status
    assert "2026-11-beta-mock: no date" in status


def test_rebuild_status_takes_top_three_across_interviews(tmp_root):
    later = create_interview(tmp_root, org="Later", kind="exam", interview_date="2026-12-20")
    sooner = create_interview(tmp_root, org="Sooner", kind="exam", interview_date="2026-11-20")
    undated = create_interview(tmp_root, org="Undated", kind="exam")
    write_tasks(later, ["later one", "later two"])
    write_tasks(sooner, ["sooner one", "sooner two"], done_items=["sooner finished"])
    write_tasks(undated, ["undated one"])

    status = status_board.rebuild_status(tmp_root, TODAY)

    top_task_lines = [line for line in status.split("## Top tasks")[1].splitlines() if line[:1].isdigit()]
    assert top_task_lines == [
        "1. [2026-11-sooner-exam] sooner one",
        "2. [2026-11-sooner-exam] sooner two",
        "3. [2026-11-later-exam] later one",
    ]
    assert "sooner finished" not in status


def test_rebuild_status_puts_no_date_interviews_last(tmp_root):
    undated = create_interview(tmp_root, org="Aaa", kind="exam")
    dated = create_interview(tmp_root, org="Zzz", kind="exam", interview_date="2027-01-10")
    write_tasks(undated, ["undated one"])
    write_tasks(dated, ["dated one"])

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert status.index("dated one") < status.index("undated one")
    assert status.index("2026-11-zzz-exam: D-55") < status.index("2026-11-aaa-exam: no date")


def test_rebuild_status_puts_a_past_interview_after_the_upcoming_ones(tmp_root):
    past = create_interview(tmp_root, org="Past", kind="exam", interview_date="2026-11-10")
    upcoming = create_interview(tmp_root, org="Upcoming", kind="exam", interview_date="2027-02-01")
    write_tasks(past, ["send thank-you note"])
    write_tasks(upcoming, ["prepare slides"])

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert status.index("prepare slides") < status.index("send thank-you note")
    assert "2026-11-past-exam: D+6 (2026-11-10)" in status


def test_rebuild_status_orders_equal_dates_by_folder_name(tmp_root):
    second = create_interview(tmp_root, org="Bbb", kind="exam", interview_date="2026-12-01")
    first = create_interview(tmp_root, org="Aaa", kind="exam", interview_date="2026-12-01")
    write_tasks(first, ["from aaa"])
    write_tasks(second, ["from bbb"])

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert status.index("from aaa") < status.index("from bbb")


def test_rebuild_status_writes_prep_status_md_with_the_returned_text(tmp_root):
    create_interview(tmp_root, interview_date="2026-12-01")

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert (tmp_root / "prep" / "status.md").read_text(encoding="utf-8") == status
    assert "Prepare 1-minute self-introduction" in status


def test_rebuild_status_with_no_interviews(tmp_root):
    status = status_board.rebuild_status(tmp_root, TODAY)

    assert "No interviews yet" in status
    assert "No open tasks" in status
    assert (tmp_root / "prep" / "status.md").is_file()


def test_rebuild_status_is_stable_when_run_twice(tmp_root):
    create_interview(tmp_root, interview_date="2026-12-01")

    first = status_board.rebuild_status(tmp_root, TODAY)
    second = status_board.rebuild_status(tmp_root, TODAY)

    assert first == second


def test_rebuild_status_keeps_the_text_around_the_generated_block(tmp_root):
    status_file = tmp_root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True)
    status_file.write_text(
        "# Status\n\n## Goal\nMy own goal text.\n\n"
        f"{status_board.BOARD_START_MARKER}\nstale board\n{status_board.BOARD_END_MARKER}\n\n"
        "## Next session\nStart from question 3.\n",
        encoding="utf-8",
    )
    create_interview(tmp_root, interview_date="2026-12-01")

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert "My own goal text." in status and "Start from question 3." in status
    assert "stale board" not in status
    assert status.count(status_board.BOARD_START_MARKER) == 1


def test_rebuild_status_appends_the_block_to_a_status_file_without_markers(tmp_root):
    status_file = tmp_root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True)
    status_file.write_text("# Status\n\nHand written notes.\n", encoding="utf-8")

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert status.startswith("# Status\n\nHand written notes.\n")
    assert status_board.BOARD_START_MARKER in status


def test_rebuild_status_marks_a_damaged_meta_file_instead_of_failing(tmp_root):
    broken = create_interview(tmp_root, org="Broken", kind="exam")
    (broken / "meta.json").write_text("{not json", encoding="utf-8")
    bad_date = create_interview(tmp_root, org="Baddate", kind="exam")
    (bad_date / "meta.json").write_text(json.dumps({"interview_date": "soon"}), encoding="utf-8")

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert "2026-11-broken-exam: no date (meta.json unreadable)" in status
    assert "2026-11-baddate-exam: no date (meta.json unreadable)" in status


def test_rebuild_status_ignores_loose_files_and_hidden_folders(tmp_root):
    create_interview(tmp_root, org="Real", kind="exam")
    (interviews_folder(tmp_root) / "notes.txt").write_text("x", encoding="utf-8")
    (interviews_folder(tmp_root) / ".hidden").mkdir()

    status = status_board.rebuild_status(tmp_root, TODAY)

    assert "notes.txt" not in status and ".hidden" not in status
    assert "2026-11-real-exam" in status


# ---------- board markers ----------

START = status_board.BOARD_START_MARKER
END = status_board.BOARD_END_MARKER


def write_status(root, text):
    status_file = root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(text, encoding="utf-8")
    return status_file


@pytest.mark.parametrize(
    "damaged_text, problem",
    [
        (f"# Status\n{START}\nold board\n", "1 start and 0 end"),
        (f"# Status\nold board\n{END}\n", "0 start and 1 end"),
        (f"# Status\n{END}\nold\n{START}\n", "end marker comes before the start marker"),
        (f"{START}\na\n{END}\n\n{START}\nb\n{END}\n", "2 start and 2 end"),
        (f"{START}\n{START}\n{END}\n", "2 start and 1 end"),
    ],
)
def test_rebuild_status_refuses_damaged_markers_and_leaves_the_file_as_it_was(tmp_root, damaged_text, problem):
    status_file = write_status(tmp_root, damaged_text)
    create_interview(tmp_root, interview_date="2026-12-01")

    with pytest.raises(interview_folder.InterviewFolderError, match="status.md board markers are damaged") as refusal:
        status_board.rebuild_status(tmp_root, TODAY)

    assert problem in str(refusal.value)
    assert status_file.read_text(encoding="utf-8") == damaged_text


def test_rebuild_status_accepts_a_file_with_no_markers_or_exactly_one_pair(tmp_root):
    write_status(tmp_root, "# Status\n\nnotes only\n")
    assert status_board.rebuild_status(tmp_root, TODAY).count(START) == 1

    # (the pair written by the first run is a valid pair for the second)
    assert status_board.rebuild_status(tmp_root, TODAY).count(START) == 1


def test_interview_folder_reexports_the_status_board_names(tmp_root):
    assert interview_folder.rebuild_status is status_board.rebuild_status
    assert interview_folder.read_open_tasks is status_board.read_open_tasks
    assert interview_folder.format_d_day is status_board.format_d_day
    assert interview_folder.BOARD_START_MARKER == START and interview_folder.BOARD_END_MARKER == END


# ---------- reading and writing the files ----------


def test_rebuild_status_names_a_status_file_that_is_not_utf8_and_leaves_it(tmp_root):
    status_file = tmp_root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True)
    status_file.write_bytes("# Status\n\ucafe".encode("cp949", errors="replace") + b"\xb0\xa1\xff")

    original_bytes = status_file.read_bytes()
    with pytest.raises(interview_folder.InterviewFolderError, match=r"prep/status\.md is not valid UTF-8"):
        status_board.rebuild_status(tmp_root, TODAY)

    assert status_file.read_bytes() == original_bytes


def test_rebuild_status_names_a_tasks_file_that_is_not_utf8(tmp_root):
    interview = create_interview(tmp_root)
    (interview / "tasks.md").write_bytes(b"## Open\n- [ ] caf\xe9 \xff\n")

    with pytest.raises(interview_folder.InterviewFolderError, match=rf"{interview.name}/tasks\.md is not valid UTF-8"):
        status_board.rebuild_status(tmp_root, TODAY)


def test_rebuild_status_treats_a_meta_file_that_is_not_utf8_as_unreadable(tmp_root):
    interview = create_interview(tmp_root, org="Broken", kind="exam")
    (interview / "meta.json").write_bytes(b'{"interview_date": "\xff"}')

    assert "2026-11-broken-exam: no date (meta.json unreadable)" in status_board.rebuild_status(tmp_root, TODAY)


def test_rebuild_status_leaves_no_temp_file_behind(tmp_root):
    create_interview(tmp_root)

    status_board.rebuild_status(tmp_root, TODAY)

    assert sorted(path.name for path in (tmp_root / "prep").iterdir() if path.is_file()) == ["status.md"]


def test_rebuild_status_keeps_the_old_file_whole_when_the_swap_fails(tmp_root, monkeypatch):
    status_file = write_status(tmp_root, "# Status\n\nprecious notes\n")
    create_interview(tmp_root)

    def fail(*arguments, **keyword_arguments):
        raise PermissionError("cannot replace")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(PermissionError):
        status_board.rebuild_status(tmp_root, TODAY)
    monkeypatch.undo()

    assert status_file.read_text(encoding="utf-8") == "# Status\n\nprecious notes\n"
    assert sorted(path.name for path in (tmp_root / "prep").iterdir() if path.is_file()) == ["status.md"]


@pytest.mark.skipif(sys.platform == "win32", reason="permission bits are not meaningful on Windows")
def test_rebuild_status_keeps_the_file_mode(tmp_root):
    status_file = write_status(tmp_root, "# Status\n")
    status_file.chmod(0o640)

    status_board.rebuild_status(tmp_root, TODAY)

    assert stat.S_IMODE(status_file.stat().st_mode) == 0o640
