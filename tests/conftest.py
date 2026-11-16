"""Fixtures shared by the init and remote guard tests: temp repo roots, isolated git config, no network"""

import subprocess

import pytest

import remote_guard


@pytest.fixture
def tmp_root(tmp_path, tmp_path_factory, monkeypatch):
    # keep the real repo untouched; no key leaks in; global git config cannot change the results
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    monkeypatch.delenv("SPARRING_ENCRYPTION_KEY", raising=False)
    empty_git_config = tmp_path_factory.mktemp("gitconfig") / "config"
    empty_git_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_git_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return tmp_path


@pytest.fixture
def git_root(tmp_root):
    subprocess.run(["git", "init", "-q", str(tmp_root)], check=True)
    return tmp_root


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """No test may reach GitHub: visibility tests install their own fake"""

    def refuse(*arguments, **keyword_arguments):
        raise AssertionError("network access in a test")

    monkeypatch.setattr(remote_guard.urllib.request, "urlopen", refuse)
