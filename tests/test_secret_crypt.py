"""Tests for secret_crypt.py: secret/ <-> secret-encrypted/ mirror with openssl, using a temp dir as the root"""

import json
import os
import stat
import subprocess

import pytest

import secret_crypt

KEY = "test-key-abc"

# crypto tests need a real openssl; folder discovery and .env parsing do not
requires_openssl = pytest.mark.skipif(
    secret_crypt.find_openssl() is None, reason="openssl is not installed"
)


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    # keep the real repo untouched; no key leaks in from the developer's shell
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    monkeypatch.delenv("SPARRING_ENCRYPTION_KEY", raising=False)
    return tmp_path


@pytest.fixture
def korean_secret_file(tmp_root):
    secret_file = tmp_root / "prep" / "profile" / "secret" / "비밀 메모.md"
    secret_file.parent.mkdir(parents=True)
    secret_file.write_text("예시 메모 12, 34\n", encoding="utf-8")
    return secret_file


def write_encrypted_with_fixed_salt(encrypted_file, plaintext, key):
    """.enc with a fixed salt: wrong-key decryption then fails the same way every run (random salt passes padding 1 in 256)"""
    encrypted_file.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [secret_crypt.find_openssl(), "enc", "-S", "0011223344556677", *secret_crypt.CIPHER_ARGUMENTS],
        input=plaintext,
        capture_output=True,
        env={**os.environ, "SPARRING_ENCRYPTION_KEY": key},
        check=True,
    )
    encrypted_file.write_bytes(completed.stdout)


# ---------- folder discovery ----------


def test_find_secret_dirs_skips_git_superpowers_and_encrypted(tmp_root):
    wanted = tmp_root / "prep" / "profile" / "secret"
    wanted.mkdir(parents=True)
    (tmp_root / "other" / "secret").mkdir(parents=True)
    # never scanned: tool output, git internals, encrypted mirrors
    (tmp_root / ".git" / "secret").mkdir(parents=True)
    (tmp_root / ".superpowers" / "secret").mkdir(parents=True)
    (tmp_root / "prep" / "secret-encrypted" / "secret").mkdir(parents=True)

    found = secret_crypt.find_secret_dirs(tmp_root)

    assert found == [tmp_root / "other" / "secret", wanted]


def test_find_secret_dirs_does_not_descend_into_secret(tmp_root):
    (tmp_root / "a" / "secret" / "secret").mkdir(parents=True)

    assert secret_crypt.find_secret_dirs(tmp_root) == [tmp_root / "a" / "secret"]


def test_encrypted_dir_for_is_sibling_secret_encrypted(tmp_root):
    secret_dir = tmp_root / "prep" / "profile" / "secret"
    assert secret_crypt.encrypted_dir_for(secret_dir) == tmp_root / "prep" / "profile" / "secret-encrypted"


# ---------- key loading ----------


def test_load_key_from_env_file(tmp_root):
    (tmp_root / ".env").write_text("SPARRING_ENCRYPTION_KEY=abc\n", encoding="utf-8")
    assert secret_crypt.load_key(tmp_root) == "abc"


def test_load_key_env_file_handles_quotes_comments_and_other_lines(tmp_root):
    (tmp_root / ".env").write_text(
        '# comment\nOTHER=1\n\nexport SPARRING_ENCRYPTION_KEY="quoted key"\n', encoding="utf-8"
    )
    assert secret_crypt.load_key(tmp_root) == "quoted key"


def test_load_key_falls_back_to_environment_variable(tmp_root, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", "from-env")
    assert secret_crypt.load_key(tmp_root) == "from-env"


def test_load_key_prefers_env_file_over_environment(tmp_root, monkeypatch):
    (tmp_root / ".env").write_text("SPARRING_ENCRYPTION_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", "from-env")
    assert secret_crypt.load_key(tmp_root) == "from-file"


def test_load_key_returns_none_when_missing_or_empty(tmp_root):
    assert secret_crypt.load_key(tmp_root) is None
    (tmp_root / ".env").write_text("SPARRING_ENCRYPTION_KEY=\n", encoding="utf-8")
    assert secret_crypt.load_key(tmp_root) is None


# ---------- openssl lookup ----------


def test_find_openssl_uses_windows_git_fallback(monkeypatch, tmp_path):
    fake_openssl = tmp_path / "openssl.exe"
    fake_openssl.write_text("")
    monkeypatch.setattr(secret_crypt.shutil, "which", lambda name: None)
    monkeypatch.setattr(secret_crypt, "is_windows", lambda: True)
    monkeypatch.setattr(
        secret_crypt, "WINDOWS_OPENSSL_CANDIDATES", [str(tmp_path / "missing.exe"), str(fake_openssl)]
    )
    assert secret_crypt.find_openssl() == str(fake_openssl)


def test_find_openssl_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(secret_crypt.shutil, "which", lambda name: None)
    monkeypatch.setattr(secret_crypt, "is_windows", lambda: False)
    assert secret_crypt.find_openssl() is None


# ---------- encrypt / decrypt ----------


@requires_openssl
def test_roundtrip_korean_filename(tmp_root, korean_secret_file):
    original = korean_secret_file.read_text(encoding="utf-8")

    changed = secret_crypt.encrypt_all(tmp_root, KEY).changed

    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    assert changed == [encrypted_file]
    assert encrypted_file.is_file()
    # ciphertext must not leak the plaintext
    assert "매출".encode("utf-8") not in encrypted_file.read_bytes()

    korean_secret_file.unlink()
    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.restored == [korean_secret_file]
    assert result.conflicts == []
    assert korean_secret_file.read_text(encoding="utf-8") == original


@requires_openssl
def test_roundtrip_keeps_nested_folders_and_binary_bytes(tmp_root):
    nested_file = tmp_root / "prep" / "secret" / "interviews" / "2026" / "raw.bin"
    nested_file.parent.mkdir(parents=True)
    payload = bytes(range(256)) * 3
    nested_file.write_bytes(payload)

    secret_crypt.encrypt_all(tmp_root, KEY)
    nested_file.unlink()
    secret_crypt.decrypt_all(tmp_root, KEY)

    assert nested_file.read_bytes() == payload
    assert (tmp_root / "prep" / "secret-encrypted" / "interviews" / "2026" / "raw.bin.enc").is_file()


@requires_openssl
def test_encrypt_skips_unchanged(tmp_root, korean_secret_file):
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed != []
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    first_bytes = encrypted_file.read_bytes()

    # random salt would change the bytes if it were rewritten
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed == []
    assert encrypted_file.read_bytes() == first_bytes


@requires_openssl
def test_encrypt_rewrites_changed_file(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.write_text("바뀐 내용\n", encoding="utf-8")

    changed = secret_crypt.encrypt_all(tmp_root, KEY).changed

    assert [path.name for path in changed] == ["비밀 메모.md.enc"]
    korean_secret_file.unlink()
    secret_crypt.decrypt_all(tmp_root, KEY)
    assert korean_secret_file.read_text(encoding="utf-8") == "바뀐 내용\n"


@requires_openssl
def test_encrypt_ignores_os_junk_files(tmp_root, korean_secret_file):
    (korean_secret_file.parent / ".DS_Store").write_bytes(b"junk")
    (korean_secret_file.parent / "Thumbs.db").write_bytes(b"junk")

    changed = secret_crypt.encrypt_all(tmp_root, KEY).changed

    assert [path.name for path in changed] == ["비밀 메모.md.enc"]


@requires_openssl
def test_encrypt_refuses_to_overwrite_with_wrong_key(tmp_root, korean_secret_file):
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    write_encrypted_with_fixed_salt(encrypted_file, b"older content", KEY)
    before = encrypted_file.read_bytes()

    with pytest.raises(secret_crypt.SecretCryptError):
        secret_crypt.encrypt_all(tmp_root, "a-different-key")

    assert encrypted_file.read_bytes() == before


@requires_openssl
def test_decrypt_with_wrong_key_raises(tmp_root):
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "note.md.enc"
    write_encrypted_with_fixed_salt(encrypted_file, b"some secret text", KEY)

    with pytest.raises(secret_crypt.SecretCryptError):
        secret_crypt.decrypt_all(tmp_root, "a-different-key")

    assert not (tmp_root / "prep" / "profile" / "secret" / "note.md").exists()


def replace_encrypted_content(tmp_root, plaintext):
    """Simulate a pulled .enc written elsewhere: same key, other content"""
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    encrypted_file.write_bytes(secret_crypt.encrypt_bytes(KEY, plaintext))
    return encrypted_file


@requires_openssl
def test_decrypt_preserves_unsynced_local_edit(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    # both sides changed since the last sync: local edit, and a different .enc arrives (pull from another machine)
    korean_secret_file.write_text("local edit\n", encoding="utf-8")
    replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))

    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.conflicts == [korean_secret_file]
    assert result.restored == []
    assert korean_secret_file.read_text(encoding="utf-8") == "local edit\n"
    remote_copy = korean_secret_file.with_name("비밀 메모.md.remote")
    assert remote_copy.read_text(encoding="utf-8") == "remote edit\n"


@requires_openssl
def test_decrypt_local_ahead_is_not_conflict(tmp_root, korean_secret_file):
    # local edit not encrypted yet, remote unchanged since the last sync: reported, never silent, never a conflict
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.write_text("local edit\n", encoding="utf-8")

    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.ahead == [korean_secret_file]
    assert result.conflicts == []
    assert result.restored == []
    assert korean_secret_file.read_text(encoding="utf-8") == "local edit\n"
    assert not korean_secret_file.with_name("비밀 메모.md.remote").exists()
    # base stays at the last synced content, so the edit is still "ahead" next time and encrypt pushes it
    assert secret_crypt.decrypt_all(tmp_root, KEY).ahead == [korean_secret_file]
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed != []
    assert secret_crypt.decrypt_all(tmp_root, KEY).ahead == []


@requires_openssl
def test_decrypt_fast_forwards_when_local_unchanged(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    # local untouched since the last sync, remote moved on
    replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))

    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.restored == [korean_secret_file]
    assert result.ahead == []
    assert result.conflicts == []
    assert korean_secret_file.read_text(encoding="utf-8") == "remote edit\n"
    assert not korean_secret_file.with_name("비밀 메모.md.remote").exists()
    # base moved to the remote content: a second run is a no-op
    again = secret_crypt.decrypt_all(tmp_root, KEY)
    assert (again.restored, again.ahead, again.conflicts) == ([], [], [])


@requires_openssl
def test_fast_forward_keeps_previous_copy(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    previous_copy = korean_secret_file.with_name("비밀 메모.md.previous")
    replace_encrypted_content(tmp_root, "remote edit 1\n".encode("utf-8"))

    secret_crypt.decrypt_all(tmp_root, KEY)

    # the overwritten content survives next to the file (single slot)
    assert previous_copy.read_text(encoding="utf-8") == "예시 메모 12, 34\n"
    assert korean_secret_file.read_text(encoding="utf-8") == "remote edit 1\n"
    # a second fast-forward overwrites the same slot with the content it replaced
    replace_encrypted_content(tmp_root, "remote edit 2\n".encode("utf-8"))
    secret_crypt.decrypt_all(tmp_root, KEY)
    assert previous_copy.read_text(encoding="utf-8") == "remote edit 1\n"
    # the previous copy is local-only: never encrypted, and a run with no change leaves the slot alone
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed == []
    assert not (tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.previous.enc").exists()
    assert previous_copy.read_text(encoding="utf-8") == "remote edit 1\n"


@requires_openssl
def test_decrypt_without_sync_state_never_overwrites_differing_local(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    secret_crypt.sync_state_path(korean_secret_file.parent).unlink()
    korean_secret_file.write_text("unknown history\n", encoding="utf-8")

    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.conflicts == [korean_secret_file]
    assert korean_secret_file.read_text(encoding="utf-8") == "unknown history\n"


@requires_openssl
def test_decrypt_skips_identical_local(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    secret_crypt.sync_state_path(korean_secret_file.parent).unlink()

    # same bytes (even with no sync state): nothing to write, no conflict
    result = secret_crypt.decrypt_all(tmp_root, KEY)

    assert result.restored == []
    assert result.conflicts == []
    # and the state is rebuilt, so a later local edit is protected
    state = secret_crypt.load_sync_state(korean_secret_file.parent)
    assert state["비밀 메모.md"] == secret_crypt.sha256_of(korean_secret_file.read_bytes())


@requires_openssl
def test_sync_state_records_hash_and_is_never_encrypted(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)

    state = secret_crypt.load_sync_state(korean_secret_file.parent)
    assert state == {"비밀 메모.md": secret_crypt.sha256_of(korean_secret_file.read_bytes())}
    assert not (korean_secret_file.parent.parent / "secret-encrypted" / ".sync-state.json.enc").exists()
    # unchanged second run: state file and conflict copies stay out of the encrypted set
    korean_secret_file.with_name("비밀 메모.md.remote").write_text("x", encoding="utf-8")
    (korean_secret_file.parent / ".leftover.partial").write_text("x", encoding="utf-8")
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed == []


@requires_openssl
def test_temp_files_are_owner_only_and_cleaned_up(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"

    assert not list(tmp_root.rglob("*.partial"))
    if not secret_crypt.is_windows():
        assert stat.S_IMODE(encrypted_file.stat().st_mode) == 0o600


@requires_openssl
def test_encrypt_refuses_to_overwrite_newer_remote(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    # a newer .enc was pulled, local still equals the last synced content
    encrypted_file = replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))
    pulled_bytes = encrypted_file.read_bytes()
    local_text = korean_secret_file.read_text(encoding="utf-8")

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    assert result.changed == []
    assert result.conflicts == [korean_secret_file]
    assert encrypted_file.read_bytes() == pulled_bytes
    assert korean_secret_file.read_text(encoding="utf-8") == local_text
    remote_copy = korean_secret_file.with_name("비밀 메모.md.remote")
    assert remote_copy.read_text(encoding="utf-8") == "remote edit\n"
    # base is untouched, so the file keeps reporting until it is resolved
    assert secret_crypt.encrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]


@requires_openssl
def test_encrypt_refuses_when_both_sides_changed(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.write_text("local edit\n", encoding="utf-8")
    encrypted_file = replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))
    pulled_bytes = encrypted_file.read_bytes()

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    assert result.conflicts == [korean_secret_file]
    assert encrypted_file.read_bytes() == pulled_bytes


@requires_openssl
def test_encrypt_without_sync_state_refuses_differing_remote(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    secret_crypt.sync_state_path(korean_secret_file.parent).unlink()
    korean_secret_file.write_text("local edit\n", encoding="utf-8")

    assert secret_crypt.encrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]


@requires_openssl
def test_encrypt_confirms_equal_remote_and_sets_base(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    secret_crypt.sync_state_path(korean_secret_file.parent).unlink()

    # remote == local with no base: nothing to write, no conflict, base recorded again
    result = secret_crypt.encrypt_all(tmp_root, KEY)

    assert (result.changed, result.conflicts) == ([], [])
    state = secret_crypt.load_sync_state(korean_secret_file.parent)
    assert state["비밀 메모.md"] == secret_crypt.sha256_of(korean_secret_file.read_bytes())


@requires_openssl
def test_conflict_resolution_paths(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.write_text("local edit\n", encoding="utf-8")
    encrypted_file = replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))
    remote_copy = korean_secret_file.with_name("비밀 메모.md.remote")
    assert secret_crypt.decrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]

    # take theirs: copy .remote over the local file, then decrypt confirms
    korean_secret_file.write_bytes(remote_copy.read_bytes())
    result = secret_crypt.decrypt_all(tmp_root, KEY)
    assert (result.restored, result.ahead, result.conflicts) == ([], [], [])

    # keep mine: merge locally, delete the stale .enc, encrypt
    korean_secret_file.write_text("merged\n", encoding="utf-8")
    replace_encrypted_content(tmp_root, "another remote\n".encode("utf-8"))
    assert secret_crypt.encrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]
    encrypted_file.unlink()
    assert secret_crypt.encrypt_all(tmp_root, KEY).changed == [encrypted_file]


def test_compare_three_way_table():
    compare = secret_crypt.compare_three_way
    status = secret_crypt.SyncStatus
    assert compare("a", "a", "a") is status.IN_SYNC
    assert compare("b", "b", "a") is status.IN_SYNC
    assert compare("a", "b", "a") is status.REMOTE_AHEAD
    assert compare("b", "a", "a") is status.LOCAL_AHEAD
    assert compare("b", "c", "a") is status.DIVERGED
    # never synced
    assert compare("a", "a", None) is status.IN_SYNC
    assert compare("a", "b", None) is status.DIVERGED


# ---------- key check ----------


@requires_openssl
def test_keycheck_created_on_first_encrypt(tmp_root, korean_secret_file):
    keycheck_file = tmp_root / ".sparring-keycheck.enc"
    assert not keycheck_file.exists()

    secret_crypt.encrypt_all(tmp_root, KEY)

    assert keycheck_file.is_file()
    assert secret_crypt.decrypt_bytes(KEY, keycheck_file.read_bytes()) == b"interview-sparring-keycheck-v1"
    # later runs keep the file as is
    first_bytes = keycheck_file.read_bytes()
    secret_crypt.encrypt_all(tmp_root, KEY)
    assert keycheck_file.read_bytes() == first_bytes


@requires_openssl
def test_wrong_key_rejected_by_keycheck(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    before = encrypted_file.read_bytes()
    korean_secret_file.write_text("changed\n", encoding="utf-8")

    with pytest.raises(secret_crypt.WrongKeyError, match="does not match this repo"):
        secret_crypt.encrypt_all(tmp_root, "a-different-key")
    with pytest.raises(secret_crypt.WrongKeyError):
        secret_crypt.decrypt_all(tmp_root, "a-different-key")

    # nothing was touched
    assert encrypted_file.read_bytes() == before
    assert korean_secret_file.read_text(encoding="utf-8") == "changed\n"


@requires_openssl
def test_wrong_key_with_chance_valid_padding_is_still_rejected(tmp_root, monkeypatch):
    # CBC may "decrypt" garbage without error: the marker comparison must catch it
    secret_crypt.create_keycheck_if_missing(tmp_root, KEY)
    monkeypatch.setattr(secret_crypt, "decrypt_bytes", lambda key, ciphertext: b"garbage")

    with pytest.raises(secret_crypt.WrongKeyError):
        secret_crypt.verify_key(tmp_root, KEY)


@requires_openssl
def test_failed_encrypt_does_not_pin_a_wrong_key(tmp_root, korean_secret_file):
    # existing .enc from a key we do not have, no keycheck yet (old repo): refuse and leave no keycheck behind
    encrypted_file = tmp_root / "prep" / "profile" / "secret-encrypted" / "비밀 메모.md.enc"
    write_encrypted_with_fixed_salt(encrypted_file, b"older content", KEY)

    with pytest.raises(secret_crypt.SecretCryptError):
        secret_crypt.encrypt_all(tmp_root, "a-different-key")

    assert not (tmp_root / ".sparring-keycheck.enc").exists()


@requires_openssl
def test_key_is_passed_only_through_child_environment(tmp_root, korean_secret_file, monkeypatch):
    calls = []
    real_run = subprocess.run

    def spy(command, **kwargs):
        calls.append((list(command), kwargs.get("env")))
        return real_run(command, **kwargs)

    monkeypatch.setattr(secret_crypt.subprocess, "run", spy)

    secret_crypt.encrypt_all(tmp_root, KEY)

    assert calls
    for command, env in calls:
        assert KEY not in " ".join(command)
        assert "env:SPARRING_ENCRYPTION_KEY" in command
        assert env["SPARRING_ENCRYPTION_KEY"] == KEY


# ---------- deleting a secret file ----------


def encrypted_copy_of(tmp_root, name):
    return tmp_root / "prep" / "profile" / "secret-encrypted" / f"{name}.enc"


@requires_openssl
def test_encrypt_removes_the_encrypted_copy_of_a_file_deleted_after_a_sync(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    encrypted_file = encrypted_copy_of(tmp_root, korean_secret_file.name)
    korean_secret_file.unlink()

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    assert result.deleted == [encrypted_file]
    assert not encrypted_file.exists()
    # the sync record goes with it, so a later file of the same name starts fresh
    assert korean_secret_file.name not in secret_crypt.load_sync_state(korean_secret_file.parent)
    assert secret_crypt.encrypt_all(tmp_root, KEY).deleted == []


@requires_openssl
def test_encrypt_deletes_only_the_removed_file_and_keeps_nested_ones(tmp_root):
    secret_dir = tmp_root / "prep" / "secret"
    keep_file = secret_dir / "keep.md"
    nested_file = secret_dir / "interviews" / "a" / "notes.md"
    removed_file = secret_dir / "doc.md"
    nested_file.parent.mkdir(parents=True)
    for file in (keep_file, nested_file, removed_file):
        file.write_text(f"{file.name}\n", encoding="utf-8")
    secret_crypt.encrypt_all(tmp_root, KEY)
    removed_file.unlink()
    nested_file.unlink()

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    mirror = tmp_root / "prep" / "secret-encrypted"
    assert sorted(result.deleted) == sorted([mirror / "doc.md.enc", mirror / "interviews" / "a" / "notes.md.enc"])
    assert (mirror / "keep.md.enc").is_file()


@requires_openssl
def test_encrypt_never_deletes_an_encrypted_copy_that_has_no_sync_record(tmp_root, korean_secret_file):
    # a fresh machine: .enc pulled from git, nothing decrypted yet, so no plaintext and no .sync-state.json
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.unlink()
    secret_crypt.sync_state_path(korean_secret_file.parent).unlink()
    encrypted_file = encrypted_copy_of(tmp_root, korean_secret_file.name)

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    assert result.deleted == []
    assert encrypted_file.is_file()
    # ... and decrypt can still restore it
    assert secret_crypt.decrypt_all(tmp_root, KEY).restored == [korean_secret_file]


@requires_openssl
def test_encrypt_keeps_a_deleted_files_encrypted_copy_that_changed_elsewhere_after_the_last_sync(
    tmp_root, korean_secret_file
):
    secret_crypt.encrypt_all(tmp_root, KEY)
    encrypted_file = encrypted_copy_of(tmp_root, korean_secret_file.name)
    korean_secret_file.unlink()
    # the other machine pushed v2 and it was pulled in: the .enc no longer equals the last synced content
    encrypted_file.write_bytes(secret_crypt.encrypt_bytes(KEY, b"v2 from elsewhere\n"))

    result = secret_crypt.encrypt_all(tmp_root, KEY)

    remote_copy = secret_crypt.remote_copy_path_for(korean_secret_file)
    assert result.deleted == []
    assert result.conflicts == [korean_secret_file]
    assert secret_crypt.decrypt_bytes(KEY, encrypted_file.read_bytes()) == b"v2 from elsewhere\n"
    assert remote_copy.read_bytes() == b"v2 from elsewhere\n"
    assert not korean_secret_file.exists()
    # the sync record stays, so the next run reports the same conflict instead of deleting
    assert korean_secret_file.name in secret_crypt.load_sync_state(korean_secret_file.parent)
    assert secret_crypt.encrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]
    assert secret_crypt.has_pending_secret_deletions(tmp_root) is True


@requires_openssl
def test_a_kept_encrypted_copy_is_restored_by_decrypt_and_the_conflict_is_gone(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    korean_secret_file.unlink()
    encrypted_copy_of(tmp_root, korean_secret_file.name).write_bytes(secret_crypt.encrypt_bytes(KEY, b"v2\n"))
    assert secret_crypt.encrypt_all(tmp_root, KEY).conflicts == [korean_secret_file]

    # take theirs: decrypt writes the file back
    assert secret_crypt.decrypt_all(tmp_root, KEY).restored == [korean_secret_file]

    result = secret_crypt.encrypt_all(tmp_root, KEY)
    assert (result.changed, result.conflicts, result.deleted) == ([], [], [])
    assert korean_secret_file.read_bytes() == b"v2\n"


@requires_openssl
def test_cli_encrypt_exits_3_with_the_deleted_here_but_changed_elsewhere_message(
    tmp_root, korean_secret_file, capsys, monkeypatch
):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    korean_secret_file.unlink()
    encrypted_copy_of(tmp_root, korean_secret_file.name).write_bytes(secret_crypt.encrypt_bytes(KEY, b"v2\n"))
    capsys.readouterr()

    assert secret_crypt.main(["encrypt"]) == 3

    assert (
        "prep/profile/secret/비밀 메모.md was deleted here but changed elsewhere; remote saved as 비밀 메모.md.remote"
        in capsys.readouterr().err
    )


@requires_openssl
def test_encrypt_stops_when_the_encrypted_copy_of_a_deleted_file_cannot_be_read(tmp_root, korean_secret_file):
    secret_crypt.encrypt_all(tmp_root, KEY)
    encrypted_file = encrypted_copy_of(tmp_root, korean_secret_file.name)
    korean_secret_file.unlink()
    encrypted_file.write_bytes(b"not an openssl file")

    with pytest.raises(secret_crypt.SecretCryptError, match="refusing to overwrite"):
        secret_crypt.encrypt_all(tmp_root, KEY)

    assert encrypted_file.is_file()


@requires_openssl
def test_has_pending_secret_deletions_sees_a_deleted_file_with_no_plaintext_left(tmp_root, korean_secret_file):
    assert secret_crypt.has_pending_secret_deletions(tmp_root) is False
    secret_crypt.encrypt_all(tmp_root, KEY)
    assert secret_crypt.has_pending_secret_deletions(tmp_root) is False

    korean_secret_file.unlink()

    assert secret_crypt.has_pending_secret_deletions(tmp_root) is True


@requires_openssl
def test_cli_encrypt_reports_the_deleted_copy(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    korean_secret_file.unlink()
    capsys.readouterr()

    assert secret_crypt.main(["encrypt"]) == 0

    assert "deleted: prep/profile/secret-encrypted/비밀 메모.md.enc" in capsys.readouterr().out


# ---------- CLI ----------


def test_cli_check_reports_state_as_json(tmp_root, korean_secret_file, capsys):
    exit_code = secret_crypt.main(["check"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert set(report) == {"openssl", "has_key", "secret_dirs", "plaintext_without_encrypted"}
    assert report["has_key"] is False
    assert report["secret_dirs"] == ["prep/profile/secret"]
    assert report["plaintext_without_encrypted"] == ["prep/profile/secret/비밀 메모.md"]


@requires_openssl
def test_cli_check_clears_plaintext_list_after_encrypt(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    capsys.readouterr()

    assert secret_crypt.main(["check"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["has_key"] is True
    assert report["plaintext_without_encrypted"] == []
    assert report["openssl"] == secret_crypt.find_openssl()


def test_cli_exits_2_without_key(tmp_root, korean_secret_file, capsys):
    assert secret_crypt.main(["encrypt"]) == 2
    assert "SPARRING_ENCRYPTION_KEY" in capsys.readouterr().err


def test_cli_exits_2_without_openssl(tmp_root, monkeypatch, capsys):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(secret_crypt, "find_openssl", lambda: None)

    assert secret_crypt.main(["decrypt"]) == 2
    assert "openssl" in capsys.readouterr().err.lower()


@requires_openssl
def test_cli_decrypt_exits_3_and_prints_conflict(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    korean_secret_file.write_text("local edit\n", encoding="utf-8")
    replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))
    capsys.readouterr()

    assert secret_crypt.main(["decrypt"]) == 3

    relative = "prep/profile/secret/비밀 메모.md"
    assert f"[secret_crypt] conflict: {relative} (remote saved as {relative}.remote)" in capsys.readouterr().err


@requires_openssl
def test_cli_exits_4_on_wrong_key(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    capsys.readouterr()

    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", "a-different-key")
    assert secret_crypt.main(["decrypt"]) == 4
    assert "encryption key does not match this repo" in capsys.readouterr().err
    assert secret_crypt.main(["encrypt"]) == 4


@requires_openssl
def test_cli_decrypt_local_ahead_exits_0_and_says_run_encrypt(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    korean_secret_file.write_text("local edit\n", encoding="utf-8")
    capsys.readouterr()

    assert secret_crypt.main(["decrypt"]) == 0

    captured = capsys.readouterr()
    assert "[secret_crypt] local ahead: prep/profile/secret/비밀 메모.md (run encrypt)" in captured.out
    assert "conflict" not in captured.err


@requires_openssl
def test_cli_encrypt_exits_3_on_newer_remote(tmp_root, korean_secret_file, capsys, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    assert secret_crypt.main(["encrypt"]) == 0
    replace_encrypted_content(tmp_root, "remote edit\n".encode("utf-8"))
    capsys.readouterr()

    assert secret_crypt.main(["encrypt"]) == 3

    relative = "prep/profile/secret/비밀 메모.md"
    assert f"[secret_crypt] conflict: {relative} (remote saved as {relative}.remote)" in capsys.readouterr().err
