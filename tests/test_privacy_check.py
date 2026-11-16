"""Tests for privacy_check.py: text scan, staged check, pre-commit hook and scan-all, using temp git repos"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import privacy_check
import privacy_patterns
import secret_crypt

REPO_ROOT = Path(__file__).resolve().parent.parent
KEY = "test-key-abc"

# crypto tests need a real openssl
requires_openssl = pytest.mark.skipif(
    secret_crypt.find_openssl() is None, reason="openssl is not installed"
)

# openssl enc -salt output starts with the Salted__ magic; the rest is irrelevant to these tests
SALTED_CONTENT = b"Salted__\x00\x01\x02\x03\x04\x05\x06\x07ciphertext"

# sample values are built from parts so this file passes its own privacy scan (hook and scan-all)
PHONE = "-".join(["010", "1234", "5678"])
EMAIL = "@".join(["jane.doe", "gmail.com"])
RESIDENT_ID = "-".join(["900101", "1234567"])

PLACEHOLDERS = [
    "010-0000-0000",
    "+82-10-0000-0000",
    "000000-0000000",
    "example@example.com",
    "name@example.org",
    "git@github.com:owner/repo.git",
]

GIT_TEST_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    # the developer's own git config (hooks path, signing) must not leak into the temp repos
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """Empty git repo (no commits) used as the repo root; no key leaks in from the developer's shell"""
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    monkeypatch.delenv("SPARRING_ENCRYPTION_KEY", raising=False)
    for name, value in GIT_TEST_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    git(tmp_path, "init", "-q")
    # same rules as the real .gitignore
    write(tmp_path, ".gitignore", ".env\n.env.*\n**/local/\n**/secret/\n")
    return tmp_path


def git(root, *arguments, check=True):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, encoding="utf-8", check=check
    )


def write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def stage(root, *relative_paths, force=False):
    git(root, "add", *(["-f"] if force else []), "--", *relative_paths)


def staged_names(root):
    return set(git(root, "diff", "--cached", "--name-only").stdout.splitlines())


def write_key_file(root, key=KEY):
    write(root, ".env", f"SPARRING_ENCRYPTION_KEY={key}\n")


SECRET_RELATIVE = "prep/profile/secret/a.md"
ENCRYPTED_RELATIVE = "prep/profile/secret-encrypted/a.md.enc"


# ---------- scan_text ----------


def test_scan_finds_korean_phone():
    findings = privacy_check.scan_text(PHONE)

    assert [finding.kind for finding in findings] == ["phone"]
    assert findings[0].line == 1


def test_scan_ignores_example_placeholder():
    for placeholder in PLACEHOLDERS:
        assert privacy_check.scan_text(placeholder) == [], placeholder
    # all placeholders on one line
    assert privacy_check.scan_text(" ".join(PLACEHOLDERS)) == []


@pytest.mark.parametrize(
    ("pieces", "separator"),
    [
        (["010", "1234", "5678"], ""),
        (["010", "1234", "5678"], " "),
        (["010", "1234", "5678"], "."),
        (["011", "123", "4567"], "-"),
        (["+82", "10", "1234", "5678"], "-"),
        (["+82", "1012345678"], ""),
        (["+1", "(415)", "555", "2671"], " "),
    ],
)
def test_scan_finds_phone_variants(pieces, separator):
    sample = separator.join(pieces)

    findings = privacy_check.scan_text(f"tel: {sample}.")

    assert [finding.kind for finding in findings] == ["phone"]
    assert sample not in findings[0].excerpt


def test_scan_finds_phone_followed_by_korean_text():
    assert [finding.kind for finding in privacy_check.scan_text(PHONE + "로 연락 주세요")] == ["phone"]


def test_scan_finds_email_and_resident_id():
    findings = privacy_check.scan_text(f"mail {EMAIL}\nid {RESIDENT_ID}")

    assert [(finding.kind, finding.line) for finding in findings] == [("email", 1), ("resident_id", 2)]


def test_scan_reports_line_numbers_and_each_occurrence():
    text = f"first\n\ncall {PHONE} or {PHONE}\n{EMAIL}"

    findings = privacy_check.scan_text(text)

    assert [(finding.kind, finding.line) for finding in findings] == [
        ("phone", 3),
        ("phone", 3),
        ("email", 4),
    ]


def test_scan_masks_the_middle_of_every_excerpt():
    findings = privacy_check.scan_text(f"{PHONE}\n{RESIDENT_ID}\n{EMAIL}")

    assert [finding.excerpt for finding in findings] == ["010-****-5678", "******-*******", "j***@***.com"]


def test_scan_does_not_report_a_resident_id_as_phone_too():
    resident_id_starting_like_a_phone = "-".join(["010101", "1234567"])

    findings = privacy_check.scan_text(resident_id_starting_like_a_phone)

    assert [finding.kind for finding in findings] == ["resident_id"]


@pytest.mark.parametrize(
    "text",
    [
        # digits inside hashes and longer numbers are not phone numbers
        "deadbeef" + "".join(["010", "1234", "5678"]) + "cafe",
        "2" + "".join(["010", "1234", "5678"]) + "9",
        "".join(["010", "123456789"]),
        "1" + RESIDENT_ID,
        # things that only look similar
        "version 1.2.3 on 2026-11-16 at 10:30-11:45",
        "010-xxxx-xxxx",
        "user@localhost and a@b",
        "",
    ],
)
def test_scan_ignores_lookalikes(text):
    assert privacy_check.scan_text(text) == []


# ---------- check_staged ----------


def test_blocks_staged_secret_plaintext(git_repo):
    write(git_repo, SECRET_RELATIVE, f"phone {PHONE}\n")
    stage(git_repo, SECRET_RELATIVE, force=True)

    reasons = privacy_check.check_staged(git_repo)

    assert len(reasons) == 1
    assert SECRET_RELATIVE in reasons[0]
    # the file is reported, never read: its content stays out of the output
    assert "010" not in reasons[0]


def test_check_staged_blocks_staged_key_files_and_local_folder(git_repo):
    write_key_file(git_repo)
    write(git_repo, ".env.local", "KEY=1\n")
    write(git_repo, "config/.env.production", "KEY=2\n")
    write(git_repo, "prep/local/notes.md", "private\n")
    stage(git_repo, ".env", ".env.local", "config/.env.production", "prep/local/notes.md", force=True)

    reasons = privacy_check.check_staged(git_repo)

    assert len(reasons) == 4
    for blocked in (".env:", ".env.local", "config/.env.production", "prep/local/notes.md"):
        assert any(blocked in reason for reason in reasons), blocked


def test_check_staged_does_not_mistake_similar_names_for_key_files(git_repo):
    write(git_repo, ".envrc", "use nix\n")
    write(git_repo, "docs/environment.md", "text\n")
    stage(git_repo, ".envrc", "docs/environment.md")

    assert privacy_check.check_staged(git_repo) == []


def test_check_staged_flags_personal_data_in_any_staged_file(git_repo):
    write(git_repo, "README.md", f"contact: {EMAIL}\n")
    write(git_repo, "tutor/notes.txt", "clean\n")
    stage(git_repo, "README.md", "tutor/notes.txt")

    reasons = privacy_check.check_staged(git_repo)

    assert reasons == ["README.md:1: email j***@***.com"]


def test_check_staged_reads_the_staged_version_not_the_working_copy(git_repo):
    write(git_repo, "README.md", f"call {PHONE}\n")
    stage(git_repo, "README.md")
    # the working copy was cleaned afterwards, but the index still holds the number
    write(git_repo, "README.md", "clean\n")
    assert len(privacy_check.check_staged(git_repo)) == 1

    # and the other way round: a dirty working copy that is not staged does not matter
    stage(git_repo, "README.md")
    write(git_repo, "README.md", f"call {PHONE}\n")
    assert privacy_check.check_staged(git_repo) == []


def test_check_staged_allows_placeholders_in_example_folder(git_repo):
    write(git_repo, "example/en-job/prep/profile.md", "\n".join(PLACEHOLDERS) + "\n")
    stage(git_repo, "example/en-job/prep/profile.md")

    assert privacy_check.check_staged(git_repo) == []


def test_check_staged_blocks_real_looking_numbers_in_example_folder(git_repo):
    write(git_repo, "example/en-job/prep/profile.md", f"phone: {PHONE}\n")
    stage(git_repo, "example/en-job/prep/profile.md")

    assert privacy_check.check_staged(git_repo) == ["example/en-job/prep/profile.md:1: phone 010-****-5678"]


def test_check_staged_skips_encrypted_and_binary_files(git_repo):
    # (an encrypted file may hold anything: only its header is checked)
    write(git_repo, ENCRYPTED_RELATIVE, SALTED_CONTENT + PHONE.encode("utf-8"))
    write(git_repo, "assets/logo.png", b"\x89PNG\0\0" + PHONE.encode("utf-8"))
    stage(git_repo, ENCRYPTED_RELATIVE, "assets/logo.png")

    assert privacy_check.check_staged(git_repo) == []


def test_check_staged_ignores_deletions(git_repo):
    write(git_repo, SECRET_RELATIVE, "leaked once\n")
    stage(git_repo, SECRET_RELATIVE, force=True)
    git(git_repo, "commit", "-q", "-m", "leak")
    git(git_repo, "rm", "-q", "--cached", "--", SECRET_RELATIVE)

    # removing a leaked file from the index is the fix, not a violation
    assert privacy_check.check_staged(git_repo) == []


def test_check_staged_handles_korean_file_names(git_repo):
    write(git_repo, "prep/자기소개.md", f"{EMAIL}\n")
    stage(git_repo, "prep/자기소개.md")

    assert len(privacy_check.check_staged(git_repo)) == 1


# ---------- run_hook ----------


def test_hook_blocks_when_key_missing(git_repo, capsys):
    write(git_repo, SECRET_RELATIVE, "private\n")

    assert privacy_check.run_hook(git_repo) == 1

    error_output = capsys.readouterr().err
    assert "no encryption key" in error_output
    assert "/spar init" in error_output
    assert "SPARRING_ENCRYPTION_KEY" in error_output
    assert not (git_repo / ENCRYPTED_RELATIVE).exists()


@requires_openssl
def test_hook_encrypts_and_stages(git_repo):
    write_key_file(git_repo)
    write(git_repo, SECRET_RELATIVE, f"phone {PHONE}\n")

    assert privacy_check.run_hook(git_repo) == 0

    names = staged_names(git_repo)
    assert ENCRYPTED_RELATIVE in names
    assert ".sparring-keycheck.enc" in names
    # plaintext never reaches the index, and personal data inside secret/ is not scanned
    assert SECRET_RELATIVE not in names


@requires_openssl
def test_hook_encrypts_with_key_from_environment(git_repo, monkeypatch):
    monkeypatch.setenv("SPARRING_ENCRYPTION_KEY", KEY)
    write(git_repo, SECRET_RELATIVE, "private\n")

    assert privacy_check.run_hook(git_repo) == 0
    assert ENCRYPTED_RELATIVE in staged_names(git_repo)


def test_hook_passes_without_secret_files_and_without_key(git_repo):
    write(git_repo, "README.md", "clean\n")
    stage(git_repo, "README.md")

    assert privacy_check.run_hook(git_repo) == 0


def test_hook_ignores_junk_inside_secret_folder(git_repo):
    # nothing encryptable (OS junk, conflict copies) means no key is needed
    write(git_repo, "prep/profile/secret/.DS_Store", "x")
    write(git_repo, "prep/profile/secret/a.md.remote", "x")

    assert privacy_check.run_hook(git_repo) == 0


@requires_openssl
def test_hook_blocks_on_conflict_and_points_to_decrypt(git_repo, capsys):
    write_key_file(git_repo)
    secret_file = write(git_repo, SECRET_RELATIVE, "v1\n")
    assert privacy_check.run_hook(git_repo) == 0
    # both sides changed since the last sync: a different .enc arrives (pull), and a local edit
    (git_repo / ENCRYPTED_RELATIVE).write_bytes(secret_crypt.encrypt_bytes(KEY, b"remote edit\n"))
    secret_file.write_text("local edit\n", encoding="utf-8")
    capsys.readouterr()

    assert privacy_check.run_hook(git_repo) == 1

    error_output = capsys.readouterr().err
    assert "python3 tutor/scripts/secret_crypt.py decrypt" in error_output
    assert "a.md.remote" in error_output
    assert secret_file.read_text(encoding="utf-8") == "local edit\n"


@requires_openssl
def test_hook_blocks_on_wrong_key(git_repo, capsys):
    write_key_file(git_repo)
    write(git_repo, SECRET_RELATIVE, "v1\n")
    assert privacy_check.run_hook(git_repo) == 0
    write_key_file(git_repo, key="another-key")
    write(git_repo, SECRET_RELATIVE, "v2\n")
    capsys.readouterr()

    assert privacy_check.run_hook(git_repo) == 1

    error_output = capsys.readouterr().err
    assert "does not match this repo" in error_output
    assert "python3 tutor/scripts/secret_crypt.py decrypt" in error_output


def test_hook_blocks_without_openssl(git_repo, monkeypatch, capsys):
    write_key_file(git_repo)
    write(git_repo, SECRET_RELATIVE, "private\n")
    monkeypatch.setattr(privacy_check, "find_openssl", lambda: None)

    assert privacy_check.run_hook(git_repo) == 1
    assert "openssl not found" in capsys.readouterr().err


def test_hook_blocks_personal_data_and_prints_only_masked_text(git_repo, capsys):
    write(git_repo, "README.md", f"call {PHONE}\n")
    stage(git_repo, "README.md")

    assert privacy_check.run_hook(git_repo) == 1

    error_output = capsys.readouterr().err
    assert "README.md:1: phone 010-****-5678" in error_output
    assert PHONE not in error_output
    assert "1234" not in error_output


@requires_openssl
def test_hook_blocks_force_added_secret_plaintext_even_with_key(git_repo, capsys):
    write_key_file(git_repo)
    write(git_repo, SECRET_RELATIVE, "private\n")
    stage(git_repo, SECRET_RELATIVE, force=True)

    assert privacy_check.run_hook(git_repo) == 1
    assert SECRET_RELATIVE in capsys.readouterr().err


def test_hook_blocks_outside_a_git_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert privacy_check.run_hook(tmp_path) == 1
    assert "git" in capsys.readouterr().err


# ---------- the hook stages only .enc files ----------

PLAINTEXT_IN_MIRROR_RELATIVE = "prep/profile/secret-encrypted/notes.md"
PLAINTEXT_IN_OTHER_MIRROR_RELATIVE = "prep/x/secret-encrypted/notes.md"


@requires_openssl
def test_hook_never_stages_plaintext_next_to_the_encrypted_copies(git_repo):
    write_key_file(git_repo)
    write(git_repo, SECRET_RELATIVE, "private\n")
    # plaintext (and junk) that happens to sit in secret-encrypted/ folders must stay unstaged
    write(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE, "plaintext inside the mirror\n")
    write(git_repo, PLAINTEXT_IN_OTHER_MIRROR_RELATIVE, "plaintext in another mirror\n")
    write(git_repo, "prep/profile/secret-encrypted/.DS_Store", "junk")

    assert privacy_check.run_hook(git_repo) == 0

    names = staged_names(git_repo)
    assert ENCRYPTED_RELATIVE in names
    assert ".sparring-keycheck.enc" in names
    assert all(name.endswith(".enc") for name in names), names


def test_hook_blocks_force_staged_plaintext_in_encrypted_folder(git_repo, capsys):
    write(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE, "plaintext inside the mirror\n")
    stage(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE)

    reasons = privacy_check.check_staged(git_repo)
    assert len(reasons) == 1
    assert PLAINTEXT_IN_MIRROR_RELATIVE in reasons[0]

    assert privacy_check.run_hook(git_repo) == 1
    assert "only .enc files" in capsys.readouterr().err


def test_scan_all_reports_tracked_plaintext_in_encrypted_folder(git_repo, capsys):
    write(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE, "plaintext inside the mirror\n")
    stage(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE)

    assert privacy_check.main(["scan-all"]) == 1
    assert PLAINTEXT_IN_MIRROR_RELATIVE in capsys.readouterr().err


def test_hook_restages_encrypted_copies_without_any_plaintext(git_repo):
    # a .enc fixed by hand or pulled, no secret/ files and no key: it must still ride along
    write(git_repo, ENCRYPTED_RELATIVE, SALTED_CONTENT)
    write(git_repo, ".sparring-keycheck.enc", SALTED_CONTENT)
    write(git_repo, PLAINTEXT_IN_MIRROR_RELATIVE, "plaintext inside the mirror\n")

    assert privacy_check.run_hook(git_repo) == 0

    assert staged_names(git_repo) == {ENCRYPTED_RELATIVE, ".sparring-keycheck.enc"}


def test_hook_stages_the_deletion_of_a_tracked_encrypted_copy(git_repo):
    write(git_repo, ENCRYPTED_RELATIVE, SALTED_CONTENT)
    write(git_repo, "prep/profile/secret-encrypted/odd [1].md.enc", SALTED_CONTENT)
    stage(git_repo, ENCRYPTED_RELATIVE, "prep/profile/secret-encrypted/odd [1].md.enc")
    git(git_repo, "commit", "-q", "-m", "encrypted copies")
    (git_repo / ENCRYPTED_RELATIVE).unlink()
    (git_repo / "prep/profile/secret-encrypted/odd [1].md.enc").unlink()

    assert privacy_check.run_hook(git_repo) == 0

    deletions = git(git_repo, "diff", "--cached", "--name-status").stdout.splitlines()
    assert sorted(deletions) == sorted(
        [f"D\t{ENCRYPTED_RELATIVE}", "D\tprep/profile/secret-encrypted/odd [1].md.enc"]
    )


def test_check_staged_blocks_a_enc_file_without_the_openssl_header(git_repo):
    write(git_repo, ENCRYPTED_RELATIVE, b"plain text pretending to be encrypted")
    write(git_repo, ".sparring-keycheck.enc", b"not salted either")
    write(git_repo, "prep/other/secret-encrypted/ok.md.enc", SALTED_CONTENT)
    stage(git_repo, ENCRYPTED_RELATIVE, ".sparring-keycheck.enc", "prep/other/secret-encrypted/ok.md.enc")

    reasons = privacy_check.check_staged(git_repo)

    assert len(reasons) == 2
    assert all("Salted__" in reason for reason in reasons)
    assert any(ENCRYPTED_RELATIVE in reason for reason in reasons)
    assert any(".sparring-keycheck.enc" in reason for reason in reasons)


def test_check_staged_blocks_an_empty_enc_file(git_repo):
    write(git_repo, ENCRYPTED_RELATIVE, b"")
    stage(git_repo, ENCRYPTED_RELATIVE)

    assert len(privacy_check.check_staged(git_repo)) == 1


# ---------- masking and the module split ----------


def test_mask_email_keeps_first_character_and_top_level_domain_only():
    short_email = "@".join(["jo", "mail.dev"])

    assert privacy_patterns.mask_email(EMAIL) == "j***@***.com"
    assert privacy_patterns.mask_email(short_email) == "j***@***.dev"


def test_privacy_check_re_exports_the_scan_interface():
    assert privacy_check.scan_text is privacy_patterns.scan_text
    assert privacy_check.Finding is privacy_patterns.Finding


# ---------- the hook file ----------


def test_hook_file_is_posix_sh_with_python_fallback():
    hook_file = REPO_ROOT / ".githooks" / "pre-commit"
    content = hook_file.read_bytes().decode("utf-8")

    assert content.startswith("#!/bin/sh\n")
    assert "\r" not in content
    # real execution is probed (a Windows Store python3 stub exists on PATH but does not run)
    assert 'if python3 -c "import sys" >/dev/null 2>&1; then' in content
    assert 'elif py -3 -c "import sys" >/dev/null 2>&1; then' in content
    assert "exec python3 tutor/scripts/privacy_check.py hook" in content
    assert "exec py -3 tutor/scripts/privacy_check.py hook" in content
    assert "command -v" not in content
    assert "Python 3 not found; commit blocked" in content
    # runs from the repo root whatever the current folder is
    assert "git rev-parse --show-toplevel" in content


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="not a git checkout")
def test_hook_file_is_executable_in_git():
    listing = git(REPO_ROOT, "ls-files", "-s", "--", ".githooks/pre-commit").stdout

    assert listing.startswith("100755 ")


def install_hook_file_into(root):
    (root / ".githooks").mkdir()
    # copy2 keeps the executable bit
    shutil.copy2(REPO_ROOT / ".githooks" / "pre-commit", root / ".githooks" / "pre-commit")


def install_engine_into(root):
    """Copy the scripts and the hook into a temp repo and switch hooks on, like init does"""
    shutil.copytree(
        REPO_ROOT / "tutor" / "scripts",
        root / "tutor" / "scripts",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    install_hook_file_into(root)
    git(root, "config", "core.hooksPath", ".githooks")


@pytest.mark.skipif(shutil.which("sh") is None, reason="no POSIX sh")
@requires_openssl
def test_hook_file_end_to_end_through_git_commit(git_repo):
    install_engine_into(git_repo)
    write_key_file(git_repo)
    write(git_repo, "README.md", "clean\n")
    write(git_repo, SECRET_RELATIVE, f"phone {PHONE}\n")
    stage(git_repo, "README.md", "tutor", ".githooks")

    # secret/ > encrypted and committed, plaintext stays out
    first_commit = git(git_repo, "commit", "-q", "-m", "first", check=False)
    assert first_commit.returncode == 0, first_commit.stderr
    committed = set(git(git_repo, "show", "--name-only", "--format=", "HEAD").stdout.splitlines())
    assert ENCRYPTED_RELATIVE in committed
    assert ".sparring-keycheck.enc" in committed
    assert SECRET_RELATIVE not in committed

    # personal data in a staged file > commit is refused
    write(git_repo, "README.md", f"call {PHONE}\n")
    stage(git_repo, "README.md")
    second_commit = git(git_repo, "commit", "-q", "-m", "second", check=False)
    assert second_commit.returncode != 0
    assert "010-****-5678" in second_commit.stderr
    assert PHONE not in second_commit.stderr
    assert git(git_repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"


def install_fake_command(bin_directory, name, script_body):
    bin_directory.mkdir(exist_ok=True)
    fake_command = bin_directory / name
    fake_command.write_text("#!/bin/sh\n" + script_body, encoding="utf-8")
    fake_command.chmod(0o755)


def run_hook_file_with_fake_commands(root, bin_directory):
    """Run .githooks/pre-commit with the fake commands first on PATH (a failing stub shadows the real python3)"""
    environment = {**os.environ, "PATH": str(bin_directory) + os.pathsep + os.environ["PATH"]}
    return subprocess.run(
        ["sh", str(root / ".githooks" / "pre-commit")],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.mark.skipif(shutil.which("sh") is None, reason="no POSIX sh")
def test_hook_file_blocks_when_no_python_actually_runs(git_repo):
    install_hook_file_into(git_repo)
    bin_directory = git_repo / "fake-bin"
    # present on PATH but not runnable (the Windows Store stub case)
    install_fake_command(bin_directory, "python3", "exit 9\n")
    install_fake_command(bin_directory, "py", "exit 9\n")

    completed = run_hook_file_with_fake_commands(git_repo, bin_directory)

    assert completed.returncode == 1
    assert "interview-sparring: Python 3 not found; commit blocked" in completed.stderr


@pytest.mark.skipif(shutil.which("sh") is None, reason="no POSIX sh")
def test_hook_file_falls_back_to_the_py_launcher_when_python3_does_not_run(git_repo):
    install_hook_file_into(git_repo)
    bin_directory = git_repo / "fake-bin"
    install_fake_command(bin_directory, "python3", "exit 9\n")
    # probe call (-c) succeeds, the real call is recorded
    install_fake_command(
        bin_directory,
        "py",
        'if [ "$2" = "-c" ]; then exit 0; fi\necho "$@" >> "$(dirname "$0")/py-calls.txt"\nexit 0\n',
    )

    completed = run_hook_file_with_fake_commands(git_repo, bin_directory)

    assert completed.returncode == 0, completed.stderr
    assert (bin_directory / "py-calls.txt").read_text(encoding="utf-8").splitlines() == [
        "-3 tutor/scripts/privacy_check.py hook"
    ]


# ---------- scan-all ----------


def commit_everything(root, message="snapshot"):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def test_scan_all_reports_tracked_and_untracked_files_and_skips_the_rest(git_repo, capsys):
    # tracked, then edited to hold personal data
    write(git_repo, "docs/tracked.md", "clean\n")
    # deleted from disk but still tracked: must not crash
    write(git_repo, "gone.md", "x\n")
    commit_everything(git_repo)
    write(git_repo, "docs/tracked.md", f"mail {EMAIL}\n")
    (git_repo / "gone.md").unlink()
    # untracked, not ignored
    write(git_repo, "notes.md", f"tel {PHONE}\n")
    # skipped: ignored folders, encrypted copies, binaries, placeholders
    write(git_repo, "prep/profile/secret/a.md", f"{PHONE}\n")
    write(git_repo, "prep/local/b.md", f"{PHONE}\n")
    write(git_repo, "x/a.enc", SALTED_CONTENT + PHONE.encode("utf-8"))
    write(git_repo, "x/bad.enc", b"plain text pretending to be encrypted")
    write(git_repo, "image.bin", b"\0" + PHONE.encode("utf-8"))
    write(git_repo, "example/en-job/prep/profile.md", "\n".join(PLACEHOLDERS) + "\n")

    assert privacy_check.main(["scan-all"]) == 1

    error_output = capsys.readouterr().err
    assert "docs/tracked.md:1: email j***@***.com" in error_output
    assert "notes.md:1: phone 010-****-5678" in error_output
    assert "x/bad.enc: not an openssl-encrypted file" in error_output
    assert PHONE not in error_output
    for skipped in ("profile/secret/a.md", "prep/local/b.md", "x/a.enc", "image.bin", "example/", "gone.md"):
        assert skipped not in error_output, skipped


def test_scan_all_returns_zero_when_clean(git_repo, capsys):
    write(git_repo, "README.md", "clean\n")
    write(git_repo, "example/en-job/prep/profile.md", "\n".join(PLACEHOLDERS) + "\n")

    assert privacy_check.main(["scan-all"]) == 0
    assert "clean" in capsys.readouterr().out


def test_scan_all_reports_a_tracked_secret_file_without_reading_it(git_repo, capsys):
    write(git_repo, SECRET_RELATIVE, f"{PHONE}\n")
    stage(git_repo, SECRET_RELATIVE, force=True)

    assert privacy_check.main(["scan-all"]) == 1

    error_output = capsys.readouterr().err
    assert SECRET_RELATIVE in error_output
    assert "phone" not in error_output


def test_cli_rejects_unknown_command(git_repo):
    with pytest.raises(SystemExit) as exit_info:
        privacy_check.main(["nope"])

    assert exit_info.value.code == 2


def test_cli_hook_runs_the_hook_on_the_repo_root(git_repo, capsys):
    write(git_repo, "README.md", f"call {PHONE}\n")
    stage(git_repo, "README.md")

    assert privacy_check.main(["hook"]) == 1
    assert "README.md:1: phone" in capsys.readouterr().err
