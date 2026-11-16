#!/usr/bin/env python3
"""Agent file sync: CLAUDE.md > AGENTS.md, .claude/commands/<name>.md > .agents/skills/<name>/SKILL.md (generated, never hand-edited).

    python3 tutor/scripts/sync_agents.py write     regenerate every file (and drop skills whose command is gone)
    python3 tutor/scripts/sync_agents.py check     exit 1 listing missing, drifted and extra generated files

AGENTS.md = one notice line + CLAUDE.md. A skill = Codex front matter (name, description) + notice + the command body.
Skill description = the command's front matter `description`, else its first heading, else its first non-empty line.
Only skills that carry the notice are treated as generated: a hand-written skill in .agents/skills/ is left alone.
write never writes through a symlink (a symlinked target or skill folder is skipped and reported) and never deletes through one.
Exit codes: 0 ok, 1 drift found or a target was skipped.
"""

import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

import common

AGENTS_FILE_NAME = "AGENTS.md"
CLAUDE_FILE_NAME = "CLAUDE.md"
COMMANDS_FOLDER = Path(".claude") / "commands"
SKILLS_FOLDER = Path(".agents") / "skills"
SKILL_FILE_NAME = "SKILL.md"

SCRIPT_PATH = "tutor/scripts/sync_agents.py"
# first line of AGENTS.md
AGENTS_NOTICE = f"<!-- Generated from {CLAUDE_FILE_NAME} by {SCRIPT_PATH}. Do not edit. -->"
SKILL_NOTICE_TEMPLATE = "<!-- Generated from {command_path} by " + SCRIPT_PATH + ". Do not edit. -->"
# every generated skill carries this prefix: it is what tells a generated skill from a hand-written one
SKILL_NOTICE_PREFIX = "<!-- Generated from .claude/commands/"

FRONT_MATTER_DELIMITER = "---"
DESCRIPTION_KEY = "description"
# YAML block scalar markers: `description: >` or `|` (the text is on the following indented lines)
BLOCK_SCALAR_MARKERS = (">", "|", ">-", "|-", ">+", "|+")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(?P<title>\S.*?)\s*#*\s*$")
# a description that may stand unquoted in a YAML front matter line
PLAIN_YAML_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.()/_'-]*$")

EXIT_OK = 0
EXIT_DRIFT = 1

# write result: files written, targets skipped because a symlink is in the way
SyncResult = namedtuple("SyncResult", ["written", "skipped"])


def read_utf8_text(path):
    """File text with LF endings and no byte order mark (reading in text mode turns CRLF into LF)"""
    return Path(path).read_text(encoding="utf-8-sig")


def split_front_matter(text):
    """Command text > (front matter lines, body); no front matter: ([], text)"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        return [], text
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_DELIMITER:
            return lines[1:index], "\n".join(lines[index + 1 :])
    # (no closing line: not a front matter block)
    return [], text


def strip_matching_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_front_matter_description(front_matter_lines):
    """description value of a front matter block: first non-empty line (block scalars: the first indented line); '' if none"""
    for index, line in enumerate(front_matter_lines):
        key, separator, value = line.partition(":")
        if not separator or key.strip() != DESCRIPTION_KEY:
            continue
        value = value.strip()
        if value in BLOCK_SCALAR_MARKERS:
            for continuation in front_matter_lines[index + 1 :]:
                if continuation.strip():
                    return continuation.strip()
            return ""
        return strip_matching_quotes(value)
    return ""


def find_first_heading_or_line(body):
    """First markdown heading title of the body; without one, its first non-empty line; '' for an empty body"""
    first_line = ""
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        heading = HEADING_PATTERN.match(stripped)
        if heading:
            return heading.group("title")
        first_line = first_line or stripped
    return first_line


def choose_description(front_matter_lines, body, command_name):
    """Front matter description > first heading > first non-empty line > command name"""
    return read_front_matter_description(front_matter_lines) or find_first_heading_or_line(body) or command_name


def format_front_matter_value(text):
    """One-line YAML value: plain when safe, else a double-quoted string (JSON strings are valid YAML)"""
    if PLAIN_YAML_PATTERN.match(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def build_skill_text(command_name, command_text):
    """Command file > skill file: Codex front matter, notice, command body (its own front matter removed)"""
    front_matter_lines, body = split_front_matter(command_text)
    description = format_front_matter_value(choose_description(front_matter_lines, body, command_name))
    notice = SKILL_NOTICE_TEMPLATE.format(command_path=f"{COMMANDS_FOLDER.as_posix()}/{command_name}.md")
    skill_front_matter = f"{FRONT_MATTER_DELIMITER}\nname: {command_name}\n{DESCRIPTION_KEY}: {description}\n{FRONT_MATTER_DELIMITER}"
    # (blank lines between the front matter and the body are dropped; the body itself is kept as written)
    body_without_leading_blank_lines = body.lstrip("\n")
    return f"{skill_front_matter}\n\n{notice}\n\n{body_without_leading_blank_lines}"


def list_command_names(root):
    """Names of .claude/commands/*.md (file stem), sorted"""
    commands_folder = Path(root) / COMMANDS_FOLDER
    if not commands_folder.is_dir():
        return []
    return sorted(path.stem for path in commands_folder.glob("*.md") if path.is_file())


def generate(root):
    """Every generated file: {absolute path: text}; AGENTS.md only when CLAUDE.md exists, one skill per command"""
    root = Path(root)
    generated = {}
    claude_file = root / CLAUDE_FILE_NAME
    if claude_file.is_file():
        generated[root / AGENTS_FILE_NAME] = f"{AGENTS_NOTICE}\n\n{read_utf8_text(claude_file)}"
    for command_name in list_command_names(root):
        command_text = read_utf8_text(root / COMMANDS_FOLDER / f"{command_name}.md")
        generated[root / SKILLS_FOLDER / command_name / SKILL_FILE_NAME] = build_skill_text(command_name, command_text)
    return generated


def is_behind_symlink(root, path):
    """The path is a symlink or sits below one (under root): never written or deleted through"""
    return common.has_symlink_component(root, Path(path).relative_to(root).as_posix())


def find_stale_skill_files(root, generated):
    """Skill files that carry the generated notice but have no command (any more)"""
    skills_folder = Path(root) / SKILLS_FOLDER
    if not skills_folder.is_dir():
        return []
    stale = []
    for skill_file in sorted(skills_folder.glob(f"*/{SKILL_FILE_NAME}")):
        if skill_file in generated or not skill_file.is_file() or is_behind_symlink(root, skill_file):
            continue
        try:
            is_generated = SKILL_NOTICE_PREFIX in skill_file.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        if is_generated:
            stale.append(skill_file)
    return stale


def describe_path(root, path):
    return Path(path).relative_to(root).as_posix()


def check(root):
    """Problems as text lines (empty: in sync): missing, drifted, extra (generated file with no source)"""
    root = Path(root)
    generated = generate(root)
    problems = []
    for path, expected_text in generated.items():
        if not path.is_file():
            problems.append(f"missing: {describe_path(root, path)}")
        elif path.read_bytes() != expected_text.encode("utf-8"):
            problems.append(f"drifted: {describe_path(root, path)}")
    agents_file = root / AGENTS_FILE_NAME
    if agents_file.is_file() and agents_file not in generated:
        problems.append(f"extra: {AGENTS_FILE_NAME} (no {CLAUDE_FILE_NAME})")
    for skill_file in find_stale_skill_files(root, generated):
        command_path = f"{COMMANDS_FOLDER.as_posix()}/{skill_file.parent.name}.md"
        problems.append(f"extra: {describe_path(root, skill_file)} (no command {command_path})")
    return problems


def write_generated_files(root):
    """Write every generated file (UTF-8, LF) except symlinked targets, delete stale generated skills > SyncResult"""
    root = Path(root)
    generated = generate(root)
    written = []
    skipped = []
    for path, text in generated.items():
        # (a link in the way: writing would land outside the repo or on the link's target)
        if is_behind_symlink(root, path):
            skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    for skill_file in find_stale_skill_files(root, generated):
        skill_file.unlink()
        try:
            # (only an empty folder goes: anything else in it is not ours)
            skill_file.parent.rmdir()
        except OSError:
            pass
    return SyncResult(written, skipped)


def write(root):
    """write_generated_files > the written paths"""
    return write_generated_files(root).written


def command_write(root):
    result = write_generated_files(root)
    for path in result.written:
        print(f"wrote {describe_path(root, path)}")
    if not result.written and not result.skipped:
        print(f"nothing to generate: no {CLAUDE_FILE_NAME} and no {COMMANDS_FOLDER.as_posix()}/*.md")
    for path in result.skipped:
        print(
            f"skipped: {describe_path(root, path)} is a symlink or inside a symlinked folder: delete the link, then run write again",
            file=sys.stderr,
        )
    return EXIT_DRIFT if result.skipped else EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(description="Generate AGENTS.md and .agents/skills from CLAUDE.md and .claude/commands")
    parser.add_argument("command", choices=("write", "check"))
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    root = common.repo_root()
    try:
        if arguments.command == "write":
            return command_write(root)
        problems = check(root)
    except (OSError, UnicodeDecodeError) as error:
        print(f"[sync_agents] {error}", file=sys.stderr)
        return EXIT_DRIFT
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"generated files are out of sync: run python3 {SCRIPT_PATH} write", file=sys.stderr)
        return EXIT_DRIFT
    print("agent files are in sync")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
