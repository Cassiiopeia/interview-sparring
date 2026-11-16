"""Tests for remote_guard.py: URL forms, visibility mapping, the push gate and its CLI (temp git repos, no network)"""

import io
import urllib.error

import pytest

import init
import remote_guard
from repo_helpers import (
    TEMPLATE_HTTPS_URL,
    USER_REMOTE_URL,
    commit_all_staged,
    run_git,
    url_with_credentials,
    write_local_rule,
    write_storage,
)


GITLAB_URL = "https://gitlab.com/someone/my-prep.git"
# built into URLs at run time, so no source line looks like an email address to privacy_check
AT_SIGN = "@"


# ---------- URL forms ----------


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Cassiiopeia/interview-sparring",
        "https://github.com/Cassiiopeia/interview-sparring.git",
        "https://github.com/cassiiopeia/Interview-Sparring/",
        "http://www.github.com/Cassiiopeia/interview-sparring.git",
        url_with_credentials("github.com/Cassiiopeia/interview-sparring.git"),
        "git@github.com:Cassiiopeia/interview-sparring.git",
        "git@github.com:cassiiopeia/interview-sparring",
        "ssh://git@github.com/Cassiiopeia/interview-sparring.git",
        "  https://github.com/Cassiiopeia/interview-sparring.git\n",
    ],
)
def test_is_template_origin_matches_every_form(url):
    assert remote_guard.is_template_origin(url) is True


# every way git and GitHub write the same repository (owner someone, repository my-prep)
GITHUB_FORMS_OF_SOMEONE_MY_PREP = [
    "https://github.com/someone/my-prep",
    "https://github.com/someone/my-prep.git",
    "https://github.com/someone/my-prep/",
    "http://www.github.com/someone/my-prep.git",
    "https://github.com:443/someone/my-prep.git",
    url_with_credentials("github.com/someone/my-prep.git"),
    "ssh://git@github.com/someone/my-prep.git",
    "ssh://git@github.com:22/someone/my-prep.git",
    "ssh://git@ssh.github.com:443/someone/my-prep.git",
    "ssh://ssh.github.com:443/someone/my-prep",
    "git://github.com/someone/my-prep.git",
    "git+ssh://git@github.com/someone/my-prep.git",
    "git@github.com:someone/my-prep.git",
    "git@github.com:someone/my-prep",
    "git@ssh.github.com:someone/my-prep.git",
    "github.com/someone/my-prep",
    "github.com/someone/my-prep.git",
    "www.github.com/someone/my-prep",
    "  https://github.com/someone/my-prep.git\n",
]

# not GitHub, although the text mentions github.com
NOT_GITHUB_URLS = [
    "",
    "https://gitlab.com/someone/my-prep.git",
    "https://github.com.evil.com/someone/my-prep",
    "https://evil.com/github.com/someone/my-prep",
    f"https://github.com{AT_SIGN}evil.com/someone/my-prep",
    "git@gitlab.com:someone/github.com",
    "/home/me/github.com/someone/my-prep",
]


@pytest.mark.parametrize("url", GITHUB_FORMS_OF_SOMEONE_MY_PREP)
def test_parse_github_repository_reads_every_form(url):
    assert remote_guard.parse_github_repository(url) == ("someone", "my-prep")


@pytest.mark.parametrize("url", GITHUB_FORMS_OF_SOMEONE_MY_PREP)
def test_template_forms_are_found_in_every_form_too(url):
    template_url = url.replace("someone/my-prep", "Cassiiopeia/interview-sparring")
    assert remote_guard.is_template_origin(template_url) is True


def test_parse_github_repository_keeps_the_letter_case_of_owner_and_repository():
    assert remote_guard.parse_github_repository("GITHUB.COM/Someone/My-Prep") == ("Someone", "My-Prep")


@pytest.mark.parametrize("url", NOT_GITHUB_URLS + ["https://github.com/someone", "ftp://github.com/someone/my-prep"])
def test_parse_github_repository_returns_none_for_everything_else(url):
    assert remote_guard.parse_github_repository(url) is None


@pytest.mark.parametrize(
    "url",
    GITHUB_FORMS_OF_SOMEONE_MY_PREP
    + [
        # (hosts GitHub runs, with or without a repository path)
        "https://github.com/someone",
        "https://github.com./someone/my-prep",
        "HTTPS://API.GITHUB.COM/repos/someone/my-prep",
        f"https://evil{AT_SIGN}github.com/someone/my-prep",
        "ftp://github.com/someone/my-prep",
        "git@github.com:someone",
        f"https://user:to{AT_SIGN}ken{AT_SIGN}github.com/someone/my-prep",
        # (a host that merely ends with github.com is not told apart: it counts as GitHub)
        "https://mygithub.com/someone/my-prep",
    ],
)
def test_is_github_host_is_true_for_any_url_on_a_github_host(url):
    assert remote_guard.is_github_host(url) is True


@pytest.mark.parametrize("url", NOT_GITHUB_URLS)
def test_is_github_host_is_false_for_other_hosts(url):
    assert remote_guard.is_github_host(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://github.com/someone/interview-sparring",
        "https://github.com/Cassiiopeia/interview-sparring-fork",
        "https://github.com/Cassiiopeia/other",
        "https://gitlab.com/Cassiiopeia/interview-sparring",
        "https://github.com/evil/github.com/Cassiiopeia/interview-sparring",
        "/home/me/interview-sparring",
    ],
)
def test_is_template_origin_rejects_everything_else(url):
    assert remote_guard.is_template_origin(url) is False


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exception_info):
        return False


def install_fake_urlopen(monkeypatch, status, requests=None):
    """status int: returned as a response / Exception instance: raised; requests collects (request, timeout)"""

    def fake_urlopen(request, timeout=None):
        if requests is not None:
            requests.append((request, timeout))
        if isinstance(status, Exception):
            raise status
        return FakeResponse(status)

    monkeypatch.setattr(remote_guard.urllib.request, "urlopen", fake_urlopen)


def http_error(code):
    return urllib.error.HTTPError("https://api.github.com/x", code, "x", {}, io.BytesIO())


def test_visibility_maps_status_codes(monkeypatch):
    url = "https://github.com/someone/my-prep"
    install_fake_urlopen(monkeypatch, 200)
    assert remote_guard.visibility(url) == "public"
    install_fake_urlopen(monkeypatch, http_error(404))
    assert remote_guard.visibility(url) == "private_or_missing"
    install_fake_urlopen(monkeypatch, http_error(500))
    assert remote_guard.visibility(url) == "unknown"
    install_fake_urlopen(monkeypatch, http_error(403))  # rate limited
    assert remote_guard.visibility(url) == "unknown"
    install_fake_urlopen(monkeypatch, 500)
    assert remote_guard.visibility(url) == "unknown"


def test_visibility_is_unknown_when_the_network_fails(monkeypatch):
    url = "git@github.com:someone/my-prep.git"
    install_fake_urlopen(monkeypatch, urllib.error.URLError("offline"))
    assert remote_guard.visibility(url) == "unknown"
    install_fake_urlopen(monkeypatch, TimeoutError())
    assert remote_guard.visibility(url) == "unknown"


def test_visibility_sends_only_a_plain_anonymous_request(monkeypatch):
    requests = []
    install_fake_urlopen(monkeypatch, 200, requests)

    remote_guard.visibility("git@github.com:someone/my-prep.git")

    ((request, timeout),) = requests
    assert request.full_url == "https://api.github.com/repos/someone/my-prep"
    assert timeout == 5
    assert request.get_header("User-agent") == "interview-sparring"
    assert not request.has_header("Authorization")
    assert request.data is None


def test_visibility_of_a_non_github_remote_makes_no_request(monkeypatch):
    requests = []
    install_fake_urlopen(monkeypatch, 200, requests)
    assert remote_guard.visibility("https://gitlab.com/someone/my-prep.git") == "unknown"
    assert remote_guard.visibility("/srv/git/my-prep.git") == "unknown"
    assert requests == []


# ---------- template look-alikes ----------


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/someone/interview-sparring.git",
        "git@gitlab.com:someone/interview-sparring.git",
        "ssh://git@git.example.org:2222/team/Interview-Sparring/",
        "/srv/git/interview-sparring.git",
        "../interview-sparring",
    ],
)
def test_is_template_lookalike_matches_a_copy_on_another_host(url):
    assert remote_guard.is_template_lookalike(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://gitlab.com/someone/my-prep.git",
        "https://gitlab.com/someone/interview-sparring-notes.git",
        # github.com repositories are judged by owner and name (is_template_origin), not by name alone
        "https://github.com/someone/interview-sparring",
        TEMPLATE_HTTPS_URL,
    ],
)
def test_is_template_lookalike_ignores_everything_else(url):
    assert remote_guard.is_template_lookalike(url) is False


# ---------- can_push ----------


def test_can_push_refuses_public_when_private_mode(git_root, monkeypatch):
    write_storage(git_root, "private")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "public" in reason


def test_can_push_allows_private_remote_in_private_mode(git_root, monkeypatch):
    write_storage(git_root, "private")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")

    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_refuses_unverifiable_remote_in_private_mode(git_root, monkeypatch):
    write_storage(git_root, "private")
    run_git(git_root, "remote", "add", "origin", "https://gitlab.com/someone/my-prep.git")
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "confirm-remote" in reason


@pytest.mark.parametrize("storage", ["private", "local", "public-encrypted"])
def test_can_push_never_pushes_to_the_template(git_root, monkeypatch, storage):
    write_storage(git_root, storage)
    run_git(git_root, "remote", "add", "origin", TEMPLATE_HTTPS_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "template" in reason


def test_can_push_public_encrypted_allows_a_public_remote(git_root, monkeypatch):
    write_storage(git_root, "public-encrypted")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_refuses_without_settings_or_origin(git_root):
    assert remote_guard.can_push(git_root)[0] is False
    write_storage(git_root, "private")
    allowed, reason = remote_guard.can_push(git_root)
    assert allowed is False
    assert "origin" in reason


def test_can_push_refuses_an_unknown_storage_mode(git_root):
    write_storage(git_root, "dropbox")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    assert remote_guard.can_push(git_root)[0] is False


def test_can_push_checks_the_target_url_not_only_origin(git_root, monkeypatch):
    write_storage(git_root, "private")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    visibility_by_url = {USER_REMOTE_URL: "private_or_missing", "https://github.com/someone/open.git": "public"}
    monkeypatch.setattr(remote_guard, "visibility", lambda url: visibility_by_url[url])

    assert remote_guard.can_push(git_root)[0] is True
    assert remote_guard.can_push(git_root, "https://github.com/someone/open.git")[0] is False


# ---------- can_push: local storage reads the real git state ----------


def test_can_push_local_allows_when_prep_is_ignored_and_untracked(git_root):
    write_storage(git_root, "local")
    write_local_rule(git_root)
    (git_root / "prep" / "status.md").write_text("# Status\n", encoding="utf-8")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is True
    # the reason says what was checked, not what is assumed
    assert "tracks nothing" in reason and "ignores" in reason


def test_can_push_local_allows_a_tracked_prep_gitignore_alone(git_root):
    write_storage(git_root, "local")
    write_local_rule(git_root)
    run_git(git_root, "add", "-f", "prep/.gitignore")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_local_refuses_when_prep_files_are_tracked(git_root):
    # reviewer probe: storage switched to local after prep/ was committed, so the files are still in git
    (git_root / "prep" / "profile").mkdir(parents=True)
    (git_root / "prep" / "profile" / "facts.md").write_text("| a fact | confirmed | cv |\n", encoding="utf-8")
    run_git(git_root, "add", "prep")
    commit_all_staged(git_root)
    write_storage(git_root, "local")
    write_local_rule(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "tracks 1 file" in reason and "prep/profile/facts.md" in reason


def test_can_push_local_refuses_when_the_ignore_rule_is_missing(git_root):
    write_storage(git_root, "local")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "does not ignore" in reason


def test_can_push_local_refuses_when_git_cannot_be_asked(tmp_root):
    # (a folder that is not a repository has no remote either, so ask with an explicit URL)
    write_storage(tmp_root, "local")
    write_local_rule(tmp_root)
    assert remote_guard.can_push(tmp_root, USER_REMOTE_URL)[0] is False


def test_can_push_refuses_other_storage_while_the_local_rule_is_still_there(git_root, monkeypatch):
    write_storage(git_root, "private")
    write_local_rule(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "local rule" in reason


def test_can_push_other_storage_accepts_a_custom_prep_gitignore(git_root, monkeypatch):
    write_storage(git_root, "private")
    (git_root / "prep").mkdir(exist_ok=True)
    (git_root / "prep" / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")
    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_treats_an_undecodable_prep_gitignore_as_not_the_local_rule(git_root, monkeypatch):
    write_storage(git_root, "private")
    (git_root / "prep").mkdir(exist_ok=True)
    (git_root / "prep" / ".gitignore").write_bytes(b"\xff\xfe\x00bad")
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")
    assert remote_guard.can_push(git_root)[0] is True


# ---------- can_push: local storage while history still holds prep/ ----------


def switch_to_local_after_committing_prep(root):
    """private setup, prep/ committed, then local setup with --untrack-prep and the removal committed (history keeps prep/)"""
    assert init.main(["setup", "--storage", "private"]) == 0
    run_git(root, "add", "prep")
    commit_all_staged(root)
    assert init.main(["setup", "--storage", "local", "--untrack-prep"]) == 0
    commit_all_staged(root)
    assert run_git(root, "ls-files", "prep") == ""


def test_can_push_local_refuses_a_public_target_when_history_holds_prep(git_root, monkeypatch):
    switch_to_local_after_committing_prep(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    # says why: the index is clean, but earlier commits contain prep/ and a push would publish them
    assert "earlier commits" in reason and "publish" in reason and "public" in reason


def test_can_push_local_allows_a_private_target_when_history_holds_prep(git_root, monkeypatch):
    switch_to_local_after_committing_prep(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is True
    assert "earlier commits" in reason


def test_can_push_local_with_prep_history_needs_the_users_confirmation_for_an_unverifiable_target(git_root, monkeypatch):
    switch_to_local_after_committing_prep(git_root)
    run_git(git_root, "remote", "add", "origin", GITLAB_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")

    allowed, reason = remote_guard.can_push(git_root)
    assert allowed is False
    assert "confirm-remote" in reason

    assert init.main(["confirm-remote"]) == 0
    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_local_ignores_history_that_only_touched_prep_gitignore(git_root, monkeypatch):
    write_storage(git_root, "local")
    write_local_rule(git_root)
    run_git(git_root, "add", "-f", "prep/.gitignore")
    commit_all_staged(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    assert remote_guard.can_push(git_root)[0] is True


def test_can_push_local_looks_at_every_ref_not_only_the_checked_out_branch(git_root, monkeypatch):
    # prep/ was committed on another branch: a push of that branch (or --all) would publish it
    (git_root / "README.md").write_text("engine\n", encoding="utf-8")
    run_git(git_root, "add", "README.md")
    commit_all_staged(git_root)
    run_git(git_root, "switch", "-q", "-c", "records")
    write_local_rule(git_root)
    (git_root / "prep" / "status.md").write_text("# Status\n", encoding="utf-8")
    run_git(git_root, "add", "-f", "prep/status.md")
    commit_all_staged(git_root)
    run_git(git_root, "switch", "-q", "-")
    write_storage(git_root, "local")
    write_local_rule(git_root)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    assert remote_guard.can_push(git_root)[0] is False


# ---------- can_push: look-alikes and the user's confirmation ----------


@pytest.mark.parametrize("storage", ["private", "local", "public-encrypted"])
def test_can_push_refuses_a_template_lookalike_in_every_mode(git_root, storage):
    write_storage(git_root, storage, confirmed_private_remote="https://gitlab.com/someone/interview-sparring.git")
    if storage == "local":
        write_local_rule(git_root)
    allowed, reason = remote_guard.can_push(git_root, "https://gitlab.com/someone/interview-sparring.git")
    assert allowed is False
    assert "template" in reason



def test_can_push_allows_an_unverifiable_remote_the_user_confirmed(git_root, monkeypatch):
    write_storage(git_root, "private", confirmed_private_remote=GITLAB_URL)
    run_git(git_root, "remote", "add", "origin", GITLAB_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is True
    assert "confirmed" in reason


def test_can_push_confirmation_ignores_credentials_but_not_other_urls(git_root, monkeypatch):
    write_storage(git_root, "private", confirmed_private_remote=GITLAB_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")

    assert remote_guard.can_push(git_root, url_with_credentials("gitlab.com/someone/my-prep.git"))[0] is True
    assert remote_guard.can_push(git_root, "https://gitlab.com/someone/another.git")[0] is False


def test_can_push_confirmation_never_beats_a_public_answer(git_root, monkeypatch):
    write_storage(git_root, "private", confirmed_private_remote=USER_REMOTE_URL)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")
    assert remote_guard.can_push(git_root)[0] is False


def test_can_push_never_accepts_a_confirmation_for_a_github_remote(git_root, monkeypatch):
    # (GitHub is checked by the API only: a confirmation stored for a GitHub URL, e.g. from an old settings.json, is ignored)
    write_storage(git_root, "private", confirmed_private_remote=USER_REMOTE_URL)
    run_git(git_root, "remote", "add", "origin", USER_REMOTE_URL)
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")

    allowed, reason = remote_guard.can_push(git_root)

    assert allowed is False
    assert "confirm-remote" not in reason
    assert "GitHub" in reason


@pytest.mark.parametrize(
    "url",
    [
        "ssh://git@ssh.github.com:443/someone/my-prep.git",
        "git://github.com/someone/my-prep.git",
        "git+ssh://git@github.com/someone/my-prep.git",
        "github.com/someone/my-prep",
        # (no repository path: the API cannot be asked, but the host is GitHub)
        "https://github.com/someone",
        "https://github.com./someone/my-prep",
        "ftp://github.com/someone/my-prep",
    ],
)
def test_can_push_never_accepts_a_confirmation_for_a_github_host_in_any_form(git_root, monkeypatch, url):
    write_storage(git_root, "private", confirmed_private_remote=url)
    monkeypatch.setattr(remote_guard, "visibility", lambda target_url: "unknown")

    allowed, reason = remote_guard.can_push(git_root, url)

    assert allowed is False
    assert "GitHub" in reason and "confirm-remote" not in reason


def test_can_push_ignores_a_confirmation_that_is_not_a_string(git_root, monkeypatch):
    write_storage(git_root, "private", confirmed_private_remote=["x"])
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "unknown")
    assert remote_guard.can_push(git_root, GITLAB_URL)[0] is False


def test_redact_url_credentials_hides_tokens_only():
    assert remote_guard.redact_url_credentials(url_with_credentials("github.com/a/b.git")) == "https://github.com/a/b.git"
    assert remote_guard.redact_url_credentials("git@github.com:a/b.git") == "git@github.com:a/b.git"


# ---------- CLI ----------


def test_cli_can_push_prints_the_reason_and_sets_the_exit_code(git_root, monkeypatch, capsys):
    write_storage(git_root, "private")
    monkeypatch.setattr(remote_guard, "visibility", lambda url: "public")

    assert remote_guard.main(["can-push", "--remote-name", "backup", "--remote-url", USER_REMOTE_URL]) == 1
    captured = capsys.readouterr()
    assert "public" in captured.err and captured.out == ""

    monkeypatch.setattr(remote_guard, "visibility", lambda url: "private_or_missing")
    assert remote_guard.main(["can-push", "--remote-url", USER_REMOTE_URL]) == 0
    assert "push allowed" in capsys.readouterr().out


def test_cli_can_push_resolves_a_remote_name_to_its_push_url(git_root, monkeypatch):
    write_storage(git_root, "private")
    run_git(git_root, "remote", "add", "backup", "https://github.com/someone/fetch-only.git")
    run_git(git_root, "remote", "set-url", "--push", "backup", USER_REMOTE_URL)
    seen_urls = []
    monkeypatch.setattr(remote_guard, "visibility", lambda url: seen_urls.append(url) or "private_or_missing")

    assert remote_guard.main(["can-push", "--remote-name", "backup"]) == 0

    assert seen_urls == [USER_REMOTE_URL]


def test_cli_can_push_refuses_an_unknown_remote_name(git_root, capsys):
    write_storage(git_root, "private")
    assert remote_guard.main(["can-push", "--remote-name", "nope"]) == 1
    assert "nope" in capsys.readouterr().err
