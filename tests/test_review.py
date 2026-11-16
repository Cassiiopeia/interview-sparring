"""Tests for review.py: add, grade and due scheduling, using a temp dir as the root"""

import re
from datetime import date, timedelta

import pytest

import review as review_module


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    # keep the real prep/ untouched
    monkeypatch.setenv("SPARRING_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def review(tmp_root):
    # cards_path() reads the env on each call, so setting it first is enough
    return review_module


def test_cards_path_is_prep_profile(review, tmp_root):
    assert review.cards_path() == tmp_root / "prep" / "profile" / "cards.md"


def test_cards_path_follows_root_env_on_each_call(review, tmp_root, tmp_path_factory, monkeypatch):
    other_root = tmp_path_factory.mktemp("other_root")
    monkeypatch.setenv("SPARRING_ROOT", str(other_root))
    assert review.cards_path() == other_root / "prep" / "profile" / "cards.md"


def test_columns_are_english(review):
    assert review.COLS == ["id", "area", "question", "source", "stage", "next_review", "history"]


def test_add_makes_id_from_area(review):
    review.cmd_add("story-01", "What is your first sentence?", "story-01 v1")
    review.cmd_add("story-01", "Second question", "story-01 v1")
    review.cmd_add("self-intro", "What do you do?", "self-intro v1")
    review.cmd_add("vocab", "What is a retention policy?", "vocab")
    ids = [card["id"] for card in review.load()]
    assert sorted(ids) == ["si-01", "story01-01", "story01-02", "voca-01"]


def test_add_creates_nested_cards_dir(review):
    # first save must work without prep/profile/
    review.cmd_add("self-intro", "question", "source")
    assert review.cards_path().exists()


def test_new_card_is_due_today(review):
    review.cmd_add("self-intro", "What is your first sentence?", "self-intro v1")
    (card,) = review.load()
    assert card["next_review"] == date.today().isoformat()
    assert card["stage"] == "0"


def test_grade_o_moves_up_and_x_resets(review):
    review.cmd_add("self-intro", "question", "source")
    review.cmd_grade("si-01", "o")
    (card,) = review.load()
    assert card["stage"] == "1"
    assert card["next_review"] == (date.today() + timedelta(days=3)).isoformat()

    review.cmd_grade("si-01", "x")
    (card,) = review.load()
    assert card["stage"] == "0"
    assert card["next_review"] == (date.today() + timedelta(days=1)).isoformat()


def test_grade_t_keeps_stage(review):
    review.cmd_add("self-intro", "question", "source")
    review.cmd_grade("si-01", "o")
    review.cmd_grade("si-01", "t")
    (card,) = review.load()
    assert card["stage"] == "1"


def test_pipe_in_question_is_escaped(review):
    review.cmd_add("facts", "Is it A | B?", "fact-01")
    (card,) = review.load()
    assert "|" not in card["question"]
    assert card["source"] == "fact-01"


def test_unknown_card_exits(review):
    with pytest.raises(SystemExit):
        review.cmd_grade("nope-01", "o")


def test_intervals_are_fixed(review):
    assert review.INTERVALS == [1, 3, 7, 21, 60]


def test_load_rejects_malformed_row(review):
    review.cmd_add("self-intro", "question", "source")
    path = review.cards_path()
    existing_text = path.read_text(encoding="utf-8")
    malformed_line_number = len(existing_text.splitlines()) + 1
    path.write_text(existing_text + "| broken | row |\n", encoding="utf-8")

    expected_message = rf"cards\.md line {malformed_line_number}: expected 7 cells, got 2"
    with pytest.raises(ValueError, match=expected_message):
        review.load()


def test_main_reports_malformed_row_as_one_line_error(review, monkeypatch, capsys):
    review.cmd_add("self-intro", "question", "source")
    path = review.cards_path()
    path.write_text(path.read_text(encoding="utf-8") + "| broken |\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["review.py", "due"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as exit_info:
        review.main()

    assert exit_info.value.code == 1
    assert re.search(r"^error: cards\.md line \d+: expected 7 cells, got 1$", capsys.readouterr().err, re.M)


def test_due_prints_one_due_card(review, capsys):
    review.cmd_add("self-intro", "What is your first sentence?", "self-intro v1")
    capsys.readouterr()

    review.cmd_due()

    output = capsys.readouterr().out
    assert "Due today: 1 card(s)" in output
    assert "[si-01] What is your first sentence?" in output
    assert "source: self-intro v1 | stage 0" in output
    assert "Grade: python3 tutor/scripts/review.py grade <id> o|t|x" in output


def test_due_prints_message_when_nothing_due(review, capsys):
    review.cmd_due()
    assert "No cards due today" in capsys.readouterr().out
