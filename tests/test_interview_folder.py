"""Tests for interview_folder.py: temp dirs as repo roots (see conftest.py)"""

import json
import os
from pathlib import Path

import pytest

import interview_folder
from interview_helpers import (
    DEFAULT_OPEN_TASKS,
    create_interview,
    interviews_folder,
    write_writing_file,
)


# ---------- new_interview ----------


def test_new_interview_normalizes_name(tmp_root):
    interview = create_interview(tmp_root, "2026-11", "Acme Corp", "job")

    assert interview == interviews_folder(tmp_root) / "2026-11-acme-corp-job"
    assert interview.is_dir()


@pytest.mark.parametrize(
    "org, kind, expected_name",
    [
        ("Acme_Corp", "Grad School", "2026-11-acme-corp-grad-school"),
        ("  Acme   Corp  ", "mock", "2026-11-acme-corp-mock"),
        ("Acme & Sons, Inc.", "final", "2026-11-acme-sons-inc-final"),
        ("--Acme--", "__mock__", "2026-11-acme-mock"),
        ("Acme 회사", "job", "2026-11-acme-job"),
        ("../../etc", "passwd", "2026-11-etc-passwd"),
    ],
)
def test_new_interview_name_keeps_only_lowercase_ascii_and_single_hyphens(tmp_root, org, kind, expected_name):
    interview = create_interview(tmp_root, org=org, kind=kind)

    assert interview.name == expected_name
    assert interview.parent == interviews_folder(tmp_root)


def test_new_interview_creates_the_template_structure(tmp_root):
    interview = create_interview(tmp_root)

    for folder_name in ("about", "writing", "submitted", "research", "practice"):
        assert (interview / folder_name).is_dir()
        assert (interview / folder_name / ".gitkeep").is_file()
    for file_name in ("checklist.md", "tasks.md", "directions.md", "questions.md", "asked.md", "meta.json"):
        assert (interview / file_name).is_file()


def test_new_interview_creates_local_and_secret_empty(tmp_root):
    interview = create_interview(tmp_root)

    for folder_name in ("local", "secret"):
        assert (interview / folder_name).is_dir()
        assert list((interview / folder_name).iterdir()) == []


def test_new_interview_writes_meta_json(tmp_root):
    interview = create_interview(tmp_root, interview_date="2026-12-01")

    meta = json.loads((interview / "meta.json").read_text(encoding="utf-8"))

    # (d_day is computed when the board is built, never stored)
    assert meta == {"org": "Acme Corp", "kind": "job", "date": "2026-11", "interview_date": "2026-12-01"}


def test_new_interview_meta_has_no_interview_date_by_default(tmp_root):
    meta = json.loads((create_interview(tmp_root) / "meta.json").read_text(encoding="utf-8"))

    assert meta["interview_date"] is None


def test_new_interview_template_tasks_start_with_the_default_open_items(tmp_root):
    interview = create_interview(tmp_root)

    open_tasks = interview_folder.read_open_tasks(interview / "tasks.md")

    assert open_tasks == DEFAULT_OPEN_TASKS
    text = (interview / "tasks.md").read_text(encoding="utf-8")
    assert "## Open" in text
    assert "## Done" in text


def test_new_interview_template_has_the_documented_sections(tmp_root):
    interview = create_interview(tmp_root)

    checklist = (interview / "checklist.md").read_text(encoding="utf-8")
    assert "| Item | Detail | Deadline | Source | Confirmed |" in checklist
    directions = (interview / "directions.md").read_text(encoding="utf-8")
    assert "## Say this way" in directions and "## Do not say" in directions
    assert "| Question | From (submitted sentence) | Type |" in (interview / "questions.md").read_text(encoding="utf-8")
    assert (interview / "asked.md").read_text(encoding="utf-8").strip().startswith("#")


def test_new_interview_refuses_an_existing_name_and_keeps_it_untouched(tmp_root):
    interview = create_interview(tmp_root)
    (interview / "tasks.md").write_text("my own tasks\n", encoding="utf-8")

    with pytest.raises(interview_folder.InterviewFolderError, match="already exists"):
        create_interview(tmp_root, org="acme corp")

    assert (interview / "tasks.md").read_text(encoding="utf-8") == "my own tasks\n"


@pytest.mark.parametrize("org, kind", [("예시대학교", "oral-exam"), ("Acme Corp", "구술시험"), ("!!!", "job"), ("", "job")])
def test_new_interview_asks_for_a_romanized_name_when_nothing_ascii_is_left(tmp_root, org, kind):
    with pytest.raises(interview_folder.InterviewFolderError, match="romanized"):
        create_interview(tmp_root, org=org, kind=kind)

    assert not interviews_folder(tmp_root).exists() or list(interviews_folder(tmp_root).iterdir()) == []


def test_new_interview_caps_org_and_kind_at_forty_characters_each(tmp_root):
    forty = "a" * 40

    interview = create_interview(tmp_root, org=forty, kind=forty)

    assert interview.name == f"2026-11-{forty}-{forty}"
    for org, kind in ((forty + "b", "job"), ("Acme Corp", forty + "b")):
        with pytest.raises(interview_folder.InterviewFolderError, match="40 characters"):
            create_interview(tmp_root, org=org, kind=kind)


def test_new_interview_measures_the_length_after_normalizing(tmp_root):
    # (symbols and extra spaces are dropped first: 60 raw characters, 20 kept)
    org = "a" * 20 + "!" * 20 + " " * 20

    assert create_interview(tmp_root, org=org).name == f"2026-11-{'a' * 20}-job"


@pytest.mark.parametrize("date_ym", ["2026-13", "2026-00", "202611", "2026-1", "26-11", "2026-11-01", "", "2026-11\n"])
def test_new_interview_refuses_a_bad_year_month(tmp_root, date_ym):
    with pytest.raises(interview_folder.InterviewFolderError, match="YYYY-MM"):
        create_interview(tmp_root, date_ym=date_ym)


@pytest.mark.parametrize("interview_date", ["2026-02-30", "20261201", "2026-12", "tomorrow", "2026-1-5", "2026-12-01\n"])
def test_new_interview_refuses_a_bad_interview_date(tmp_root, interview_date):
    with pytest.raises(interview_folder.InterviewFolderError, match="YYYY-MM-DD"):
        create_interview(tmp_root, interview_date=interview_date)

    assert not interviews_folder(tmp_root).exists() or list(interviews_folder(tmp_root).iterdir()) == []


# ---------- submit ----------


def test_submit_copies_from_writing_to_submitted_keeping_the_relative_path(tmp_root):
    interview = create_interview(tmp_root)
    plan = write_writing_file(interview, "plan.md", "research plan")
    nested = write_writing_file(interview, "drafts/essay.md", "essay")

    copied = interview_folder.submit(tmp_root, interview, [plan, nested])

    assert copied == [interview / "submitted" / "plan.md", interview / "submitted" / "drafts" / "essay.md"]
    assert (interview / "submitted" / "plan.md").read_text(encoding="utf-8") == "research plan"
    assert (interview / "submitted" / "drafts" / "essay.md").read_text(encoding="utf-8") == "essay"
    # (a copy: the draft stays where it was)
    assert plan.read_text(encoding="utf-8") == "research plan"


def test_submit_refuses_overwrite(tmp_root):
    interview = create_interview(tmp_root)
    plan = write_writing_file(interview, "plan.md", "v2 draft")
    (interview / "submitted" / "plan.md").write_text("v1 as submitted", encoding="utf-8")

    with pytest.raises(interview_folder.InterviewFolderError, match="already submitted"):
        interview_folder.submit(tmp_root, interview, [plan])

    assert (interview / "submitted" / "plan.md").read_text(encoding="utf-8") == "v1 as submitted"


def test_submit_copies_nothing_when_one_file_would_overwrite(tmp_root):
    interview = create_interview(tmp_root)
    fresh = write_writing_file(interview, "a-new.md")
    taken = write_writing_file(interview, "taken.md")
    (interview / "submitted" / "taken.md").write_text("kept", encoding="utf-8")

    with pytest.raises(interview_folder.InterviewFolderError):
        interview_folder.submit(tmp_root, interview, [fresh, taken])

    assert not (interview / "submitted" / "a-new.md").exists()


def test_submit_accepts_a_file_listed_twice_once(tmp_root):
    interview = create_interview(tmp_root)
    plan = write_writing_file(interview, "plan.md")

    copied = interview_folder.submit(tmp_root, interview, [plan, plan])

    assert copied == [interview / "submitted" / "plan.md"]


def test_submit_refuses_paths_outside_writing(tmp_root):
    interview = create_interview(tmp_root)
    secret_note = interview / "secret" / "salary.md"
    secret_note.write_text("private", encoding="utf-8")
    outside_file = tmp_root / "elsewhere.md"
    outside_file.write_text("x", encoding="utf-8")
    write_writing_file(interview, "ok.md")

    for bad_path in (
        secret_note,
        outside_file,
        interview / "writing" / ".." / "secret" / "salary.md",
        interview / "tasks.md",
    ):
        with pytest.raises(interview_folder.InterviewFolderError, match="inside writing"):
            interview_folder.submit(tmp_root, interview, [bad_path])

    assert list((interview / "submitted").iterdir()) == [interview / "submitted" / ".gitkeep"]


def test_submit_refuses_a_symlink_that_points_out_of_writing(tmp_root):
    interview = create_interview(tmp_root)
    secret_note = interview / "secret" / "salary.md"
    secret_note.write_text("private", encoding="utf-8")
    link = interview / "writing" / "innocent.md"
    try:
        os.symlink(secret_note, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")

    with pytest.raises(interview_folder.InterviewFolderError, match="inside writing"):
        interview_folder.submit(tmp_root, interview, [link])

    assert not (interview / "submitted" / "innocent.md").exists()


def test_submit_refuses_a_missing_file_and_a_folder(tmp_root):
    interview = create_interview(tmp_root)
    write_writing_file(interview, "drafts/essay.md")

    with pytest.raises(interview_folder.InterviewFolderError, match="not found"):
        interview_folder.submit(tmp_root, interview, [interview / "writing" / "ghost.md"])
    with pytest.raises(interview_folder.InterviewFolderError, match="not a file"):
        interview_folder.submit(tmp_root, interview, [interview / "writing" / "drafts"])


def test_submit_reads_a_relative_path_from_the_interview_folder(tmp_root, monkeypatch):
    interview = create_interview(tmp_root)
    write_writing_file(interview, "plan.md", "text")
    monkeypatch.chdir(tmp_root)

    copied = interview_folder.submit(tmp_root, interview, [Path("writing/plan.md")])

    assert copied == [interview / "submitted" / "plan.md"]


def test_submit_works_only_on_a_folder_directly_under_interviews(tmp_root):
    stray_folder = tmp_root / "stray"
    (stray_folder / "writing").mkdir(parents=True)
    (stray_folder / "writing" / "a.md").write_text("x", encoding="utf-8")
    create_interview(tmp_root)

    with pytest.raises(interview_folder.InterviewFolderError, match="under prep/interviews"):
        interview_folder.submit(tmp_root, stray_folder, [stray_folder / "writing" / "a.md"])
    with pytest.raises(interview_folder.InterviewFolderError, match="not found"):
        interview_folder.submit(tmp_root, interviews_folder(tmp_root) / "ghost", [])


# ---------- CLI ----------


def test_cli_submit_accepts_a_relative_folder_path_and_prints_root_relative_paths(tmp_root, monkeypatch, capsys):
    interview = create_interview(tmp_root)
    write_writing_file(interview, "plan.md")
    monkeypatch.chdir(tmp_root)
    capsys.readouterr()

    exit_code = interview_folder.main(["submit", f"prep/interviews/{interview.name}", "writing/plan.md"])

    assert exit_code == 0
    assert f"submitted prep/interviews/{interview.name}/submitted/plan.md" in capsys.readouterr().out.replace("\\", "/")
    assert (interview / "submitted" / "plan.md").is_file()


def test_cli_submit_accepts_dot_inside_the_interview_folder(tmp_root, monkeypatch, capsys):
    interview = create_interview(tmp_root)
    write_writing_file(interview, "plan.md")
    monkeypatch.chdir(interview)
    capsys.readouterr()

    assert interview_folder.main(["submit", ".", "writing/plan.md"]) == 0

    assert (interview / "submitted" / "plan.md").is_file()


def test_cli_submit_prefers_a_folder_name_under_interviews_over_a_same_named_local_folder(tmp_root, monkeypatch):
    interview = create_interview(tmp_root)
    write_writing_file(interview, "plan.md")
    # (a folder with the same name in the current directory is not an interview)
    (tmp_root / interview.name).mkdir()
    monkeypatch.chdir(tmp_root)

    assert interview_folder.main(["submit", interview.name, "writing/plan.md"]) == 0
    assert (interview / "submitted" / "plan.md").is_file()


def test_display_path_is_relative_to_the_root_and_falls_back_to_the_path_itself(tmp_root, tmp_path_factory):
    inside = tmp_root / "prep" / "interviews" / "x" / "submitted" / "a.md"
    outside = tmp_path_factory.mktemp("elsewhere") / "a.md"

    assert interview_folder.display_path(tmp_root, inside) == "prep/interviews/x/submitted/a.md"
    assert interview_folder.display_path(tmp_root, outside) == outside.as_posix()


def test_cli_new_reports_the_folder_when_the_board_cannot_be_rebuilt(tmp_root, capsys):
    status_file = tmp_root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True)
    damaged_text = f"# Status\n{interview_folder.BOARD_START_MARKER}\nno end marker\n"
    status_file.write_text(damaged_text, encoding="utf-8")

    exit_code = interview_folder.main(["new", "--date", "2026-11", "--org", "Acme", "--kind", "mock"])

    assert exit_code == interview_folder.EXIT_INVALID_INPUT
    error_text = capsys.readouterr().err
    assert "2026-11-acme-mock was created" in error_text
    assert "status could not be rebuilt" in error_text and "markers are damaged" in error_text
    assert len(error_text.strip().splitlines()) == 1
    assert (interviews_folder(tmp_root) / "2026-11-acme-mock" / "meta.json").is_file()
    assert status_file.read_text(encoding="utf-8") == damaged_text


def test_cli_status_with_damaged_markers_exits_with_one_line(tmp_root, capsys):
    status_file = tmp_root / "prep" / "status.md"
    status_file.parent.mkdir(parents=True)
    status_file.write_text(f"{interview_folder.BOARD_END_MARKER}\n{interview_folder.BOARD_START_MARKER}\n", encoding="utf-8")

    assert interview_folder.main(["status"]) == interview_folder.EXIT_INVALID_INPUT

    assert capsys.readouterr().err.startswith("[interview] status.md board markers are damaged")


def test_cli_translates_a_disk_error_into_one_line(tmp_root, monkeypatch, capsys):
    def fail(*arguments, **keyword_arguments):
        raise PermissionError("disk is read-only")

    monkeypatch.setattr(interview_folder.shutil, "copytree", fail)

    exit_code = interview_folder.main(["new", "--date", "2026-11", "--org", "Acme", "--kind", "mock"])

    assert exit_code == interview_folder.EXIT_INVALID_INPUT
    error_text = capsys.readouterr().err
    assert error_text.strip() == "[interview] disk is read-only"
    # (the half-built folder is gone, so the name is free again)
    assert list(interviews_folder(tmp_root).iterdir()) == []



def test_cli_new_creates_the_folder_and_rebuilds_the_board(tmp_root, capsys):
    exit_code = interview_folder.main(
        ["new", "--date", "2026-11", "--org", "Acme Corp", "--kind", "job", "--interview-date", "2026-12-01"]
    )

    assert exit_code == 0
    assert "2026-11-acme-corp-job" in capsys.readouterr().out
    assert (interviews_folder(tmp_root) / "2026-11-acme-corp-job" / "meta.json").is_file()
    assert "2026-11-acme-corp-job" in (tmp_root / "prep" / "status.md").read_text(encoding="utf-8")


def test_cli_new_asks_for_a_romanized_name(tmp_root, capsys):
    exit_code = interview_folder.main(["new", "--date", "2026-11", "--org", "예시대학교", "--kind", "oral-exam"])

    assert exit_code == interview_folder.EXIT_INVALID_INPUT
    assert "romanized" in capsys.readouterr().err


def test_cli_new_refuses_an_existing_name(tmp_root, capsys):
    arguments = ["new", "--date", "2026-11", "--org", "Acme", "--kind", "mock"]
    assert interview_folder.main(arguments) == 0
    capsys.readouterr()

    assert interview_folder.main(arguments) == interview_folder.EXIT_INVALID_INPUT
    assert "already exists" in capsys.readouterr().err


def test_cli_submit_takes_a_folder_name_and_lists_the_copies(tmp_root, capsys):
    interview = create_interview(tmp_root)
    plan = write_writing_file(interview, "plan.md")
    capsys.readouterr()

    exit_code = interview_folder.main(["submit", interview.name, str(plan)])

    assert exit_code == 0
    assert "submitted/plan.md" in capsys.readouterr().out.replace("\\", "/")
    assert (interview / "submitted" / "plan.md").is_file()


def test_cli_submit_reports_a_refusal(tmp_root, capsys):
    interview = create_interview(tmp_root)
    plan = write_writing_file(interview, "plan.md")
    assert interview_folder.main(["submit", interview.name, str(plan)]) == 0
    capsys.readouterr()

    assert interview_folder.main(["submit", interview.name, str(plan)]) == interview_folder.EXIT_INVALID_INPUT
    assert "already submitted" in capsys.readouterr().err


def test_cli_submit_refuses_an_unknown_folder(tmp_root, capsys):
    assert interview_folder.main(["submit", "no-such-folder", "a.md"]) == interview_folder.EXIT_INVALID_INPUT
    assert "not found" in capsys.readouterr().err


def test_cli_status_prints_the_board_and_writes_it(tmp_root, capsys):
    create_interview(tmp_root, interview_date="2026-12-01")
    capsys.readouterr()

    assert interview_folder.main(["status"]) == 0

    output = capsys.readouterr().out
    assert "## Interviews" in output and "## Top tasks" in output
    assert (tmp_root / "prep" / "status.md").read_text(encoding="utf-8").strip() == output.strip()
