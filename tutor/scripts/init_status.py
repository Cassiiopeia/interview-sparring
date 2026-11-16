"""Status report for `init.py status`: settings, key, hook, origin, what is ready and what the init conversation must still fill"""

from pathlib import Path

from prep_git_state import GIT_HOOKS_PATH, is_git_repository
from prep_settings import read_settings
from privacy_check import GitCommandError, run_git
from remote_guard import get_origin_url, is_template_origin, redact_url_credentials
from secret_crypt import load_key

# a markdown table has a header row and a separator row before the data rows
TABLE_HEADER_ROW_COUNT = 2
PLACEHOLDER_FILE_NAME = ".gitkeep"


def is_hooks_configured(root):
    """core.hooksPath of the root's own repository points at .githooks"""
    if not is_git_repository(root):
        return False
    try:
        configured = run_git(root, "config", "--get", "core.hooksPath").decode("utf-8", errors="replace").strip()
    except GitCommandError:
        return False
    return configured == GIT_HOOKS_PATH


def count_table_data_rows(markdown_file):
    """Rows below a markdown table's header and separator"""
    if not markdown_file.is_file():
        return 0
    table_rows = [line for line in markdown_file.read_text(encoding="utf-8").splitlines() if line.lstrip().startswith("|")]
    return max(0, len(table_rows) - TABLE_HEADER_ROW_COUNT)


def has_files_besides_placeholder(folder):
    return folder.is_dir() and any(path.is_file() and path.name != PLACEHOLDER_FILE_NAME for path in folder.rglob("*"))


def has_subfolder(folder):
    return folder.is_dir() and any(path.is_dir() for path in folder.iterdir())


def list_content_progress(prep):
    """What the init conversation has filled (ready) and still has to fill (missing)"""
    ready, missing = [], []
    checks = [
        (count_table_data_rows(prep / "profile" / "facts.md") > 0, "profile/facts.md has facts", "profile/facts.md is empty"),
        (
            has_files_besides_placeholder(prep / "profile" / "experiences"),
            "experience cards exist",
            "no experience card yet",
        ),
        (has_subfolder(prep / "interviews"), "an interview folder exists", "no interview folder yet"),
    ]
    for is_done, ready_text, missing_text in checks:
        (ready if is_done else missing).append(ready_text if is_done else missing_text)
    return ready, missing


def build_status_report(root, openssl_path):
    """Everything `init.py status` prints; openssl_path comes from the caller (path or None)"""
    settings = read_settings(root)
    origin = get_origin_url(root)
    is_origin_template = origin is not None and is_template_origin(origin)
    hooks = is_hooks_configured(root)
    has_key = load_key(root) is not None
    ready = []
    if settings is not None:
        ready.append("settings saved")
    if hooks:
        ready.append("privacy hook is active")
    if has_key:
        ready.append("encryption key is present")
    if origin is not None and not is_origin_template:
        ready.append("remote origin is set")
    if settings is None:
        missing = ["setup has not run yet"]
    else:
        content_ready, missing = list_content_progress(Path(root) / "prep")
        ready.extend(content_ready)
    settings = settings or {}
    return {
        "storage": settings.get("storage"),
        "language": settings.get("language"),
        "input": settings.get("input"),
        "has_key": has_key,
        "openssl": openssl_path,
        "hooks": hooks,
        "origin": redact_url_credentials(origin) if origin is not None else None,
        "origin_is_template": is_origin_template,
        "ready": ready,
        "missing": missing,
    }
