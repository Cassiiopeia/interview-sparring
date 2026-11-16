"""Tests for common.py: repo root and prep dir resolution"""

from pathlib import Path

import common

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_repo_root_default_without_env(monkeypatch):
    monkeypatch.delenv("SPARRING_ROOT", raising=False)
    assert common.repo_root() == REPO_ROOT
    assert (common.repo_root() / "tutor" / "scripts" / "common.py").exists()


def test_repo_root_uses_env_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    assert common.repo_root() == tmp_path


def test_prep_dir_is_prep_under_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    assert common.prep_dir() == tmp_path / "prep"
