"""Getting the upstream copy for update.py: the `upstream` remote's URL, a shallow clone, a temp folder that is cleaned up"""

import os
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

import remote_guard
from prep_git_state import is_git_repository
from privacy_check import GitCommandError, run_git
from remote_setup import UPSTREAM_REMOTE_NAME

# where updates come from when the repo has no `upstream` remote
DEFAULT_UPSTREAM_URL = f"https://github.com/{remote_guard.TEMPLATE_OWNER}/{remote_guard.TEMPLATE_REPOSITORY}.git"
CLONE_TIMEOUT_SECONDS = 180
TEMP_FOLDER_PREFIX = "sparring-update-"

# a token in a clone URL or in git's error text is never printed
redact = remote_guard.redact_url_credentials


class UpdateError(Exception):
    """The update cannot be planned or applied (the message says why and what to do)"""


def resolve_upstream_url(root):
    """Fetch URL of the `upstream` remote; without one, the public template"""
    if is_git_repository(root):
        try:
            remote_output = run_git(root, "remote", "get-url", UPSTREAM_REMOTE_NAME)
            configured_url = remote_output.decode("utf-8", errors="replace").strip()
        except GitCommandError:
            # (no such remote)
            configured_url = ""
        if configured_url:
            return configured_url
    return DEFAULT_UPSTREAM_URL


def fetch_upstream(url, destination):
    """git clone --depth 1 url > destination (never prompts for credentials; a token in the URL is not printed)"""
    command = ["git", "clone", "--depth", "1", "--quiet", "--", url, str(destination)]
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        completed = subprocess.run(command, capture_output=True, env=environment, timeout=CLONE_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpdateError(f"git clone failed: {redact(str(error))}") from error
    if completed.returncode != 0:
        reason = completed.stderr.decode("utf-8", errors="replace").strip()
        raise UpdateError(f"git clone failed for {redact(url)}: {redact(reason)}")


def remove_temp_tree(path):
    """Delete a temp folder; git's object files are read-only on Windows, so make them writable first"""
    for directory, _, file_names in os.walk(path):
        for file_name in file_names:
            try:
                os.chmod(os.path.join(directory, file_name), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


@contextmanager
def upstream_checkout(root, source_dir):
    """The directory to compare against: --source as given, else a fresh shallow clone that is removed afterwards"""
    if source_dir:
        yield Path(source_dir).expanduser()
        return
    temp_folder = Path(tempfile.mkdtemp(prefix=TEMP_FOLDER_PREFIX))
    try:
        upstream_url = resolve_upstream_url(root)
        print(f"fetching the engine from {redact(upstream_url)}")
        fetch_upstream(upstream_url, temp_folder / "upstream")
        yield temp_folder / "upstream"
    finally:
        remove_temp_tree(temp_folder)
