"""Tests for init.py: temp dirs as repo roots, temp git repos (see conftest.py), openssl and visibility faked"""

import json
import os
import re
import stat
import subprocess
import sys
from datetime import date

import pytest

import init
import prep_settings
import remote_guard
import review
from repo_helpers import TEMPLATE_HTTPS_URL, USER_REMOTE_URL, commit_all_staged, run_git, url_with_credentials

KEY_LINE_PATTERN = re.compile(r"^SPARRING_ENCRYPTION_KEY=(\S+)$", re.MULTILINE)


@pytest.fixture
def fake_openssl(monkeypatch):
    """Key generation needs openssl to exist, not to run"""
    monkeypatch.setattr(init, "find_openssl", lambda: "/usr/bin/openssl")


def setup_arguments(storage, *extra):
    return ["setup", "--storage", storage, *extra]


# ---------- setup: prep from template ----------


def test_setup_creates_prep_from_template(git_root):
    assert init.main(setup_arguments("private")) == 0

    prep = git_root / "prep"
    for relative in (
        "status.md",
        "profile/facts.md",
        "profile/coaching.md",
        "profile/coaching-log.md",
        "profile/transcription.md",
        "profile/cards.md",
        "profile/experiences/.gitkeep",
        "explore/candidates.md",
        "explore/contacts.md",
        "interviews/.gitkeep",
    ):
        assert (prep / relative).is_file(), relative
    settings = json.loads((prep / "profile" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {
        "storage": "private",
        "language": "en",
        "input": "typing",
        "created": date.today().isoformat(),
    }


def test_setup_never_overwrites_existing_prep_files(git_root):
    init.main(setup_arguments("private"))
    facts = git_root / "prep" / "profile" / "facts.md"
    facts.write_text("my own facts\n", encoding="utf-8")

    assert init.main(setup_arguments("private")) == 0

    assert facts.read_text(encoding="utf-8") == "my own facts\n"


def test_setup_rerun_updates_settings_and_keeps_created_date(git_root):
    init.main(setup_arguments("private", "--language", "en"))
    settings_file = prep_settings.settings_path(git_root)
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    settings["created"] = "2026-01-02"
    settings_file.write_text(json.dumps(settings), encoding="utf-8")

    init.main(setup_arguments("local", "--language", "ko", "--input", "voice"))

    updated = json.loads(settings_file.read_text(encoding="utf-8"))
    assert updated == {"storage": "local", "language": "ko", "input": "voice", "created": "2026-01-02"}


def test_setup_rejects_language_that_is_not_a_code(git_root, capsys):
    assert init.main(setup_arguments("private", "--language", "korean")) == init.EXIT_INVALID_INPUT
    assert "language" in capsys.readouterr().err
    assert not (git_root / "prep").exists()


def test_template_cards_file_matches_what_review_writes(git_root, tmp_path_factory, monkeypatch):
    # one source for the card layout: review.py; a drifted template would break the first load
    other_root = tmp_path_factory.mktemp("review_root")
    monkeypatch.setenv("SPARRING_ROOT", str(other_root))
    review.save([])
    expected = review.cards_path().read_text(encoding="utf-8")
    template_cards = init.TEMPLATE_PREP_DIR / "profile" / "cards.md"
    assert template_cards.read_text(encoding="utf-8") == expected


def test_template_facts_table_header_and_status_values():
    lines = (init.TEMPLATE_PREP_DIR / "profile" / "facts.md").read_text(encoding="utf-8").splitlines()
    assert "| Fact | Status | Source |" in lines
    # the allowed status values are listed once, in the one-line description above the table
    description = next(line for line in lines if "confirmed" in line)
    for status_value in ("confirmed", "unconfirmed", "do-not-say", "confidential"):
        assert status_value in description


def test_template_files_hold_no_key_file_names():
    # the privacy hook blocks .env and .env.* files, so no template may use such a name
    names = [path.name for path in init.TEMPLATE_PREP_DIR.rglob("*") if path.is_file()]
    assert not [name for name in names if name == ".env" or name.startswith(".env.")]


# ---------- setup: storage local ----------


def test_setup_local_writes_prep_gitignore(git_root):
    assert init.main(setup_arguments("local")) == 0

    ignore_file = git_root / "prep" / ".gitignore"
    assert ignore_file.read_text(encoding="utf-8").splitlines() == ["*", "!.gitignore"]
    # prep content never reaches git status (only the ignore file itself is visible)
    status = run_git(git_root, "status", "--porcelain", "--untracked-files=all")
    assert "prep/profile" not in status
    assert "prep/.gitignore" in status


def test_setup_local_keeps_an_existing_different_prep_gitignore(git_root, capsys):
    (git_root / "prep").mkdir()
    ignore_file = git_root / "prep" / ".gitignore"
    ignore_file.write_text("my-rule\n", encoding="utf-8")

    init.main(setup_arguments("local"))

    assert ignore_file.read_text(encoding="utf-8") == "my-rule\n"
    assert "prep/.gitignore" in capsys.readouterr().out


def test_setup_local_treats_an_undecodable_prep_gitignore_as_custom(git_root, capsys):
    (git_root / "prep").mkdir()
    ignore_file = git_root / "prep" / ".gitignore"
    ignore_file.write_bytes(b"\xff\xfe\x00bad")

    assert init.main(setup_arguments("local")) == 0

    assert ignore_file.read_bytes() == b"\xff\xfe\x00bad"
    assert "prep/.gitignore" in capsys.readouterr().out


def test_setup_private_after_local_removes_the_generated_ignore_rule(git_root, capsys):
    init.main(setup_arguments("local"))
    capsys.readouterr()

    assert init.main(setup_arguments("private")) == 0

    assert not (git_root / "prep" / ".gitignore").exists()
    assert "removed prep/.gitignore" in capsys.readouterr().out
    # prep/ is now visible to git again
    assert "prep/status.md" in run_git(git_root, "status", "--porcelain", "--untracked-files=all")


def test_setup_private_after_local_keeps_a_customised_ignore_file_and_warns(git_root, capsys):
    init.main(setup_arguments("local"))
    ignore_file = git_root / "prep" / ".gitignore"
    ignore_file.write_text("*\n!.gitignore\nextra\n", encoding="utf-8")
    capsys.readouterr()

    init.main(setup_arguments("private"))

    assert ignore_file.read_text(encoding="utf-8") == "*\n!.gitignore\nextra\n"
    assert "left as it is" in capsys.readouterr().out


def test_setup_private_keeps_an_unrelated_prep_gitignore_and_says_so(git_root, capsys):
    (git_root / "prep").mkdir()
    ignore_file = git_root / "prep" / ".gitignore"
    ignore_file.write_text("*.tmp\n", encoding="utf-8")

    init.main(setup_arguments("private"))

    assert ignore_file.read_text(encoding="utf-8") == "*.tmp\n"
    assert "not the generated local rule" in capsys.readouterr().out


def track_prep_status_file(root):
    init.main(setup_arguments("private"))
    run_git(root, "add", "prep/status.md")
    commit_all_staged(root)


def test_setup_local_refuses_while_prep_files_are_tracked(git_root, capsys):
    track_prep_status_file(git_root)
    capsys.readouterr()

    assert init.main(setup_arguments("local")) == init.EXIT_INVALID_INPUT

    error = capsys.readouterr().err
    assert "git rm -r --cached prep" in error and "--untrack-prep" in error
    # nothing changed: still private, no ignore rule written, the file is still tracked
    assert prep_settings.read_settings(git_root)["storage"] == "private"
    assert not (git_root / "prep" / ".gitignore").exists()
    assert run_git(git_root, "ls-files", "prep") == "prep/status.md"


def test_setup_local_untrack_prep_removes_the_files_from_git_but_keeps_them(git_root, capsys):
    track_prep_status_file(git_root)
    capsys.readouterr()

    assert init.main(setup_arguments("local", "--untrack-prep")) == 0

    assert run_git(git_root, "ls-files", "prep") == ""
    assert (git_root / "prep" / "status.md").is_file()
    assert "untracked" in capsys.readouterr().out
    # the removal is staged, so a commit would delete them from the repository
    assert "D  prep/status.md" in run_git(git_root, "status", "--porcelain")


def test_setup_untrack_prep_is_ignored_outside_local_storage(git_root, capsys):
    track_prep_status_file(git_root)
    capsys.readouterr()

    assert init.main(setup_arguments("private", "--untrack-prep")) == 0

    assert run_git(git_root, "ls-files", "prep") == "prep/status.md"
    assert "--untrack-prep" in capsys.readouterr().out


def test_setup_local_allows_a_tracked_prep_gitignore_alone(git_root):
    init.main(setup_arguments("local"))
    run_git(git_root, "add", "-f", "prep/.gitignore")
    commit_all_staged(git_root)

    assert init.main(setup_arguments("local")) == 0


# ---------- setup: encryption key ----------


def read_key(root):
    match = KEY_LINE_PATTERN.search((root / ".env").read_text(encoding="utf-8"))
    return match.group(1) if match else None


def test_setup_public_encrypted_creates_key_once(git_root, fake_openssl):
    assert init.main(setup_arguments("public-encrypted")) == 0
    first_key = read_key(git_root)
    assert first_key and len(first_key) >= 40

    assert init.main(setup_arguments("public-encrypted")) == 0
    assert read_key(git_root) == first_key
    assert (git_root / ".env").read_text(encoding="utf-8").count("SPARRING_ENCRYPTION_KEY") == 1


def test_setup_never_prints_the_key(git_root, fake_openssl, capsys):
    init.main(setup_arguments("public-encrypted"))
    captured = capsys.readouterr()
    assert read_key(git_root) not in captured.out + captured.err


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_env_file_is_owner_only(git_root, fake_openssl):
    init.main(setup_arguments("public-encrypted"))
    assert stat.S_IMODE((git_root / ".env").stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_existing_env_file_is_tightened_and_other_lines_survive(git_root, fake_openssl):
    env_file = git_root / ".env"
    env_file.write_text("OTHER=1", encoding="utf-8")  # no trailing newline on purpose
    env_file.chmod(0o644)

    init.main(setup_arguments("public-encrypted"))

    text = env_file.read_text(encoding="utf-8")
    assert text.startswith("OTHER=1\nSPARRING_ENCRYPTION_KEY=")
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_setup_keeps_a_key_that_comes_from_the_environment(git_root, fake_openssl, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", "from-the-shell")
    init.main(setup_arguments("public-encrypted"))
    assert not (git_root / ".env").exists()


def test_setup_private_has_no_key_unless_asked(git_root, fake_openssl):
    init.main(setup_arguments("private"))
    assert not (git_root / ".env").exists()

    init.main(setup_arguments("private", "--encrypt-secrets"))
    assert read_key(git_root)


def test_setup_local_ignores_encrypt_secrets(git_root, fake_openssl, capsys):
    init.main(setup_arguments("local", "--encrypt-secrets"))
    assert not (git_root / ".env").exists()
    assert "--encrypt-secrets" in capsys.readouterr().out


def test_setup_public_encrypted_without_openssl_is_refused(git_root, monkeypatch, capsys):
    monkeypatch.setattr(init, "find_openssl", lambda: None)

    assert init.main(setup_arguments("public-encrypted")) == init.EXIT_PREREQUISITE_MISSING

    assert "openssl" in capsys.readouterr().err
    assert not (git_root / "prep").exists()
    assert not (git_root / ".env").exists()


# ---------- setup: hooks ----------


def test_setup_sets_hooks_path(git_root):
    init.main(setup_arguments("private"))
    assert run_git(git_root, "config", "--get", "core.hooksPath") == ".githooks"


def test_setup_outside_a_git_repo_still_creates_prep(tmp_root, capsys):
    assert init.main(setup_arguments("private")) == 0
    assert (tmp_root / "prep" / "profile" / "settings.json").is_file()
    assert "not a git repository" in capsys.readouterr().out


def test_setup_does_not_touch_the_hooks_of_an_enclosing_repo(tmp_root, monkeypatch):
    # the root has no .git of its own, its parent does: the parent's config must stay as it was
    outer = tmp_root / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(outer)], check=True)
    monkeypatch.setenv("SPARRING_ROOT", str(inner))

    init.main(setup_arguments("private"))

    assert run_git(outer, "config", "--get", "core.hooksPath") == ""


# ---------- setup: remotes ----------


@pytest.fixture
def private_remote(monkeypatch):
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")


@pytest.mark.parametrize(
    "template_url",
    [TEMPLATE_HTTPS_URL, "git@github.com:Cassiiopeia/interview-sparring.git"],
)
def test_init_renames_template_origin(git_root, private_remote, template_url):
    run_git(git_root, "remote", "add", "origin", template_url)
    # the rename carries branch tracking over: a bare `git push` would then target the template
    run_git(git_root, "config", "branch.main.remote", "origin")
    run_git(git_root, "config", "branch.main.merge", "refs/heads/main")

    assert init.main(setup_arguments("private", "--remote", USER_REMOTE_URL)) == 0

    assert run_git(git_root, "remote", "get-url", "upstream") == template_url
    assert run_git(git_root, "remote", "get-url", "--push", "upstream") == "no_push"
    assert run_git(git_root, "remote", "get-url", "origin") == USER_REMOTE_URL
    assert run_git(git_root, "config", "--get", "branch.main.remote") == ""
    assert run_git(git_root, "config", "--get", "branch.main.merge") == ""


def test_setup_renames_template_origin_even_without_a_remote(git_root, capsys):
    run_git(git_root, "remote", "add", "origin", TEMPLATE_HTTPS_URL)

    assert init.main(setup_arguments("private")) == 0

    assert run_git(git_root, "remote").split() == ["upstream"]
    assert "--remote" in capsys.readouterr().out


def test_setup_drops_template_origin_when_upstream_already_exists(git_root, private_remote):
    run_git(git_root, "remote", "add", "origin", TEMPLATE_HTTPS_URL)
    run_git(git_root, "remote", "add", "upstream", TEMPLATE_HTTPS_URL)

    assert init.main(setup_arguments("private", "--remote", USER_REMOTE_URL)) == 0

    assert run_git(git_root, "remote", "get-url", "origin") == USER_REMOTE_URL
    assert run_git(git_root, "remote", "get-url", "upstream") == TEMPLATE_HTTPS_URL
    assert run_git(git_root, "remote", "get-url", "--push", "upstream") == "no_push"


def test_setup_replaces_a_different_existing_origin(git_root, private_remote):
    run_git(git_root, "remote", "add", "origin", "https://github.com/someone/old.git")
    init.main(setup_arguments("private", "--remote", USER_REMOTE_URL))
    assert run_git(git_root, "remote", "get-url", "origin") == USER_REMOTE_URL
    assert "upstream" not in run_git(git_root, "remote").split()


def test_setup_disables_push_to_any_remote_that_points_at_the_template(git_root, private_remote):
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    run_git(git_root, "remote", "add", "engine", "git@github.com:Cassiiopeia/interview-sparring.git")

    assert init.main(setup_arguments("private")) == 0

    assert run_git(git_root, "remote", "get-url", "--push", "engine") == "no_push"
    assert run_git(git_root, "remote", "get-url", "--push", "origin") == USER_REMOTE_URL


def test_setup_disables_a_template_push_url_even_when_only_the_push_side_points_there(git_root, private_remote):
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    run_git(git_root, "remote", "set-url", "--push", "origin", TEMPLATE_HTTPS_URL)

    init.main(setup_arguments("private"))

    assert run_git(git_root, "remote", "get-url", "--push", "origin") == "no_push"


def test_setup_warns_about_a_template_lookalike_remote(git_root, capsys):
    assert init.main(setup_arguments("private", "--remote", "https://gitlab.com/someone/interview-sparring.git")) == 0
    assert "refused" in capsys.readouterr().out


def test_setup_refuses_the_template_as_remote(git_root, capsys):
    assert init.main(setup_arguments("private", "--remote", TEMPLATE_HTTPS_URL + ".git")) == init.EXIT_INVALID_INPUT
    assert "template" in capsys.readouterr().err
    assert not (git_root / "prep").exists()


def test_setup_refuses_remote_that_looks_like_a_git_option(git_root, capsys):
    assert init.main(setup_arguments("private", "--remote=--upload-pack=evil")) == init.EXIT_INVALID_INPUT


def test_setup_refuses_public_remote_in_private_mode(git_root, monkeypatch, capsys):
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    assert init.main(setup_arguments("private", "--remote", USER_REMOTE_URL)) == init.EXIT_INVALID_INPUT

    assert "public" in capsys.readouterr().err
    assert not (git_root / "prep").exists()
    assert run_git(git_root, "remote") == ""


def test_setup_allows_public_remote_in_public_encrypted_mode(git_root, fake_openssl, monkeypatch):
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")
    assert init.main(setup_arguments("public-encrypted", "--remote", USER_REMOTE_URL)) == 0
    assert run_git(git_root, "remote", "get-url", "origin") == USER_REMOTE_URL


# ---------- confirm-remote ----------


def test_confirm_remote_records_the_current_origin_without_credentials(git_root, monkeypatch):
    init.main(setup_arguments("private"))
    run_git(git_root, "remote", "add", "origin", url_with_credentials("gitlab.com/someone/my-prep.git"))

    assert init.main(["confirm-remote"]) == 0

    settings = prep_settings.read_settings(git_root)
    assert settings["confirmed_private_remote"] == "https://gitlab.com/someone/my-prep.git"
    assert settings["storage"] == "private"


def test_confirm_remote_makes_can_push_pass_for_an_unverifiable_origin(git_root):
    init.main(setup_arguments("private"))
    run_git(git_root, "remote", "add", "origin", "https://gitlab.com/someone/my-prep.git")
    assert remote_guard.can_push(git_root)[0] is False

    init.main(["confirm-remote"])

    assert remote_guard.can_push(git_root)[0] is True


def test_setup_never_confirms_a_remote_by_itself(git_root):
    init.main(setup_arguments("private", "--remote", "https://gitlab.com/someone/my-prep.git"))
    assert "confirmed_private_remote" not in prep_settings.read_settings(git_root)


def test_setup_keeps_an_earlier_confirmation_but_a_new_origin_invalidates_it(git_root):
    init.main(setup_arguments("private", "--remote", "https://gitlab.com/someone/my-prep.git"))
    init.main(["confirm-remote"])

    init.main(setup_arguments("private", "--remote", "https://gitlab.com/someone/other.git"))

    assert prep_settings.read_settings(git_root)["confirmed_private_remote"] == "https://gitlab.com/someone/my-prep.git"
    assert remote_guard.can_push(git_root)[0] is False


@pytest.mark.parametrize(
    "origin, problem",
    [
        (None, "origin"),
        (TEMPLATE_HTTPS_URL, "template"),
        ("https://gitlab.com/someone/interview-sparring.git", "template"),
    ],
)
def test_confirm_remote_refuses_what_can_never_be_private(git_root, capsys, origin, problem):
    init.main(setup_arguments("private"))
    if origin:
        run_git(git_root, "remote", "add", "origin", origin)
    capsys.readouterr()

    assert init.main(["confirm-remote"]) == init.EXIT_INVALID_INPUT

    assert problem in capsys.readouterr().err
    assert "confirmed_private_remote" not in prep_settings.read_settings(git_root)


@pytest.mark.parametrize("answer", ["unknown", "public", "private_or_missing"])
def test_confirm_remote_refuses_any_github_remote(git_root, monkeypatch, capsys, answer):
    init.main(setup_arguments("private"))
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: answer)
    capsys.readouterr()

    assert init.main(["confirm-remote"]) == init.EXIT_INVALID_INPUT

    assert "GitHub remotes are checked automatically; make the repo private" in capsys.readouterr().err
    assert "confirmed_private_remote" not in prep_settings.read_settings(git_root)


@pytest.mark.parametrize(
    "origin",
    [
        "ssh://git@ssh.github.com:443/someone/my-prep.git",
        "git://github.com/someone/my-prep.git",
        "git+ssh://git@github.com/someone/my-prep.git",
        "github.com/someone/my-prep",
        "https://github.com/someone",
        "https://github.com./someone/my-prep",
        "HTTPS://API.GITHUB.COM/someone/my-prep",
        "https://github.com:443/someone/my-prep.git",
        "ftp://github.com/someone/my-prep",
    ],
)
def test_confirm_remote_refuses_every_form_of_a_github_host(git_root, monkeypatch, capsys, origin):
    init.main(setup_arguments("private"))
    run_git(git_root, "remote", "add", "origin", origin)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")
    capsys.readouterr()

    assert init.main(["confirm-remote"]) == init.EXIT_INVALID_INPUT

    assert "GitHub remotes are checked automatically; make the repo private" in capsys.readouterr().err
    assert "confirmed_private_remote" not in prep_settings.read_settings(git_root)


def test_confirm_remote_needs_setup_first(git_root, capsys):
    assert init.main(["confirm-remote"]) == init.EXIT_INVALID_INPUT
    assert "setup" in capsys.readouterr().err


# ---------- status ----------


def read_status(capsys):
    assert init.main(["status"]) == 0
    return json.loads(capsys.readouterr().out)


def test_status_before_setup(git_root, capsys):
    report = read_status(capsys)

    assert report["storage"] is None
    assert report["hooks"] is False
    assert report["origin"] is None
    assert report["origin_is_template"] is False
    assert report["has_key"] is False
    assert report["ready"] == []
    assert report["missing"] == ["setup has not run yet"]


def test_status_after_setup_lists_what_the_conversation_must_fill(git_root, capsys):
    init.main(setup_arguments("private", "--language", "ko", "--input", "voice"))
    capsys.readouterr()

    report = read_status(capsys)

    assert report["storage"] == "private"
    assert report["language"] == "ko"
    assert report["input"] == "voice"
    assert report["hooks"] is True
    assert report["missing"] == [
        "profile/facts.md is empty",
        "no experience card yet",
        "no interview folder yet",
    ]
    assert "privacy hook is active" in report["ready"]


def test_status_notices_filled_facts_experiences_and_interviews(git_root, capsys):
    init.main(setup_arguments("private"))
    prep = git_root / "prep"
    with (prep / "profile" / "facts.md").open("a", encoding="utf-8") as facts:
        facts.write("| Led the migration | confirmed | resume |\n")
    (prep / "profile" / "experiences" / "migration.md").write_text("# Migration\n", encoding="utf-8")
    (prep / "interviews" / "2026-11-acme-backend").mkdir()
    capsys.readouterr()

    report = read_status(capsys)

    assert report["missing"] == []


def test_status_reports_remote_and_key(git_root, fake_openssl, private_remote, capsys):
    run_git(git_root, "remote", "add", "origin", TEMPLATE_HTTPS_URL)
    assert read_status(capsys)["origin_is_template"] is True

    init.main(setup_arguments("public-encrypted", "--remote", url_with_credentials("github.com/someone/my-prep.git")))
    capsys.readouterr()
    report = read_status(capsys)

    assert report["has_key"] is True
    assert report["origin"] == "https://github.com/someone/my-prep.git"  # credentials never echoed
    assert report["origin_is_template"] is False
    assert report["openssl"] == "/usr/bin/openssl"
    assert "remote origin is set" in report["ready"]
    assert read_key(git_root) not in json.dumps(report)


def test_status_reports_a_corrupted_settings_file_as_an_error(git_root, capsys):
    settings_file = prep_settings.settings_path(git_root)
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text("{not json", encoding="utf-8")

    assert init.main(["status"]) == init.EXIT_INVALID_INPUT

    assert "settings.json" in capsys.readouterr().err
