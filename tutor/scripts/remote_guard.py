#!/usr/bin/env python3
"""Remote safety: template detection, repository visibility, and the push gate (also run by .githooks/pre-push).

    python3 tutor/scripts/remote_guard.py can-push [--remote-name NAME] [--remote-url URL]
        exit 0 when pushing prep/ to that remote is safe, else 1 with the reason (no URL: origin is checked)

Visibility asks the public GitHub API anonymously (no token, 5 s timeout, nothing but the repository path is sent).
Push gate, in order:
    target is the template (any URL form), or a copy of it on another host    refused in every mode
    storage is not local but prep/.gitignore still holds the generated local rule    refused (switch left a stale rule)
    private           GitHub must answer 404 to an anonymous request; 200 is refused; no answer (non-GitHub, offline)
                      is refused unless the URL is not on GitHub and settings.json confirmed_private_remote equals it
                      (init.py confirm-remote); a GitHub URL is never accepted on the user's word
    local             git must track nothing under prep/ except prep/.gitignore, and must ignore the prep/ probe paths;
                      when any ref's history still holds prep/ content, the target must pass the private rule too
    public-encrypted  no visibility rule (the pre-commit hook keeps secret/ plaintext out; the rest of prep/ is public)
"""

import argparse
import re
import sys
import urllib.error
import urllib.request

import common
import prep_settings
from prep_git_state import (
    find_commit_holding_prep,
    is_generated_local_rule,
    list_paths_git_does_not_ignore,
    list_tracked_prep_files,
    prep_gitignore_path,
)
from privacy_check import GitCommandError, run_git

# the public template this repo is copied from
TEMPLATE_OWNER = "Cassiiopeia"
TEMPLATE_REPOSITORY = "interview-sparring"

# visibility results
VISIBILITY_PUBLIC = "public"
VISIBILITY_PRIVATE_OR_MISSING = "private_or_missing"
VISIBILITY_UNKNOWN = "unknown"

GITHUB_API_REPOSITORY_URL = "https://api.github.com/repos/{owner}/{repository}"
GITHUB_API_TIMEOUT_SECONDS = 5
HTTP_USER_AGENT = "interview-sparring"
HTTP_STATUS_OK = 200
HTTP_STATUS_NOT_FOUND = 404

ORIGIN_REMOTE_NAME = "origin"

# every form git accepts for a GitHub repository (matched at the start, case-insensitive):
#   https|http|ssh|git|git+ssh://[user[:token]@]HOST[:port]/o/r[.git][/]   scp form [user@]HOST:o/r   bare HOST/o/r
# HOST = [www.|ssh.]github.com (ssh.github.com is the port-443 SSH host)
GITHUB_REPOSITORY_PATTERN = re.compile(
    r"^(?:(?:https?|ssh|git|git\+ssh)://(?:[^@/\s]+@)?|[^@/\s]+@)?"
    r"(?:www\.|ssh\.)?github\.com(?::[0-9]+)?[:/]"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repository>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
# host of any URL form: [scheme://][user@]host (userinfo runs to the last @ before the first /)
URL_HOST_PATTERN = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://)?(?:[^/\s]*@)?(?P<host>[^:/\s@]+)")
# any host ending in this counts as GitHub's (github.com, ssh.github.com, api.github.com, github.com. with a dot)
GITHUB_HOST_SUFFIX = "github.com"
# credentials in an http(s) URL (https://user:token@host/...)
URL_CREDENTIALS_PATTERN = re.compile(r"^(?P<scheme>https?://)[^@/\s]+@")
# a path that ends in the template's name: .../interview-sparring[.git][/] (any host, local paths included)
TEMPLATE_NAME_PATH_PATTERN = re.compile(rf"(?:^|[/:]){re.escape(TEMPLATE_REPOSITORY)}(?:\.git)?/?$", re.IGNORECASE)

# commit hash characters shown in a refusal
HISTORY_COMMIT_SHOWN_LENGTH = 12

EXIT_ALLOWED = 0
EXIT_REFUSED = 1


def parse_github_repository(url):
    """GitHub URL in any form git accepts (https, ssh, git, git+ssh, scp, bare github.com/o/r; with or without .git) > (owner, repository); None for anything else"""
    match = GITHUB_REPOSITORY_PATTERN.match(url.strip())
    if match is None:
        return None
    owner, repository = match.group("owner"), match.group("repository")
    # (".." would climb out of the /repos/{owner}/{repository} API path)
    if set(owner) == {"."} or set(repository) == {"."}:
        return None
    return owner, repository


def is_github_host(url):
    """True when the URL's host ends with github.com (any scheme, port, user, letter case, trailing dot), even without a repository path"""
    match = URL_HOST_PATTERN.match(url.strip())
    if match is None:
        return False
    return match.group("host").lower().rstrip(".").endswith(GITHUB_HOST_SUFFIX)


def is_template_origin(url):
    """True when url is the template repository (any URL form, any letter case)"""
    repository = parse_github_repository(url)
    if repository is None:
        return False
    return repository[0].lower() == TEMPLATE_OWNER.lower() and repository[1].lower() == TEMPLATE_REPOSITORY.lower()


def is_template_lookalike(url):
    """True for a non-GitHub-parsable URL whose path ends in the template's name: a mirror of the template is not provably yours"""
    cleaned_url = url.strip()
    return parse_github_repository(cleaned_url) is None and TEMPLATE_NAME_PATH_PATTERN.search(cleaned_url) is not None


def redact_url_credentials(url):
    """Remove user:token@ from an http(s) URL so a token is never printed"""
    return URL_CREDENTIALS_PATTERN.sub(r"\g<scheme>", url)


def visibility(url):
    """GitHub repo visibility from an anonymous API call: 200 public, 404 private_or_missing; anything else unknown"""
    repository = parse_github_repository(url)
    if repository is None:
        return VISIBILITY_UNKNOWN
    owner, repository_name = repository
    request = urllib.request.Request(
        GITHUB_API_REPOSITORY_URL.format(owner=owner, repository=repository_name),
        headers={"User-Agent": HTTP_USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_API_TIMEOUT_SECONDS) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except (urllib.error.URLError, OSError):
        # (offline, timeout, DNS failure: cannot tell)
        return VISIBILITY_UNKNOWN
    if status == HTTP_STATUS_OK:
        return VISIBILITY_PUBLIC
    if status == HTTP_STATUS_NOT_FOUND:
        return VISIBILITY_PRIVATE_OR_MISSING
    return VISIBILITY_UNKNOWN


def get_origin_url(root):
    """URL of the origin remote; None when there is none (or root is not a git repository)"""
    try:
        return run_git(root, "remote", "get-url", ORIGIN_REMOTE_NAME).decode("utf-8", errors="replace").strip() or None
    except GitCommandError:
        return None


def get_remote_push_url(root, remote_name):
    """URL git would push to for a remote name (push URL if set, else fetch URL); None when the remote does not exist"""
    try:
        output = run_git(root, "remote", "get-url", "--push", "--", remote_name)
    except GitCommandError:
        return None
    return output.decode("utf-8", errors="replace").strip() or None


def can_push(root, remote_url=None):
    """Push gate: (allowed, reason). Checks the target URL (origin when None); every reason names what was checked"""
    settings = prep_settings.read_settings(root)
    if settings is None:
        return False, "init has not run (no prep/profile/settings.json): run `/spar init` first"
    target_url = get_origin_url(root) if remote_url is None else remote_url.strip()
    if not target_url:
        return False, "no remote URL to check (no origin remote): add your own repository as origin first"
    if is_template_origin(target_url):
        return False, "target is the public template repository: set your own repository as origin"
    if is_template_lookalike(target_url):
        return False, (
            f"target path ends in /{TEMPLATE_REPOSITORY} on a host other than github.com, so it may be a copy of the "
            "template and is refused in every storage mode: rename your repository"
        )
    storage = settings.get("storage")
    if storage != prep_settings.STORAGE_LOCAL and is_generated_local_rule(prep_gitignore_path(root)):
        return False, (
            f"storage is {storage!r} but prep/.gitignore still holds the generated local rule (* and !.gitignore): "
            "delete it, or run init setup again"
        )
    if storage == prep_settings.STORAGE_LOCAL:
        return check_local_storage(root, target_url, settings)
    if storage == prep_settings.STORAGE_PUBLIC_ENCRYPTED:
        return True, "storage public-encrypted: no visibility rule applies (everything outside secret/ is published as is)"
    if storage == prep_settings.STORAGE_PRIVATE:
        return check_private_target(target_url, settings)
    return False, f"unknown storage mode {storage!r} in settings.json: run `/spar init` again"


def check_local_storage(root, target_url, settings):
    """Local storage: git tracks nothing under prep/ (except prep/.gitignore) and ignores the probe paths; history is checked last"""
    try:
        tracked_paths = list_tracked_prep_files(root)
        not_ignored_paths = [] if tracked_paths else list_paths_git_does_not_ignore(root)
        history_commit = None if tracked_paths or not_ignored_paths else find_commit_holding_prep(root)
    except GitCommandError as error:
        return False, f"git could not be asked about prep/ ({error}): local storage is not proven"
    if tracked_paths:
        shown = ", ".join(tracked_paths[:3]) + (", ..." if len(tracked_paths) > 3 else "")
        return False, (
            f"storage is local but git tracks {len(tracked_paths)} file(s) under prep/ ({shown}): "
            "run `git rm -r --cached prep` (the files stay on disk) and commit"
        )
    if not_ignored_paths:
        return False, (
            f"storage is local but git does not ignore {', '.join(not_ignored_paths)}: "
            "prep/.gitignore needs the rule `*` and `!.gitignore`"
        )
    index_reason = (
        "git tracks nothing under prep/ except prep/.gitignore, and git ignores prep/status.md and prep/profile/facts.md"
    )
    if history_commit is None:
        return True, f"storage local: {index_reason}"
    # (a clean index does not help: a push sends the commits that already hold prep/)
    is_private_target, private_reason = check_private_target(target_url, settings)
    if is_private_target:
        return True, (
            f"storage local: {index_reason}; earlier commits (e.g. {history_commit[:HISTORY_COMMIT_SHOWN_LENGTH]}) "
            f"contain prep/, but the target passes the private rule: {private_reason}"
        )
    return False, (
        f"storage is local and {index_reason}, but earlier commits (e.g. {history_commit[:HISTORY_COMMIT_SHOWN_LENGTH]}) "
        f"contain prep/, and pushing would publish them to a target that is not confirmed private ({private_reason}). "
        "Push to a repository you confirmed private, or start a fresh repository, or rewrite the history first "
        "(nothing here does that for you)"
    )


def normalize_remote_url(url):
    """URL as stored and compared in settings: trimmed, http(s) credentials removed"""
    return redact_url_credentials(url.strip())


def check_private_target(target_url, settings):
    """Private storage: only a repository confirmed private (by GitHub or by the user) may receive prep/"""
    target_visibility = visibility(target_url)
    if target_visibility == VISIBILITY_PRIVATE_OR_MISSING:
        return True, "GitHub answered 404 to an anonymous request (private or missing)"
    if target_visibility == VISIBILITY_PUBLIC:
        return False, (
            "GitHub answered 200 to an anonymous request: the repository is public, "
            "but storage is private (make it private, or choose public-encrypted)"
        )
    # (GitHub must prove it by the API; a stored confirmation counts only for hosts GitHub cannot be asked about)
    if parse_github_repository(target_url) is not None or is_github_host(target_url):
        return False, (
            "GitHub did not answer (offline or rate limited), and a user confirmation is not accepted for GitHub "
            "remotes: retry when online, and make the repository private"
        )
    confirmed_url = settings.get("confirmed_private_remote")
    if isinstance(confirmed_url, str) and confirmed_url == normalize_remote_url(target_url):
        return True, "GitHub could not be asked, but the user confirmed this URL as private (confirmed_private_remote)"
    return False, (
        "cannot verify that the target is private (not on GitHub): "
        "ask the user whether it is private, then run `python3 tutor/scripts/init.py confirm-remote`"
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Remote safety checks")
    commands = parser.add_subparsers(dest="command", required=True)
    can_push_command = commands.add_parser("can-push", help="exit 0 when pushing prep/ there is safe")
    can_push_command.add_argument("--remote-name", help="git remote name (its push URL is checked unless --remote-url is given)")
    can_push_command.add_argument("--remote-url", help="URL being pushed to (the pre-push hook passes it)")
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    root = common.repo_root()
    remote_url = arguments.remote_url
    if not remote_url and arguments.remote_name:
        remote_url = get_remote_push_url(root, arguments.remote_name)
        if remote_url is None:
            print(f"push refused: no remote named {arguments.remote_name!r}", file=sys.stderr)
            return EXIT_REFUSED
    allowed, reason = can_push(root, remote_url)
    if allowed:
        print(f"push allowed: {reason}")
        return EXIT_ALLOWED
    print(f"push refused: {reason}", file=sys.stderr)
    return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
