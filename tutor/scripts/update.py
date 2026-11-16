#!/usr/bin/env python3
"""Engine update: replace the tutor's own files with the newest upstream copy, never touching the user's files.

    python3 tutor/scripts/update.py plan  [--source DIR]         list what an update would add, change and remove
    python3 tutor/scripts/update.py apply [--source DIR] --yes   do it (nothing is committed)

Upstream = a shallow clone (`git clone --depth 1`) of the `upstream` remote's fetch URL, or the public template when
that remote does not exist; --source DIR uses a local directory instead (no network).
Engine paths (ENGINE_PATHS below) are replaced as a whole: new and changed files are copied, files upstream no longer
has are deleted. The user's records (prep/), .env and every other path are never read from upstream nor written.
apply refuses while engine paths hold uncommitted changes (commit them first) or when a file it would write already
exists as a git-ignored file (the user's own, never overwritten), never writes through a symlink (temp files are created
exclusively, so a planted link is not followed), sets `git config core.hooksPath .githooks` again, and does not commit:
the tutor reviews the diff and commits.
Exit codes: 0 ok, 1 refused or failed.
"""

import argparse
import os
import shlex
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import common
from common import has_symlink_component
from prep_git_state import GIT_HOOKS_PATH, is_git_repository
from privacy_check import GitCommandError, run_git, split_nul_separated_paths
# (re-exported: callers and tests reach the fetch helpers through update)
from upstream_fetch import (  # noqa: F401
    DEFAULT_UPSTREAM_URL,
    UpdateError,
    fetch_upstream,
    resolve_upstream_url,
    upstream_checkout,
)

# paths the engine owns: update replaces them as a whole (files and folders, repo-relative)
ENGINE_PATHS = [
    "tutor",
    "example",
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/commands",
    ".agents/skills",
    ".gitignore",
    ".gitattributes",
    ".githooks",
    "README.md",
    "README.ko.md",
    "pyproject.toml",
    "tests",
    ".github",
]

# temp file name ends like secret_crypt's leftovers: .gitignore (.*.partial) already hides a crashed one
TEMP_FILE_SUFFIX = ".partial"

# an upstream checkout without this folder is not an interview-sparring copy: nothing is planned from it
ENGINE_MARKER_FOLDER = "tutor/scripts"

# build leftovers that a plain (non-git) folder walk skips
BYPRODUCT_FOLDER_NAMES = frozenset({"__pycache__", ".pytest_cache"})
BYPRODUCT_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})
BYPRODUCT_FILE_SUFFIX = ".pyc"

# paths named in one refusal
SHOWN_PATH_COUNT = 10
# status line of `git status --porcelain -z`: two status letters and a space come before the path
PORCELAIN_PATH_OFFSET = 3
# rename or copy entries of `git status --porcelain -z` are followed by one more entry: the original path
PORCELAIN_RENAME_LETTERS = "RC"

GITIGNORE_FILE_NAME = ".gitignore"
GITIGNORE_REVIEW_WARNING = "Warning: review .gitignore: it protects .env, local/ and secret/"

EXIT_OK = 0
EXIT_FAILED = 1


@dataclass
class UpdatePlan:
    added: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    removed: list = field(default_factory=list)

    @property
    def all_paths(self):
        """Every affected path, sorted (repo-relative, posix)"""
        return sorted(self.added + self.changed + self.removed)

    @property
    def is_empty(self):
        return not (self.added or self.changed or self.removed)


# ---------- listing engine files ----------


def is_plain_file(base, relative_path):
    """A regular file that is not a symlink and does not sit below one (the only kind update ever reads)"""
    return not has_symlink_component(base, relative_path) and (Path(base) / relative_path).is_file()


def walk_engine_paths(base):
    """Folder walk for a base that is not a git repository: engine files without build leftovers, symlinks not followed"""
    for engine_path in ENGINE_PATHS:
        start = Path(base) / engine_path
        if start.is_symlink():
            continue
        if start.is_file():
            yield engine_path
        elif start.is_dir():
            for directory, directory_names, file_names in os.walk(start, followlinks=False):
                directory_names[:] = [name for name in directory_names if name not in BYPRODUCT_FOLDER_NAMES]
                for file_name in file_names:
                    if file_name in BYPRODUCT_FILE_NAMES or file_name.endswith(BYPRODUCT_FILE_SUFFIX):
                        continue
                    yield Path(os.path.relpath(Path(directory) / file_name, base)).as_posix()


def list_engine_files(base):
    """Sorted repo-relative paths of the plain files under ENGINE_PATHS; a git base: tracked or not ignored, nothing else"""
    if (Path(base) / ".git").exists():
        listed = run_git(base, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *ENGINE_PATHS)
        candidates = split_nul_separated_paths(listed)
    else:
        candidates = walk_engine_paths(base)
    return sorted({path for path in candidates if is_plain_file(base, path)})


# ---------- plan ----------


def ensure_upstream_is_an_engine_checkout(upstream_dir):
    upstream_dir = Path(upstream_dir)
    if not upstream_dir.is_dir():
        raise UpdateError(f"the upstream source is not a directory: {upstream_dir}")
    if not (upstream_dir / ENGINE_MARKER_FOLDER).is_dir():
        raise UpdateError(
            f"{upstream_dir} does not hold the engine (no {ENGINE_MARKER_FOLDER} folder): "
            "it is not an interview-sparring checkout, so nothing is replaced from it"
        )


def have_same_content(first_path, second_path):
    return Path(first_path).read_bytes() == Path(second_path).read_bytes()


def build_plan(root, upstream_dir):
    """What an update would do: engine files only, grouped as added, changed and removed"""
    ensure_upstream_is_an_engine_checkout(upstream_dir)
    installed_files = set(list_engine_files(root))
    upstream_files = set(list_engine_files(upstream_dir))
    return UpdatePlan(
        added=sorted(upstream_files - installed_files),
        changed=sorted(
            path
            for path in installed_files & upstream_files
            if not have_same_content(Path(root) / path, Path(upstream_dir) / path)
        ),
        removed=sorted(installed_files - upstream_files),
    )


def plan(root, upstream_dir):
    """Paths an update would touch, sorted"""
    return build_plan(root, upstream_dir).all_paths


# ---------- apply ----------


def format_path_list(paths):
    shown = ", ".join(paths[:SHOWN_PATH_COUNT])
    hidden_count = len(paths) - SHOWN_PATH_COUNT
    return f"{shown} and {hidden_count} more" if hidden_count > 0 else shown


def parse_porcelain_paths(status_output):
    """`git status --porcelain -z` bytes > one text per change (a rename or copy entry takes the next entry as its origin)"""
    entries = [os.fsdecode(entry) for entry in status_output.split(b"\0") if entry]
    changes = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        change_path = entry[PORCELAIN_PATH_OFFSET:]
        if entry[0] in PORCELAIN_RENAME_LETTERS or entry[1] in PORCELAIN_RENAME_LETTERS:
            if index < len(entries):
                change_path = f"{change_path} (renamed from {entries[index]})"
                index += 1
        changes.append(change_path)
    return changes


def ensure_engine_is_committed(root):
    """apply needs a git repository whose engine paths hold no uncommitted change (git is the way back from an update)"""
    if not is_git_repository(root):
        raise UpdateError(
            f"{root} is not a git repository (no .git folder): uncommitted changes in engine files cannot be detected; "
            "run git init, commit, then update"
        )
    status = run_git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--", *ENGINE_PATHS)
    dirty_paths = parse_porcelain_paths(status)
    if dirty_paths:
        raise UpdateError(
            f"engine files have uncommitted changes ({format_path_list(dirty_paths)}): "
            "commit them first, update replaces these paths"
        )


def ensure_no_ignored_file_in_the_way(root, relative_paths):
    """A git-ignored file (or link) where the update would write is the user's own: refuse instead of overwriting it"""
    listed = run_git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", *ENGINE_PATHS)
    # (casefold: on macOS and Windows a name that differs only in letter case is the same file)
    write_targets = {relative_path.casefold() for relative_path in relative_paths}
    in_the_way = sorted(path for path in set(split_nul_separated_paths(listed)) if path.casefold() in write_targets)
    if in_the_way:
        raise UpdateError(
            f"git-ignored files sit where the update would write ({format_path_list(in_the_way)}): "
            "they are not overwritten; move or delete them, then update again"
        )


def ensure_no_symlink_in_the_way(root, relative_paths):
    """Nothing is written through a symlinked folder (the file itself may be a symlink: it is replaced, not followed)"""
    for relative_path in relative_paths:
        if has_symlink_component(root, relative_path, include_last=False):
            raise UpdateError(f"refusing to write {relative_path}: a folder on its path is a symlink")


def copy_engine_file(upstream_dir, root, relative_path):
    """Upstream file > root file via an exclusively created temp file and a rename (a link at the target is replaced)"""
    source = Path(upstream_dir) / relative_path
    target = Path(root) / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp: random name, O_CREAT|O_EXCL: a planted link of any name (even an ignored .*.partial one) is never followed
    descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=".", suffix=TEMP_FILE_SUFFIX)
    try:
        with open(source, "rb") as source_file, os.fdopen(descriptor, "wb") as partial_file:
            shutil.copyfileobj(source_file, partial_file)
        # (execute bits of hook files survive: mkstemp starts at 0600)
        os.chmod(partial_name, stat.S_IMODE(source.stat().st_mode))
        os.replace(partial_name, target)
    finally:
        if os.path.lexists(partial_name):
            os.unlink(partial_name)


def delete_engine_file(root, relative_path):
    """Delete the file, then every folder it leaves empty (never the root itself, never a folder that holds anything else)"""
    target = Path(root) / relative_path
    target.unlink()
    for parent in target.parents:
        if parent == Path(root):
            break
        try:
            parent.rmdir()
        except OSError:
            break


def describe_way_back(finished_restorable_paths, finished_added_paths):
    """Commands that undo a half-done update: restore changed and removed files, delete added ones"""
    commands = []
    if finished_restorable_paths:
        commands.append("git restore -- " + " ".join(shlex.quote(path) for path in finished_restorable_paths))
    if finished_added_paths:
        commands.append("git clean -f -- " + " ".join(shlex.quote(path) for path in finished_added_paths))
    return commands


def apply_update(root, upstream_dir):
    """Replace the engine from upstream_dir > the plan that was carried out; nothing is committed"""
    root = Path(root)
    ensure_engine_is_committed(root)
    update_plan = build_plan(root, upstream_dir)
    # (everything is checked before the first file is touched)
    ensure_no_symlink_in_the_way(root, update_plan.added + update_plan.changed)
    ensure_no_ignored_file_in_the_way(root, update_plan.added + update_plan.changed)
    current_path = None
    finished_restorable_paths = []
    finished_added_paths = []
    try:
        # removals first: a folder that becomes a file (or the other way round) needs the old one gone
        for current_path in update_plan.removed:
            delete_engine_file(root, current_path)
            finished_restorable_paths.append(current_path)
        for current_path in update_plan.added:
            copy_engine_file(upstream_dir, root, current_path)
            finished_added_paths.append(current_path)
        for current_path in update_plan.changed:
            copy_engine_file(upstream_dir, root, current_path)
            finished_restorable_paths.append(current_path)
    except OSError as error:
        way_back = describe_way_back(finished_restorable_paths, finished_added_paths)
        raise UpdateError(
            "\n".join(
                [f"update stopped at {current_path}: {error}", "engine files are half updated; to go back run:"]
                + [f"  {command}" for command in way_back]
                + ([] if way_back else ["  (nothing was changed yet)"])
            )
        ) from error
    # (the hook folder arrived with the engine: point git at it again, also when nothing changed)
    run_git(root, "config", "core.hooksPath", GIT_HOOKS_PATH)
    return update_plan


def apply(root, upstream_dir):
    """apply_update > the changed paths, sorted"""
    return apply_update(root, upstream_dir).all_paths


# ---------- command line ----------


def print_path_group(title, paths):
    if paths:
        print(f"{title} ({len(paths)}):")
        for path in paths:
            print(f"  {path}")


def print_plan(update_plan, heading="Engine update plan"):
    if update_plan.is_empty:
        print("Engine is up to date: nothing to change.")
        return
    print(f"{heading}: {len(update_plan.all_paths)} file(s)")
    print_path_group("added", update_plan.added)
    print_path_group("changed", update_plan.changed)
    print_path_group("removed", update_plan.removed)
    print("Your records (prep/) and every file outside the engine paths are never touched.")
    if GITIGNORE_FILE_NAME in update_plan.all_paths:
        print(GITIGNORE_REVIEW_WARNING)


def command_plan(root, source_dir):
    with upstream_checkout(root, source_dir) as upstream_dir:
        update_plan = build_plan(root, upstream_dir)
    print_plan(update_plan)
    if not update_plan.is_empty:
        print("Apply it with: python3 tutor/scripts/update.py apply --yes")
    return EXIT_OK


def command_apply(root, source_dir, is_confirmed):
    if not is_confirmed:
        print(
            "apply replaces engine files: look at `update.py plan` first, then run apply again with --yes",
            file=sys.stderr,
        )
        return EXIT_FAILED
    # (checked before the download, and again inside apply_update)
    ensure_engine_is_committed(root)
    with upstream_checkout(root, source_dir) as upstream_dir:
        update_plan = apply_update(root, upstream_dir)
    print_plan(update_plan, heading="Engine updated")
    if not update_plan.is_empty:
        print("Nothing is committed. Review the changes (git status, git diff), then commit them.")
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(description="Update the tutor engine from upstream; your records are never touched")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="list what an update would change")
    apply_parser = commands.add_parser("apply", help="replace the engine files (needs --yes)")
    for sub_parser in (plan_parser, apply_parser):
        sub_parser.add_argument("--source", metavar="DIR", help="use this local directory instead of cloning upstream")
    apply_parser.add_argument("--yes", action="store_true", help="confirm that engine files are replaced")
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    root = common.repo_root()
    try:
        if arguments.command == "plan":
            return command_plan(root, arguments.source)
        return command_apply(root, arguments.source, arguments.yes)
    except (UpdateError, GitCommandError, OSError) as error:
        print(f"[update] {error}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
