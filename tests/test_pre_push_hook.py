"""Tests for .githooks/pre-push: the hook script itself and real `git push` runs against a bare repository"""

import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from repo_helpers import commit_all_staged, run_git, write_local_rule, write_storage

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

requires_posix_shell = pytest.mark.skipif(
    sys.platform.startswith("win") or shutil.which("sh") is None, reason="hook runs under a POSIX sh"
)


@pytest.fixture
def hooked_repo(git_root, tmp_path_factory):
    """Repo with the real .githooks and scripts copied in, one commit, and a bare repository as origin"""
    shutil.copytree(REPOSITORY_ROOT / ".githooks", git_root / ".githooks")
    shutil.copytree(
        REPOSITORY_ROOT / "tutor" / "scripts", git_root / "tutor" / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    run_git(git_root, "config", "core.hooksPath", ".githooks")
    (git_root / "README.md").write_text("engine\n", encoding="utf-8")
    run_git(git_root, "add", "README.md")
    commit_all_staged(git_root)
    bare_repository = tmp_path_factory.mktemp("bare")
    subprocess.run(["git", "init", "--bare", "-q", str(bare_repository)], check=True)
    run_git(git_root, "remote", "add", "origin", str(bare_repository))
    return git_root, bare_repository


def push_to_origin(root):
    return subprocess.run(
        ["git", "-C", str(root), "push", "origin", "HEAD:refs/heads/main"], capture_output=True, text=True
    )


def count_bare_branches(bare_repository):
    return len(run_git(bare_repository, "for-each-ref", "refs/heads").splitlines())


def test_pre_push_hook_file_is_an_executable_posix_script():
    hook_file = REPOSITORY_ROOT / ".githooks" / "pre-push"
    content = hook_file.read_bytes()
    assert content.startswith(b"#!/bin/sh\n")
    assert b"\r" not in content
    assert b'can-push --remote-name "$1" --remote-url "$2"' in content
    assert b"py -3" in content
    if not sys.platform.startswith("win"):
        assert hook_file.stat().st_mode & stat.S_IXUSR


@requires_posix_shell
def test_pre_push_hook_blocks_an_unverifiable_remote_in_private_mode(hooked_repo):
    root, bare_repository = hooked_repo
    write_storage(root, "private")

    completed = push_to_origin(root)

    assert completed.returncode != 0
    assert "push refused" in completed.stderr
    assert count_bare_branches(bare_repository) == 0


@requires_posix_shell
def test_pre_push_hook_lets_a_confirmed_remote_through(hooked_repo):
    root, bare_repository = hooked_repo
    write_storage(root, "private", confirmed_private_remote=str(bare_repository))

    completed = push_to_origin(root)

    assert completed.returncode == 0, completed.stderr
    assert count_bare_branches(bare_repository) == 1


@requires_posix_shell
def test_pre_push_hook_lets_public_encrypted_storage_push(hooked_repo):
    root, bare_repository = hooked_repo
    write_storage(root, "public-encrypted")

    assert push_to_origin(root).returncode == 0
    assert count_bare_branches(bare_repository) == 1


@requires_posix_shell
def test_pre_push_hook_blocks_local_storage_with_tracked_prep_files(hooked_repo):
    root, bare_repository = hooked_repo
    write_storage(root, "local")
    write_local_rule(root)
    (root / "prep" / "status.md").write_text("# Status\n", encoding="utf-8")
    run_git(root, "add", "-f", "prep/status.md")
    commit_all_staged(root)

    completed = push_to_origin(root)

    assert completed.returncode != 0
    assert "prep/status.md" in completed.stderr
    assert count_bare_branches(bare_repository) == 0


@requires_posix_shell
def test_pre_push_hook_checks_the_url_it_is_given_not_origin(hooked_repo, tmp_path_factory):
    # origin is fine for private storage only when confirmed; a second, unconfirmed remote must still be blocked
    root, bare_repository = hooked_repo
    write_storage(root, "private", confirmed_private_remote=str(bare_repository))
    other_bare = tmp_path_factory.mktemp("other_bare")
    subprocess.run(["git", "init", "--bare", "-q", str(other_bare)], check=True)
    run_git(root, "remote", "add", "backup", str(other_bare))

    completed = subprocess.run(
        ["git", "-C", str(root), "push", "backup", "HEAD:refs/heads/main"], capture_output=True, text=True
    )

    assert completed.returncode != 0
    assert count_bare_branches(other_bare) == 0


@requires_posix_shell
def test_pre_push_hook_blocks_local_storage_when_history_holds_prep_unless_confirmed(hooked_repo):
    root, bare_repository = hooked_repo
    # prep/ was committed once, then untracked: the index is clean but the history to push still holds it
    (root / "prep").mkdir()
    (root / "prep" / "status.md").write_text("# Status\n", encoding="utf-8")
    run_git(root, "add", "-f", "prep/status.md")
    commit_all_staged(root)
    run_git(root, "rm", "-r", "--cached", "-q", "--", "prep")
    commit_all_staged(root)
    write_storage(root, "local")
    write_local_rule(root)

    blocked = push_to_origin(root)
    assert blocked.returncode != 0
    assert "earlier commits" in blocked.stderr
    assert count_bare_branches(bare_repository) == 0

    write_storage(root, "local", confirmed_private_remote=str(bare_repository))
    allowed = push_to_origin(root)
    assert allowed.returncode == 0, allowed.stderr
    assert count_bare_branches(bare_repository) == 1
