"""Git facts about prep/: repository detection, the local-storage ignore rule, tracked and ignored paths.

Shared by init.py (setup) and remote_guard.py (push gate): both must read the real git state, not a stored setting.
"""

from pathlib import Path

from privacy_check import GitCommandError, run_git

# pre-commit and pre-push hook folder (relative to the root)
GIT_HOOKS_PATH = ".githooks"

# what local storage writes to prep/.gitignore: everything in prep/ except the file itself
PREP_GITIGNORE_LINES = ("*", "!.gitignore")
# the one tracked path local storage may have under prep/
PREP_GITIGNORE_GIT_PATH = "prep/.gitignore"
# template files that git must report as ignored under local storage
IGNORE_PROBE_PATHS = ("prep/status.md", "prep/profile/facts.md")


def is_git_repository(root):
    """The root itself is a repository (an enclosing repository does not count: its config must stay untouched)"""
    return (Path(root) / ".git").exists()


def prep_gitignore_path(root):
    return Path(root) / "prep" / ".gitignore"


def is_generated_local_rule(ignore_file):
    """True when the file holds exactly the lines local storage writes; missing, unreadable or any other content: False"""
    try:
        return ignore_file.is_file() and ignore_file.read_text(encoding="utf-8").split() == list(PREP_GITIGNORE_LINES)
    except (UnicodeDecodeError, OSError):
        return False


def list_tracked_prep_files(root):
    """Paths git tracks under prep/ except prep/.gitignore (GitCommandError when git cannot answer)"""
    listed = run_git(root, "ls-files", "-z", "--", "prep").split(b"\0")
    paths = [path.decode("utf-8", errors="replace") for path in listed if path]
    return [path for path in paths if path != PREP_GITIGNORE_GIT_PATH]


def list_paths_git_does_not_ignore(root):
    """Probe paths under prep/ that the ignore rules would not hide (index state is left out of the question)"""
    not_ignored = []
    for probe_path in IGNORE_PROBE_PATHS:
        try:
            run_git(root, "check-ignore", "-q", "--no-index", "--", probe_path)
        except GitCommandError:
            # (exit 1: not ignored; any other failure counts the same: ignoring is not proven)
            not_ignored.append(probe_path)
    return not_ignored


def find_commit_holding_prep(root):
    """A commit on any ref that touched prep/ (except prep/.gitignore); None when the history never held prep/ content"""
    output = run_git(root, "log", "--all", "--format=%H", "-1", "--", "prep", f":(exclude){PREP_GITIGNORE_GIT_PATH}")
    return output.decode("ascii", errors="replace").strip() or None
