"""Settings chosen during init: {root}/prep/profile/settings.json

{"storage": "private" | "local" | "public-encrypted", "language": "en", "input": "typing" | "voice", "created": "YYYY-MM-DD"}
Shared by init.py and remote_guard.py (the push gate reads the storage mode).
"""

import json
from pathlib import Path

# storage: prep/ committed to a private repo
STORAGE_PRIVATE = "private"
# storage: prep/ never committed (prep/.gitignore)
STORAGE_LOCAL = "local"
# storage: public repo, secret/ folders committed only as encrypted copies
STORAGE_PUBLIC_ENCRYPTED = "public-encrypted"
STORAGE_MODES = (STORAGE_PRIVATE, STORAGE_LOCAL, STORAGE_PUBLIC_ENCRYPTED)

INPUT_TYPING = "typing"
INPUT_VOICE = "voice"
INPUT_MODES = (INPUT_TYPING, INPUT_VOICE)


def settings_path(root):
    return Path(root) / "prep" / "profile" / "settings.json"


def read_settings(root):
    """Settings dict; None when init has not written it yet; ValueError when the file is damaged"""
    path = settings_path(root)
    if not path.is_file():
        return None
    try:
        settings = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} is not valid JSON: {error}") from error
    if not isinstance(settings, dict):
        raise ValueError(f"{path.name} must hold a JSON object")
    return settings


def write_settings(root, settings):
    path = settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as settings_file:
        json.dump(settings, settings_file, ensure_ascii=False, indent=2)
        settings_file.write("\n")
