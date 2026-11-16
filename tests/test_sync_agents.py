"""Tests for sync_agents.py: AGENTS.md and .agents/skills/<name>/SKILL.md generated from CLAUDE.md and .claude/commands/*.md"""

import os

import pytest

import sync_agents

AGENTS_NOTICE = "<!-- Generated from CLAUDE.md by tutor/scripts/sync_agents.py. Do not edit. -->\n\n"
CLAUDE_TEXT = "# Tutor rules\n\nAsk one question at a time.\n"
SPAR_COMMAND = (
    "---\n"
    "description: Start a sparring session: review first, then one question at a time\n"
    "argument-hint: [interview]\n"
    "---\n"
    "\n"
    "# Spar\n"
    "\n"
    "Read prep/status.md first.\n"
)
SPAR_SKILL = (
    "---\n"
    "name: spar\n"
    'description: "Start a sparring session: review first, then one question at a time"\n'
    "---\n"
    "\n"
    "<!-- Generated from .claude/commands/spar.md by tutor/scripts/sync_agents.py. Do not edit. -->\n"
    "\n"
    "# Spar\n"
    "\n"
    "Read prep/status.md first.\n"
)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def skill_path(root, name):
    return root / ".agents" / "skills" / name / "SKILL.md"


def make_symlink(link_path, target_path):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target_path, link_path)
    except (OSError, NotImplementedError):
        pytest.skip("this platform cannot create symlinks here")


@pytest.fixture
def project(tmp_root):
    write_text(tmp_root / "CLAUDE.md", CLAUDE_TEXT)
    write_text(tmp_root / ".claude" / "commands" / "spar.md", SPAR_COMMAND)
    return tmp_root


# ---------- generate ----------


def test_generate_builds_agents_md_and_one_skill_per_command(project):
    generated = sync_agents.generate(project)

    assert generated == {
        project / "AGENTS.md": AGENTS_NOTICE + CLAUDE_TEXT,
        skill_path(project, "spar"): SPAR_SKILL,
    }


def test_generate_makes_a_skill_for_every_command(project):
    write_text(project / ".claude" / "commands" / "review.md", "---\ndescription: Review the week\n---\nBody\n")
    write_text(project / ".claude" / "commands" / "notes.txt", "not a command")

    generated = sync_agents.generate(project)

    assert sorted(path.parent.name for path in generated if path.name == "SKILL.md") == ["review", "spar"]
    review_skill = generated[skill_path(project, "review")]
    assert review_skill.startswith("---\nname: review\ndescription: Review the week\n---\n\n")
    assert review_skill.endswith("-->\n\nBody\n")


def test_generate_works_with_nothing_to_generate_from(tmp_root):
    assert sync_agents.generate(tmp_root) == {}


def test_generate_without_commands_still_builds_agents_md(tmp_root):
    write_text(tmp_root / "CLAUDE.md", CLAUDE_TEXT)

    assert sync_agents.generate(tmp_root) == {tmp_root / "AGENTS.md": AGENTS_NOTICE + CLAUDE_TEXT}


def test_generate_without_claude_md_still_builds_skills(tmp_root):
    write_text(tmp_root / ".claude" / "commands" / "spar.md", SPAR_COMMAND)

    assert list(sync_agents.generate(tmp_root)) == [skill_path(tmp_root, "spar")]


@pytest.mark.parametrize(
    "command_text, expected_description_line",
    [
        pytest.param("---\ndescription: Plain words here\n---\nBody\n", "description: Plain words here", id="plain"),
        pytest.param('---\ndescription: "Quoted one"\n---\nBody\n', "description: Quoted one", id="quotes-removed"),
        pytest.param("---\ndescription: 'Single quoted'\n---\nBody\n", "description: Single quoted", id="single-quotes"),
        pytest.param("---\ndescription: >\n  First line\n  second line\n---\nBody\n", "description: First line", id="block"),
        pytest.param("---\nargument-hint: x\n---\n# The Heading\nBody\n", "description: The Heading", id="no-description-uses-heading"),
        pytest.param("# Just A Heading\nBody\n", "description: Just A Heading", id="no-front-matter-uses-heading"),
        pytest.param("\n\nFirst real line\nsecond\n", "description: First real line", id="no-heading-uses-first-line"),
        pytest.param("---\ndescription:\n---\n# Fallback\n", "description: Fallback", id="empty-description-uses-heading"),
        pytest.param("", "description: spar", id="empty-file-uses-the-name"),
        pytest.param("---\ndescription: ends: with #hash\n---\nBody\n", 'description: "ends: with #hash"', id="needs-quoting"),
    ],
)
def test_generate_picks_the_description(tmp_root, command_text, expected_description_line):
    write_text(tmp_root / ".claude" / "commands" / "spar.md", command_text)

    skill_text = sync_agents.generate(tmp_root)[skill_path(tmp_root, "spar")]

    assert skill_text.split("\n")[1:3] == ["name: spar", expected_description_line]


def test_generate_strips_front_matter_but_keeps_the_rest_of_the_body(tmp_root):
    write_text(
        tmp_root / ".claude" / "commands" / "spar.md",
        "---\ndescription: d\n---\n\n\nFirst\n\n---\nnot front matter\n$ARGUMENTS\n",
    )

    skill_text = sync_agents.generate(tmp_root)[skill_path(tmp_root, "spar")]

    assert skill_text.endswith("-->\n\nFirst\n\n---\nnot front matter\n$ARGUMENTS\n")
    assert "description: d\n---\n\n<!--" in skill_text
    assert skill_text.count("description:") == 1


def test_generate_normalizes_line_endings_and_a_byte_order_mark(tmp_root):
    (tmp_root / "CLAUDE.md").write_bytes(b"\xef\xbb\xbf# Rules\r\nline\r\n")
    (tmp_root / ".claude" / "commands").mkdir(parents=True)
    (tmp_root / ".claude" / "commands" / "spar.md").write_bytes(b"---\r\ndescription: d\r\n---\r\nBody\r\n")

    generated = sync_agents.generate(tmp_root)

    assert generated[tmp_root / "AGENTS.md"] == AGENTS_NOTICE + "# Rules\nline\n"
    assert generated[skill_path(tmp_root, "spar")].endswith("-->\n\nBody\n")
    assert all("\r" not in text for text in generated.values())


# ---------- check / write ----------


def test_sync_check_detects_drift(project):
    sync_agents.write(project)
    assert sync_agents.check(project) == []

    # a hand edit of a generated file
    agents_file = project / "AGENTS.md"
    agents_file.write_bytes(agents_file.read_bytes() + b"hand edit\n")
    # a generated file that was deleted
    skill_path(project, "spar").unlink()
    # a command that changed after the last write
    write_text(project / ".claude" / "commands" / "review.md", "---\ndescription: New\n---\nBody\n")

    problems = sync_agents.check(project)

    assert any(problem.startswith("drifted") and "AGENTS.md" in problem for problem in problems)
    assert any(problem.startswith("missing") and ".agents/skills/spar/SKILL.md" in problem for problem in problems)
    assert any(problem.startswith("missing") and ".agents/skills/review/SKILL.md" in problem for problem in problems)


def test_sync_check_flags_a_stale_skill_whose_command_is_gone(project):
    sync_agents.write(project)
    (project / ".claude" / "commands" / "spar.md").unlink()

    problems = sync_agents.check(project)

    assert problems == ["extra: .agents/skills/spar/SKILL.md (no command .claude/commands/spar.md)"]


def test_sync_check_flags_agents_md_without_claude_md(project):
    sync_agents.write(project)
    (project / "CLAUDE.md").unlink()

    assert sync_agents.check(project) == ["extra: AGENTS.md (no CLAUDE.md)"]


def test_sync_check_leaves_a_hand_written_skill_alone(project):
    sync_agents.write(project)
    write_text(skill_path(project, "mine"), "---\nname: mine\ndescription: my own skill\n---\n\nHand written.\n")

    assert sync_agents.check(project) == []
    sync_agents.write(project)
    assert "Hand written." in skill_path(project, "mine").read_text(encoding="utf-8")


def test_write_creates_every_generated_file_with_lf_and_utf8(project):
    write_text(project / ".claude" / "commands" / "review.md", "---\ndescription: Weekly review\n---\nCheck it\n")

    written = sync_agents.write(project)

    assert sorted(path.relative_to(project).as_posix() for path in written) == [
        ".agents/skills/review/SKILL.md",
        ".agents/skills/spar/SKILL.md",
        "AGENTS.md",
    ]
    for path in written:
        content = path.read_bytes()
        assert b"\r" not in content
        content.decode("utf-8")
    assert (project / "AGENTS.md").read_bytes() == (AGENTS_NOTICE + CLAUDE_TEXT).encode("utf-8")


def test_write_removes_a_stale_skill_and_its_empty_folder(project):
    sync_agents.write(project)
    (project / ".claude" / "commands" / "spar.md").unlink()

    sync_agents.write(project)

    assert not (project / ".agents" / "skills" / "spar").exists()
    assert sync_agents.check(project) == []


def test_write_keeps_other_files_in_a_stale_skill_folder(project):
    sync_agents.write(project)
    (project / ".claude" / "commands" / "spar.md").unlink()
    extra_file = project / ".agents" / "skills" / "spar" / "notes.md"
    extra_file.write_text("keep me\n", encoding="utf-8")

    sync_agents.write(project)

    assert extra_file.read_text(encoding="utf-8") == "keep me\n"
    assert not skill_path(project, "spar").exists()


def test_write_is_idempotent(project):
    sync_agents.write(project)
    first_pass = {path: path.read_bytes() for path in sync_agents.generate(project)}

    sync_agents.write(project)

    assert {path: path.read_bytes() for path in first_pass} == first_pass


# ---------- symlinks ----------


def test_write_skips_a_symlinked_target_and_reports_it(project, tmp_path_factory):
    outside_file = tmp_path_factory.mktemp("outside") / "elsewhere.md"
    outside_file.write_text("not generated\n", encoding="utf-8")
    make_symlink(project / "AGENTS.md", outside_file)

    result = sync_agents.write_generated_files(project)

    assert outside_file.read_text(encoding="utf-8") == "not generated\n"
    assert (project / "AGENTS.md").is_symlink()
    assert result.skipped == [project / "AGENTS.md"]
    assert result.written == [skill_path(project, "spar")]
    assert sync_agents.write(project) == [skill_path(project, "spar")]


def test_write_skips_a_symlinked_skill_folder(project, tmp_path_factory):
    outside_folder = tmp_path_factory.mktemp("outside")
    make_symlink(project / ".agents" / "skills" / "spar", outside_folder)

    result = sync_agents.write_generated_files(project)

    assert list(outside_folder.iterdir()) == []
    assert result.skipped == [skill_path(project, "spar")]


def test_write_never_deletes_a_stale_skill_through_a_symlinked_folder(project, tmp_path_factory):
    outside_folder = tmp_path_factory.mktemp("outside")
    stale_skill = outside_folder / "SKILL.md"
    stale_skill.write_text("<!-- Generated from .claude/commands/gone.md by tutor/scripts/sync_agents.py. Do not edit. -->\n", encoding="utf-8")
    make_symlink(project / ".agents" / "skills" / "gone", outside_folder)

    sync_agents.write(project)

    assert stale_skill.is_file()


def test_cli_write_reports_a_skipped_symlink_and_fails(project, tmp_path_factory, capsys):
    outside_file = tmp_path_factory.mktemp("outside") / "elsewhere.md"
    outside_file.write_text("not generated\n", encoding="utf-8")
    make_symlink(project / "AGENTS.md", outside_file)

    exit_code = sync_agents.main(["write"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "skipped: AGENTS.md is a symlink" in output.err
    assert outside_file.read_text(encoding="utf-8") == "not generated\n"


# ---------- command line ----------


def test_cli_write_then_check(project, capsys):
    assert sync_agents.main(["check"]) == 1
    capsys.readouterr()

    assert sync_agents.main(["write"]) == 0
    assert "AGENTS.md" in capsys.readouterr().out
    assert sync_agents.main(["check"]) == 0


def test_cli_check_lists_every_problem_and_the_fix_command(project, capsys):
    exit_code = sync_agents.main(["check"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "missing: AGENTS.md" in output.err
    assert "missing: .agents/skills/spar/SKILL.md" in output.err
    assert "sync_agents.py write" in output.err


def test_cli_check_passes_when_there_is_nothing_to_generate(tmp_root):
    assert sync_agents.main(["check"]) == 0
