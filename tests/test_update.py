"""Tests for update.py: engine files replaced from an upstream checkout, user files (prep/ and the rest) never touched.

Roots are temp git repos, upstream checkouts are temp directories or local git repos: no network."""

import hashlib
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import update
from repo_helpers import commit_all_staged, run_git

# an installed copy: engine files, the user's records, and a file the user owns outside the engine
INSTALLED_FILES = {
    ".gitignore": "__pycache__/\n.env\n**/local/\n**/secret/\n",
    "CLAUDE.md": "old tutor rules\n",
    "README.md": "old readme\n",
    "tutor/scripts/common.py": "old common\n",
    "tutor/scripts/retired.py": "removed upstream\n",
    "tests/test_common.py": "old test\n",
    "prep/profile/facts.md": "my facts\n",
    "prep/interviews/2026-11-acme/local/notes.md": "private notes\n",
    "prep/interviews/2026-11-acme/secret/answers.md.enc": "ciphertext\n",
    "notes.txt": "a file the user keeps next to the engine\n",
}
# the newer upstream: some engine files changed, one added, one gone; plus things that must never be copied
UPSTREAM_FILES = {
    ".gitignore": "__pycache__/\n.env\n**/local/\n**/secret/\n",
    "CLAUDE.md": "new tutor rules\n",
    "README.md": "old readme\n",
    "tutor/scripts/common.py": "new common\n",
    "tutor/scripts/added.py": "brand new engine file\n",
    "tests/test_common.py": "old test\n",
    "tests/test_added.py": "brand new test\n",
    "prep/profile/facts.md": "UPSTREAM facts must not land\n",
    "prep/profile/upstream-only.md": "UPSTREAM only must not land\n",
    ".env": "UPSTREAM_KEY=1\n",
    ".superpowers/sdd/plan.md": "tool output\n",
    "notes.txt": "UPSTREAM notes must not land\n",
}
ENGINE_PATH_PREFIXES = tuple(f"{engine_path}/" for engine_path in update.ENGINE_PATHS)


def write_files(base, files):
    for relative_path, text in files.items():
        target = base / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def commit_everything(root):
    # -f: the upstream copy tracks .env and .superpowers on purpose (they must still never be copied)
    run_git(root, "add", "-A", "-f")
    commit_all_staged(root)


def hash_tree(base, only=None):
    """{relative posix path: sha256} of every file under base except .git; only: keep paths for which only(path) is true"""
    hashes = {}
    for directory, directory_names, file_names in os.walk(base):
        directory_names[:] = [name for name in directory_names if name != ".git"]
        for file_name in file_names:
            path = os.path.join(directory, file_name)
            relative_path = os.path.relpath(path, base).replace(os.sep, "/")
            if only is None or only(relative_path):
                with open(path, "rb") as opened:
                    hashes[relative_path] = hashlib.sha256(opened.read()).hexdigest()
    return hashes


def is_engine_file(relative_path):
    return relative_path in update.ENGINE_PATHS or relative_path.startswith(ENGINE_PATH_PREFIXES)


def is_user_file(relative_path):
    return not is_engine_file(relative_path)


# the engine part of an installed copy: an upstream that equals it has nothing to update
INSTALLED_ENGINE_FILES = {path: text for path, text in INSTALLED_FILES.items() if is_engine_file(path)}


@pytest.fixture
def installed(git_root):
    write_files(git_root, INSTALLED_FILES)
    commit_everything(git_root)
    return git_root


@pytest.fixture
def make_upstream(tmp_path_factory):
    """Factory: an upstream checkout directory; as_repository=True makes it a real git repository (like a clone)"""

    def build(files=None, as_repository=False):
        upstream = tmp_path_factory.mktemp("upstream")
        write_files(upstream, UPSTREAM_FILES if files is None else files)
        if as_repository:
            run_git(upstream, "init", "-q")
            commit_everything(upstream)
        return upstream

    return build


@pytest.fixture
def upstream(make_upstream):
    return make_upstream()


def make_symlink(link_path, target_path):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target_path, link_path)
    except (OSError, NotImplementedError):
        pytest.skip("this platform cannot create symlinks here")


# ---------- the named contract tests ----------


def test_update_never_touches_prep(installed, make_upstream):
    # the upstream is a real repository that even tracks prep/, .env and .superpowers
    upstream = make_upstream(as_repository=True)
    user_files_before = hash_tree(installed, only=is_user_file)

    update.apply(installed, upstream)

    assert hash_tree(installed, only=is_user_file) == user_files_before
    # prep/ and everything else outside the engine: same files, same bytes (nothing added from upstream either)
    assert not (installed / "prep" / "profile" / "upstream-only.md").exists()
    assert not (installed / ".env").exists()
    assert not (installed / ".superpowers").exists()
    # the engine itself did move
    assert (installed / "tutor" / "scripts" / "common.py").read_text(encoding="utf-8") == "new common\n"


def test_update_plan_lists_only_engine_paths(installed, upstream):
    planned = update.plan(installed, upstream)

    assert planned == [
        "CLAUDE.md",
        "tests/test_added.py",
        "tutor/scripts/added.py",
        "tutor/scripts/common.py",
        "tutor/scripts/retired.py",
    ]
    assert all(is_engine_file(path) for path in planned)


def test_update_plan_tells_added_changed_and_removed_apart(installed, upstream):
    update_plan = update.build_plan(installed, upstream)

    assert update_plan.added == ["tests/test_added.py", "tutor/scripts/added.py"]
    assert update_plan.changed == ["CLAUDE.md", "tutor/scripts/common.py"]
    assert update_plan.removed == ["tutor/scripts/retired.py"]


def test_update_plan_is_empty_when_the_engine_is_identical(installed, make_upstream):
    assert update.plan(installed, make_upstream(INSTALLED_ENGINE_FILES)) == []


# ---------- apply ----------


def test_apply_replaces_adds_and_removes_engine_files(installed, upstream):
    changed_paths = update.apply(installed, upstream)

    assert changed_paths == [
        "CLAUDE.md",
        "tests/test_added.py",
        "tutor/scripts/added.py",
        "tutor/scripts/common.py",
        "tutor/scripts/retired.py",
    ]
    assert (installed / "CLAUDE.md").read_text(encoding="utf-8") == "new tutor rules\n"
    assert (installed / "tutor" / "scripts" / "added.py").read_text(encoding="utf-8") == "brand new engine file\n"
    assert (installed / "tests" / "test_added.py").is_file()
    assert not (installed / "tutor" / "scripts" / "retired.py").exists()
    # the plan after an apply is empty
    assert update.plan(installed, upstream) == []


def test_apply_deletes_a_removed_file_only_inside_engine_paths(installed, make_upstream):
    # upstream has no notes.txt and no prep/: they are not engine paths, so they stay even though upstream lacks them
    engine_only_upstream = make_upstream({"tutor/scripts/common.py": "old common\n"})

    update.apply(installed, engine_only_upstream)

    assert (installed / "notes.txt").is_file()
    assert (installed / "prep" / "profile" / "facts.md").is_file()
    # inside engine paths the missing ones are gone (README.md, CLAUDE.md, tests/ ...)
    assert not (installed / "CLAUDE.md").exists()
    assert not (installed / "tests" / "test_common.py").exists()
    assert not (installed / "tutor" / "scripts" / "retired.py").exists()


def test_apply_prunes_a_directory_that_the_removal_emptied(installed, make_upstream):
    (installed / "tutor" / "old_area").mkdir()
    (installed / "tutor" / "old_area" / "only.py").write_text("x\n", encoding="utf-8")
    commit_everything(installed)

    update.apply(installed, make_upstream({"tutor/scripts/common.py": "old common\n"}))

    assert not (installed / "tutor" / "old_area").exists()
    assert (installed / "tutor" / "scripts").is_dir()


def test_apply_leaves_ignored_byproducts_in_engine_paths_alone(installed, upstream):
    byproduct = installed / "tutor" / "scripts" / "__pycache__" / "common.cpython-312.pyc"
    byproduct.parent.mkdir()
    byproduct.write_bytes(b"compiled")

    assert not any("__pycache__" in path for path in update.plan(installed, upstream))
    update.apply(installed, upstream)

    assert byproduct.read_bytes() == b"compiled"


def test_apply_leaves_files_the_user_has_git_ignore_in_engine_paths_alone(installed, upstream):
    # a local ignore rule (not the committed .gitignore): the user's own scratch file inside an engine folder
    (installed / ".git" / "info" / "exclude").write_text("scratch.tmp\n", encoding="utf-8")
    scratch_file = installed / "tests" / "scratch.tmp"
    scratch_file.write_text("mine\n", encoding="utf-8")

    assert "tests/scratch.tmp" not in update.plan(installed, upstream)
    update.apply(installed, upstream)

    assert scratch_file.read_text(encoding="utf-8") == "mine\n"


@pytest.mark.parametrize(
    "dirty_change",
    [
        pytest.param(("tutor/scripts/common.py", "edited by the user\n"), id="modified-tracked-engine-file"),
        pytest.param(("tests/my_own_test.py", "untracked new test\n"), id="untracked-file-in-engine-path"),
        pytest.param(("CLAUDE.md", "tutor rules the user tweaked\n"), id="modified-engine-file-at-root"),
    ],
)
def test_apply_refuses_uncommitted_engine_changes_and_changes_nothing(installed, upstream, dirty_change):
    relative_path, text = dirty_change
    write_files(installed, {relative_path: text})
    files_before = hash_tree(installed)

    with pytest.raises(update.UpdateError, match="uncommitted"):
        update.apply(installed, upstream)

    assert hash_tree(installed) == files_before


def test_apply_ignores_uncommitted_changes_outside_engine_paths(installed, upstream):
    write_files(installed, {"prep/profile/facts.md": "edited, not committed\n", "notes.txt": "edited\n", "draft.md": "new\n"})

    update.apply(installed, upstream)

    assert (installed / "prep" / "profile" / "facts.md").read_text(encoding="utf-8") == "edited, not committed\n"
    assert (installed / "tutor" / "scripts" / "common.py").read_text(encoding="utf-8") == "new common\n"


def test_apply_does_not_commit(installed, upstream):
    head_before = run_git(installed, "rev-parse", "HEAD")

    update.apply(installed, upstream)

    assert run_git(installed, "rev-parse", "HEAD") == head_before
    assert "tutor/scripts/common.py" in run_git(installed, "status", "--porcelain")


def test_apply_sets_the_hooks_path_again(installed, upstream):
    run_git(installed, "config", "core.hooksPath", "somewhere-else")

    update.apply(installed, upstream)

    assert run_git(installed, "config", "core.hooksPath") == ".githooks"


def test_apply_sets_the_hooks_path_even_when_the_engine_is_current(installed, make_upstream):
    run_git(installed, "config", "core.hooksPath", "somewhere-else")

    assert update.apply(installed, make_upstream(INSTALLED_ENGINE_FILES)) == []

    assert run_git(installed, "config", "core.hooksPath") == ".githooks"


def test_apply_refuses_a_root_that_is_not_a_git_repository(tmp_root, upstream):
    write_files(tmp_root, INSTALLED_FILES)

    with pytest.raises(update.UpdateError, match="git repository"):
        update.apply(tmp_root, upstream)

    assert (tmp_root / "tutor" / "scripts" / "common.py").read_text(encoding="utf-8") == "old common\n"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX execute bit")
def test_apply_keeps_the_execute_bit_of_hook_files(installed, make_upstream):
    hook = make_upstream({".githooks/pre-commit": "#!/bin/sh\nexit 0\n", "tutor/scripts/common.py": "old common\n"})
    (hook / ".githooks" / "pre-commit").chmod(0o755)

    update.apply(installed, hook)

    assert (installed / ".githooks" / "pre-commit").stat().st_mode & stat.S_IXUSR


# ---------- symlinks ----------


def test_symlinks_in_the_root_are_never_followed(installed, upstream, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "precious.txt").write_text("not the engine\n", encoding="utf-8")
    make_symlink(installed / "tests" / "linked", outside)
    commit_everything(installed)

    assert not any("linked" in path for path in update.plan(installed, upstream))
    update.apply(installed, upstream)

    assert (outside / "precious.txt").read_text(encoding="utf-8") == "not the engine\n"
    assert (installed / "tests" / "linked").is_symlink()


def test_apply_refuses_to_write_through_a_symlinked_engine_directory(installed, upstream, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (installed / "tutor" / "scripts" / "common.py").unlink()
    (installed / "tutor" / "scripts" / "retired.py").unlink()
    (installed / "tutor" / "scripts").rmdir()
    (installed / "tutor").rmdir()
    make_symlink(installed / "tutor", outside)
    commit_everything(installed)

    files_before = hash_tree(installed)

    with pytest.raises(update.UpdateError, match="symlink"):
        update.apply(installed, upstream)

    assert list(outside.iterdir()) == []
    # refused up front: not even the files outside the symlink were replaced
    assert hash_tree(installed) == files_before


def test_symlinks_in_the_upstream_are_not_copied(installed, make_upstream, tmp_path_factory):
    secret_outside = tmp_path_factory.mktemp("secret") / "token.txt"
    secret_outside.write_text("do not copy\n", encoding="utf-8")
    plain_upstream = make_upstream({"tutor/scripts/common.py": "old common\n"})
    make_symlink(plain_upstream / "tutor" / "scripts" / "leak.py", secret_outside)

    assert "tutor/scripts/leak.py" not in update.plan(installed, plain_upstream)
    update.apply(installed, plain_upstream)

    assert not (installed / "tutor" / "scripts" / "leak.py").exists()


# ---------- links and ignored files ----------

IGNORE_TEMP_FILES_RULE = ".*.partial\n"


def test_apply_never_follows_a_planted_temp_file_symlink(installed, make_upstream):
    # the temp-file pattern is ignored (as in the shipped .gitignore), so git does not show the planted link
    gitignore_text = INSTALLED_FILES[".gitignore"] + IGNORE_TEMP_FILES_RULE
    write_files(installed, {".gitignore": gitignore_text})
    commit_everything(installed)
    victim = installed / "prep" / "profile" / "facts.md"
    victim_before = victim.read_bytes()
    make_symlink(installed / "tutor" / "scripts" / ".common.py.partial", Path("../../prep/profile/facts.md"))
    upstream = make_upstream({"tutor/scripts/common.py": "new common\n", ".gitignore": gitignore_text})

    update.apply(installed, upstream)

    assert victim.read_bytes() == victim_before
    updated_file = installed / "tutor" / "scripts" / "common.py"
    assert not updated_file.is_symlink()
    assert updated_file.read_text(encoding="utf-8") == "new common\n"


def test_apply_refuses_to_overwrite_a_git_ignored_file(installed, make_upstream):
    (installed / ".git" / "info" / "exclude").write_text("local_notes.txt\n", encoding="utf-8")
    ignored_file = installed / "tests" / "local_notes.txt"
    ignored_file.write_text("my private notes\n", encoding="utf-8")
    upstream_with_same_name = make_upstream({**UPSTREAM_FILES, "tests/local_notes.txt": "upstream version\n"})
    files_before = hash_tree(installed)

    with pytest.raises(update.UpdateError, match="git-ignored") as refusal:
        update.apply(installed, upstream_with_same_name)

    assert "tests/local_notes.txt" in str(refusal.value)
    assert ignored_file.read_text(encoding="utf-8") == "my private notes\n"
    assert hash_tree(installed) == files_before


def test_apply_refuses_an_ignored_file_that_differs_only_in_letter_case(installed, make_upstream):
    # (macOS and Windows file systems treat Local_Notes.txt and local_notes.txt as the same file)
    (installed / ".git" / "info" / "exclude").write_text("Local_Notes.txt\n", encoding="utf-8")
    ignored_file = installed / "tests" / "Local_Notes.txt"
    ignored_file.write_text("my private notes\n", encoding="utf-8")
    upstream_with_other_case = make_upstream({**UPSTREAM_FILES, "tests/local_notes.txt": "upstream version\n"})

    with pytest.raises(update.UpdateError, match="git-ignored") as refusal:
        update.apply(installed, upstream_with_other_case)

    assert "Local_Notes.txt" in str(refusal.value)
    assert ignored_file.read_text(encoding="utf-8") == "my private notes\n"


def test_apply_refuses_when_an_ignored_symlink_sits_where_a_file_would_land(installed, make_upstream, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "target.txt"
    outside.write_text("not the engine\n", encoding="utf-8")
    (installed / ".git" / "info" / "exclude").write_text("planted.py\n", encoding="utf-8")
    make_symlink(installed / "tutor" / "scripts" / "planted.py", outside)
    upstream_with_same_name = make_upstream({**UPSTREAM_FILES, "tutor/scripts/planted.py": "upstream version\n"})

    with pytest.raises(update.UpdateError, match="git-ignored"):
        update.apply(installed, upstream_with_same_name)

    assert outside.read_text(encoding="utf-8") == "not the engine\n"


# ---------- a failure half way ----------


def test_a_failure_half_way_names_the_commands_that_go_back(installed, upstream, monkeypatch):
    real_copy = update.copy_engine_file

    def fail_on_one_file(upstream_dir, root, relative_path):
        if relative_path == "tutor/scripts/common.py":
            raise OSError("disk full")
        real_copy(upstream_dir, root, relative_path)

    monkeypatch.setattr(update, "copy_engine_file", fail_on_one_file)
    files_before = hash_tree(installed)

    with pytest.raises(update.UpdateError) as failure:
        update.apply(installed, upstream)

    message = str(failure.value)
    assert "tutor/scripts/common.py" in message and "disk full" in message
    # (added files are git clean candidates, changed and removed ones are git restore candidates)
    command_lines = [line.strip() for line in message.splitlines() if line.strip().startswith("git ")]
    assert any(line.startswith("git restore --") and "tutor/scripts/retired.py" in line and "CLAUDE.md" in line for line in command_lines)
    assert any(line.startswith("git clean -f --") and "tests/test_added.py" in line and "tutor/scripts/added.py" in line for line in command_lines)
    # the advice works: running it brings the tree back
    for line in command_lines:
        subprocess.run(shlex.split(line), cwd=installed, check=True, capture_output=True)
    assert hash_tree(installed) == files_before


# ---------- uncommitted changes: git status rename entries ----------


def test_parse_porcelain_paths_reads_rename_entries_as_one_change():
    status = b"R  tests/new_name.py\0tests/old_name.py\0 M tutor/scripts/common.py\0?? tests/extra.py\0"

    assert update.parse_porcelain_paths(status) == [
        "tests/new_name.py (renamed from tests/old_name.py)",
        "tutor/scripts/common.py",
        "tests/extra.py",
    ]


def test_apply_names_a_staged_rename_correctly(installed, upstream):
    run_git(installed, "mv", "tests/test_common.py", "tests/test_renamed.py")

    with pytest.raises(update.UpdateError, match="uncommitted") as refusal:
        update.apply(installed, upstream)

    assert "tests/test_renamed.py (renamed from tests/test_common.py)" in str(refusal.value)


# ---------- the upstream directory ----------


def test_an_upstream_directory_without_the_engine_is_refused(installed, tmp_path_factory):
    not_an_engine = tmp_path_factory.mktemp("empty")

    with pytest.raises(update.UpdateError, match="engine"):
        update.plan(installed, not_an_engine)
    with pytest.raises(update.UpdateError, match="not a directory"):
        update.plan(installed, installed / "missing")


def test_a_git_upstream_leaves_out_its_ignored_files(installed, make_upstream):
    repository = make_upstream(as_repository=True)
    (repository / "tutor" / "scripts" / "__pycache__").mkdir()
    (repository / "tutor" / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"x")

    assert not any("__pycache__" in path for path in update.plan(installed, repository))


# ---------- fetching ----------


def test_resolve_upstream_url_prefers_the_upstream_remote(installed):
    assert update.resolve_upstream_url(installed) == update.DEFAULT_UPSTREAM_URL

    run_git(installed, "remote", "add", "origin", "https://example.com/mine/origin.git")
    assert update.resolve_upstream_url(installed) == update.DEFAULT_UPSTREAM_URL

    run_git(installed, "remote", "add", "upstream", "https://example.com/somewhere/engine.git")
    assert update.resolve_upstream_url(installed) == "https://example.com/somewhere/engine.git"


def test_fetch_upstream_clones_a_shallow_copy(installed, make_upstream, tmp_path_factory):
    repository = make_upstream(as_repository=True)
    destination = tmp_path_factory.mktemp("fetched") / "checkout"

    update.fetch_upstream(repository.as_uri(), destination)

    assert (destination / "tutor" / "scripts" / "common.py").read_text(encoding="utf-8") == "new common\n"
    assert update.plan(installed, destination) == update.plan(installed, repository)


def test_fetch_upstream_reports_a_clone_that_fails(tmp_path_factory):
    destination = tmp_path_factory.mktemp("fetched") / "checkout"

    with pytest.raises(update.UpdateError, match="clone"):
        update.fetch_upstream((destination.parent / "no-such-repository").as_uri(), destination)


# ---------- command line ----------


def test_cli_plan_prints_the_three_groups_and_changes_nothing(installed, upstream, capsys):
    files_before = hash_tree(installed)

    exit_code = update.main(["plan", "--source", str(upstream)])

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert "added" in printed and "changed" in printed and "removed" in printed
    assert "tutor/scripts/added.py" in printed and "tutor/scripts/retired.py" in printed
    assert "prep/profile" not in printed and "upstream-only" not in printed
    assert hash_tree(installed) == files_before


def test_cli_plan_says_so_when_nothing_changes(installed, make_upstream, capsys):
    exit_code = update.main(["plan", "--source", str(make_upstream(INSTALLED_ENGINE_FILES))])

    assert exit_code == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_apply_requires_yes(installed, upstream, capsys):
    files_before = hash_tree(installed)

    exit_code = update.main(["apply", "--source", str(upstream)])

    assert exit_code == 1
    assert "--yes" in capsys.readouterr().err
    assert hash_tree(installed) == files_before


def test_cli_warns_when_gitignore_changes(installed, make_upstream, capsys):
    upstream_with_new_ignore = make_upstream({**UPSTREAM_FILES, ".gitignore": INSTALLED_FILES[".gitignore"] + "*.log\n"})

    update.main(["plan", "--source", str(upstream_with_new_ignore)])
    assert "review .gitignore: it protects .env, local/ and secret/" in capsys.readouterr().out

    update.main(["apply", "--source", str(upstream_with_new_ignore), "--yes"])
    assert "review .gitignore: it protects .env, local/ and secret/" in capsys.readouterr().out


def test_cli_stays_quiet_about_gitignore_when_it_is_unchanged(installed, upstream, capsys):
    update.main(["apply", "--source", str(upstream), "--yes"])

    assert ".gitignore" not in capsys.readouterr().out


def test_cli_apply_with_yes_lists_the_files_and_asks_for_a_review(installed, upstream, capsys):
    exit_code = update.main(["apply", "--source", str(upstream), "--yes"])

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert "tutor/scripts/common.py" in printed
    assert "commit" in printed
    assert (installed / "tutor" / "scripts" / "common.py").read_text(encoding="utf-8") == "new common\n"


def test_cli_apply_reports_a_dirty_engine_on_stderr(installed, upstream, capsys):
    write_files(installed, {"CLAUDE.md": "edited\n"})

    exit_code = update.main(["apply", "--source", str(upstream), "--yes"])

    assert exit_code == 1
    assert "uncommitted" in capsys.readouterr().err


def test_cli_refuses_a_bad_source_directory(installed, tmp_path, capsys):
    exit_code = update.main(["plan", "--source", str(tmp_path / "missing")])

    assert exit_code == 1
    assert "not a directory" in capsys.readouterr().err


def test_cli_plan_without_source_fetches_the_upstream_remote(installed, make_upstream, capsys):
    repository = make_upstream(as_repository=True)
    run_git(installed, "remote", "add", "upstream", repository.as_uri())

    exit_code = update.main(["plan"])

    assert exit_code == 0
    assert "tutor/scripts/added.py" in capsys.readouterr().out
