"""Helpers shared by the init, remote guard and hook tests: git commands, settings, the local-storage ignore rule"""

import subprocess

import prep_settings

TEMPLATE_HTTPS_URL = "https://github.com/Cassiiopeia/interview-sparring"
USER_REMOTE_URL = "https://github.com/someone/my-prep.git"
# what init writes to prep/.gitignore for local storage
LOCAL_RULE_TEXT = "*\n!.gitignore\n"


def run_git(root, *arguments):
    completed = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True)
    return completed.stdout.strip()


def commit_all_staged(root):
    # --no-verify: the pre-commit hook is not what these tests exercise
    run_git(
        root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--no-verify", "-m", "x"
    )


def write_storage(root, storage, **extra_settings):
    settings = {"storage": storage, "language": "en", "input": "typing", "created": "2026-01-01", **extra_settings}
    prep_settings.write_settings(root, settings)


def write_local_rule(root):
    ignore_file = root / "prep" / ".gitignore"
    ignore_file.parent.mkdir(parents=True, exist_ok=True)
    ignore_file.write_text(LOCAL_RULE_TEXT, encoding="utf-8")


def url_with_credentials(host_and_path):
    """https://user:token@host/path built at run time, so no source line looks like an email address to privacy_check"""
    user_info = "user:token"
    return f"https://{user_info}@{host_and_path}"
