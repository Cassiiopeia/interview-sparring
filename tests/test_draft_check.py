"""Tests for draft_check.py: warnings on the tutor's own drafts (banned phrases, long sentences, repeated endings).

Uses the shipped language packs in tutor/rules/language/*.patterns.txt."""

import pytest

import draft_check


def kinds_of(warnings):
    return [warning.kind for warning in warnings]


# ---------- banned phrases ----------


def test_flags_banned_ko_phrase():
    warnings = draft_check.check("저는 빠진 값을 따로 표시함으로써 문제를 줄였습니다.", "ko")

    assert kinds_of(warnings) == ["banned_phrase"]
    assert warnings[0].sentence_index == 1
    assert "함으로써" in warnings[0].excerpt


def test_flags_banned_en_phrase_in_any_letter_case():
    warnings = draft_check.check("I am Passionate About security. I fixed the login bug.", "en")

    assert kinds_of(warnings) == ["banned_phrase"]
    assert warnings[0].sentence_index == 1


def test_flags_the_ko_hedge_ending():
    warnings = draft_check.check("그때 처음 센서 기록을 봤던 것 같습니다.", "ko")

    assert "banned_phrase" in kinds_of(warnings)


# ---------- sentence length ----------


def test_flags_long_sentence():
    long_korean = "가" * 81 + "입니다."
    long_english = " ".join(["word"] * 31) + "."

    assert kinds_of(draft_check.check(long_korean, "ko")) == ["long_sentence"]
    assert kinds_of(draft_check.check(long_english, "en")) == ["long_sentence"]


def test_sentences_at_the_cap_pass():
    korean_at_cap = "가" * 76 + "입니다."
    english_at_cap = " ".join(["word"] * 30) + "."

    assert len(korean_at_cap) == 80
    assert draft_check.check(korean_at_cap, "ko") == []
    assert draft_check.check(english_at_cap, "en") == []


# ---------- repeated endings ----------


def test_flags_three_same_endings():
    text = "센서 값을 모았습니다. 빠진 날을 정리했습니다. 비교표를 고쳤습니다. 기록을 남겼습니다."
    same_endings = "센서 값을 확인했습니다. 기준을 변경했습니다. 결과를 보고했습니다."

    assert "repeated_ending" not in kinds_of(draft_check.check(text, "ko"))
    warnings = draft_check.check(same_endings, "ko")
    assert kinds_of(warnings) == ["repeated_ending"]
    assert warnings[0].sentence_index == 3


def test_two_same_endings_pass():
    assert draft_check.check("센서 값을 확인했습니다. 기준을 변경했습니다. 그게 제 일입니다.", "ko") == []


# ---------- clean text and input handling ----------


def test_clean_text_has_no_warnings():
    korean = "저는 품질관리팀에서 일합니다. 센서 데이터로 불량 원인을 찾습니다. 그래서 이 일을 더 알고 싶습니다."
    english = "I work on delivery tracking. Last year I rebuilt our tracking cache. That is why I applied here."

    assert draft_check.check(korean, "ko") == []
    assert draft_check.check(english, "en") == []


def test_sentence_index_counts_across_lines():
    warnings = draft_check.check("First line is fine.\nSecond line is fine.\nI believe that it works.", "en")

    assert [warning.sentence_index for warning in warnings] == [3]


def test_region_subtag_resolves_to_the_primary_language():
    assert draft_check.resolve_language("ko-KR") == ("ko", False)
    assert kinds_of(draft_check.check("저는 빠진 값을 따로 표시함으로써 문제를 줄였습니다.", "ko-KR")) == ["banned_phrase"]


def test_unknown_language_falls_back_to_english():
    assert draft_check.resolve_language("xx") == ("en", True)
    assert kinds_of(draft_check.check("I am passionate about tracking.", "xx")) == ["banned_phrase"]


@pytest.mark.parametrize("language", ["../en", "en/x", "en\\x", ".."])
def test_path_like_language_is_refused(language):
    with pytest.raises(draft_check.LanguagePackError):
        draft_check.check("text", language)


def test_invalid_regex_names_the_file_and_line(tmp_path):
    pattern_file = tmp_path / "zz.patterns.txt"
    pattern_file.write_text("# comment\nfine\n(unclosed\n", encoding="utf-8")

    with pytest.raises(draft_check.LanguagePackError, match=r"zz\.patterns\.txt:3"):
        draft_check.load_patterns(pattern_file)


def test_pattern_file_skips_comments_and_blank_lines(tmp_path):
    pattern_file = tmp_path / "zz.patterns.txt"
    pattern_file.write_text("# comment\n\nforbidden\n", encoding="utf-8")

    patterns = draft_check.load_patterns(pattern_file)

    assert [pattern.pattern for pattern in patterns] == ["forbidden"]


def test_cli_exit_codes(tmp_path, capsys):
    clean_file = tmp_path / "clean.txt"
    clean_file.write_text("I fixed the login bug.", encoding="utf-8")
    flagged_file = tmp_path / "flagged.txt"
    flagged_file.write_text("In today's fast-paced world I fixed it.", encoding="utf-8")

    assert draft_check.main(["--lang", "en", str(clean_file)]) == draft_check.EXIT_CLEAN
    assert draft_check.main(["--lang", "en", str(flagged_file)]) == draft_check.EXIT_WARNINGS
    assert "banned_phrase" in capsys.readouterr().out
    capsys.readouterr()
    assert draft_check.main(["--lang", "xx", str(clean_file)]) == draft_check.EXIT_CLEAN
    assert "falling back to en" in capsys.readouterr().err
    assert draft_check.main(["--lang", "../en", str(clean_file)]) == draft_check.EXIT_USAGE


def test_language_code_is_lowercased_for_pack_and_length_rule():
    assert draft_check.resolve_language("KO") == ("ko", False)
    assert draft_check.resolve_language("Ko-kr") == ("ko", False)
    # (ko cap is 80 characters: 81 characters of one word must be flagged, which the en word cap would miss)
    assert kinds_of(draft_check.check("가" * 81 + "입니다.", "KO")) == ["long_sentence"]
