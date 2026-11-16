"""Git remote setup for init: template origin > upstream, --remote > origin, no push to any remote that points at the template"""

import remote_guard
from prep_git_state import is_git_repository
from privacy_check import GitCommandError, run_git
from remote_guard import get_origin_url, is_template_origin, redact_url_credentials

UPSTREAM_REMOTE_NAME = "upstream"
# push URL for remotes that point at the template: not a repository, so a push there fails
DISABLED_PUSH_URL = "no_push"


def decode_git_output(output):
    return output.decode("utf-8", errors="replace").strip()


def list_remote_names(root):
    return decode_git_output(run_git(root, "remote")).split()


def clear_branch_tracking(root, remote_name):
    """Unset branch.<name>.remote/.merge that point at remote_name (a bare `git push` must not follow them)"""
    try:
        listed = decode_git_output(run_git(root, "config", "--get-regexp", r"^branch\..*\.remote$"))
    except GitCommandError:
        # (exit 1: no branch has tracking config)
        return
    for line in listed.splitlines():
        key, _, value = line.partition(" ")
        if value.strip() != remote_name:
            continue
        branch_name = key[len("branch.") : -len(".remote")]
        for suffix in ("remote", "merge"):
            try:
                run_git(root, "config", "--unset", f"branch.{branch_name}.{suffix}")
            except GitCommandError:
                pass


def move_template_origin_to_upstream(root):
    """origin (the template) > upstream; with an upstream already present, origin is just dropped"""
    if UPSTREAM_REMOTE_NAME in list_remote_names(root):
        run_git(root, "remote", "remove", remote_guard.ORIGIN_REMOTE_NAME)
        return
    run_git(root, "remote", "rename", remote_guard.ORIGIN_REMOTE_NAME, UPSTREAM_REMOTE_NAME)
    # (the rename drags branch tracking along: main would track upstream/main and a bare push would target the template)
    clear_branch_tracking(root, UPSTREAM_REMOTE_NAME)


def disable_push_to_template_remotes(root):
    """Push URL of every remote whose fetch or push URL is the template > no_push; returns the remote names changed"""
    disabled = []
    for remote_name in list_remote_names(root):
        fetch_url = decode_git_output(run_git(root, "remote", "get-url", "--", remote_name))
        push_url = decode_git_output(run_git(root, "remote", "get-url", "--push", "--", remote_name))
        points_at_template = is_template_origin(fetch_url) or is_template_origin(push_url)
        if points_at_template and push_url != DISABLED_PUSH_URL:
            run_git(root, "remote", "set-url", "--push", "--", remote_name, DISABLED_PUSH_URL)
            disabled.append(remote_name)
    return disabled


def configure_remotes(root, remote_url):
    """Template origin > upstream, --remote > origin, template pushes off; returns the notes to show"""
    if not is_git_repository(root):
        if remote_url:
            return ["not a git repository: --remote was not applied; run `git init`, then run setup again"]
        return []
    notes = []
    origin = get_origin_url(root)
    if origin is not None and is_template_origin(origin):
        move_template_origin_to_upstream(root)
        origin = None
        notes.append(
            f"template origin renamed to {UPSTREAM_REMOTE_NAME} (engine updates come from there, your records never go there)"
        )
    if remote_url is not None:
        if origin is None:
            run_git(root, "remote", "add", remote_guard.ORIGIN_REMOTE_NAME, remote_url)
        elif origin != remote_url:
            run_git(root, "remote", "set-url", remote_guard.ORIGIN_REMOTE_NAME, remote_url)
        notes.append(f"origin is {redact_url_credentials(remote_url)}")
    elif origin is None:
        notes.append("no origin remote yet: run setup with --remote <your repository URL> before pushing")
    for remote_name in disable_push_to_template_remotes(root):
        notes.append(f"push to {remote_name} disabled (push URL {DISABLED_PUSH_URL}): it points at the template")
    return notes
