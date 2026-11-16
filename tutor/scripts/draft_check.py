#!/usr/bin/env python3
"""Draft check: warnings on the tutor's own draft answers before it shows them (spec: the tutor's drafts are not trusted).

    python3 tutor/scripts/draft_check.py --lang ko [FILE]     FILE omitted or '-': read the draft from stdin

Three kinds of warning, one line each (kind, sentence number, excerpt):
    banned_phrase     a pattern from tutor/rules/language/<lang>.patterns.txt (written style, hedging, cliché)
    long_sentence     over the language cap (ko 80 characters, en and others 30 words): hard to say in one breath
    repeated_ending   three sentences in a row end the same way (uniform rhythm reads as machine-written)
Language: an exact pack first, then the primary subtag (ko-KR > ko), else en with a warning on stderr.
Warnings only: the final call is the user reading the draft aloud.
Exit codes: 0 no warnings, 1 warnings printed, 2 path-like language, invalid pattern or unreadable input.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

import common

LANGUAGE_PACK_DIR = Path(__file__).resolve().parent.parent / "rules" / "language"
PATTERN_FILE_SUFFIX = ".patterns.txt"
COMMENT_PREFIX = "#"
# pack used when no pack matches the language (settings.json language without its own pack)
FALLBACK_LANGUAGE = "en"
# a language code never names a path: these would leave the pack folder
PATH_LIKE_FRAGMENTS = ("/", "\\", "..")


class LengthRule(NamedTuple):
    """unit: characters or words / maximum: allowed length / ending_characters: 0 = the ending is the last word"""

    unit: str
    maximum: int
    ending_characters: int


# ko: 80 characters, ending = last 4 characters (했습니다 vs 었습니다) / en: 30 words, ending = last word
LENGTH_RULES = {
    "ko": LengthRule("characters", 80, 4),
    "en": LengthRule("words", 30, 0),
}
DEFAULT_LENGTH_RULE = LengthRule("words", 30, 0)

# same ending this many times in a row > warning
REPEATED_ENDING_RUN = 3
# long sentence excerpt: first characters only
EXCERPT_CHARACTERS = 40

SENTENCE_BREAK_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")
# list markers and slot labels ("- ", "1. ", "> ", "[Conclusion] ") are not part of the spoken sentence
LINE_PREFIX_PATTERN = re.compile(r"^\s*(?:(?:[-*>]+|\d+[.)])\s+)?(?:\[[^\]]*\]\s*)?")
TRAILING_PUNCTUATION = ".!?。！？\"'”’)…"

EXIT_CLEAN = 0
EXIT_WARNINGS = 1
EXIT_USAGE = 2


class Warning(NamedTuple):  # noqa: A001  (the interface name in the spec)
    """kind: banned_phrase, long_sentence or repeated_ending / sentence_index: 1-based / excerpt: the part that triggered it"""

    kind: str
    sentence_index: int
    excerpt: str


class LanguagePackError(Exception):
    """Language code that looks like a path, or a pattern file that cannot be used"""


def pattern_file_path(language):
    return LANGUAGE_PACK_DIR / f"{language}{PATTERN_FILE_SUFFIX}"


def resolve_language(language):
    """Language code > (pack code, fell back to en): exact pack > primary subtag (ko-KR > ko) > en"""
    if not language or any(fragment in language for fragment in PATH_LIKE_FRAGMENTS):
        raise LanguagePackError(f"language must be a code such as en or ko-KR, got {language!r}")
    primary_subtag = re.split(r"[-_]", language)[0].lower()
    # (lowercase: pack files and LENGTH_RULES keys are lowercase, and macOS/Windows match file names in any case)
    for candidate in (language.lower(), primary_subtag):
        if pattern_file_path(candidate).is_file():
            return candidate, False
    return FALLBACK_LANGUAGE, True


def load_patterns(pattern_file):
    """Pattern file > compiled regexes (one per line, '#' comments and blank lines skipped, case-insensitive)"""
    pattern_file = Path(pattern_file)
    patterns = []
    for line_number, line in enumerate(pattern_file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIX):
            continue
        try:
            patterns.append(re.compile(stripped, re.IGNORECASE))
        except re.error as error:
            raise LanguagePackError(f"{pattern_file.name}:{line_number}: invalid pattern {stripped!r}: {error}") from error
    return patterns


def split_sentences(text):
    """Draft text > spoken sentences in order (per line, list markers and slot labels removed)"""
    sentences = []
    for line in text.splitlines():
        spoken_line = LINE_PREFIX_PATTERN.sub("", line).strip()
        if not spoken_line:
            continue
        sentences.extend(part.strip() for part in SENTENCE_BREAK_PATTERN.split(spoken_line) if part.strip())
    return sentences


def measure_length(sentence, length_rule):
    return len(sentence) if length_rule.unit == "characters" else len(sentence.split())


def find_ending(sentence, length_rule):
    """Sentence > its ending (last N characters, or last word) without trailing punctuation, lowercased"""
    core = sentence.rstrip(TRAILING_PUNCTUATION).strip()
    if length_rule.ending_characters:
        return core[-length_rule.ending_characters :]
    words = core.split()
    return words[-1].lower() if words else ""


def shorten(sentence):
    return sentence if len(sentence) <= EXCERPT_CHARACTERS else sentence[:EXCERPT_CHARACTERS] + "..."


def check(text: str, lang: str) -> list[Warning]:
    """Draft > warnings in sentence order: banned phrases, then length, then a third same ending in a row"""
    pack_language, _ = resolve_language(lang)
    patterns = load_patterns(pattern_file_path(pack_language))
    length_rule = LENGTH_RULES.get(pack_language, DEFAULT_LENGTH_RULE)
    warnings = []
    previous_ending, run_length = None, 0
    for sentence_index, sentence in enumerate(split_sentences(text), start=1):
        # banned phrases (every pattern that hits)
        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                warnings.append(Warning("banned_phrase", sentence_index, match.group()))
        # length cap
        if measure_length(sentence, length_rule) > length_rule.maximum:
            warnings.append(Warning("long_sentence", sentence_index, shorten(sentence)))
        # same ending run (warned once, on the third sentence)
        ending = find_ending(sentence, length_rule)
        run_length = run_length + 1 if ending and ending == previous_ending else 1
        previous_ending = ending
        if run_length == REPEATED_ENDING_RUN:
            warnings.append(Warning("repeated_ending", sentence_index, ending))
    return warnings


def read_draft(source):
    if source in (None, "-"):
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8-sig")


def build_parser():
    parser = argparse.ArgumentParser(description="Warn about banned phrases, long sentences and repeated endings in a draft")
    parser.add_argument("--lang", required=True, help="language pack code, e.g. en or ko")
    parser.add_argument("file", nargs="?", help="draft file (omit or '-' for stdin)")
    return parser


def main(argv=None):
    common.use_utf8_console()
    arguments = build_parser().parse_args(argv)
    try:
        pack_language, has_fallen_back = resolve_language(arguments.lang)
        if has_fallen_back:
            print(f"[draft check] no language pack for {arguments.lang!r}: falling back to {pack_language}", file=sys.stderr)
        warnings = check(read_draft(arguments.file), arguments.lang)
    except (LanguagePackError, OSError, UnicodeDecodeError) as error:
        print(f"[draft check] {error}", file=sys.stderr)
        return EXIT_USAGE
    for warning in warnings:
        print(f"{warning.kind}\tsentence {warning.sentence_index}\t{warning.excerpt}")
    if not warnings:
        print("no warnings: read it aloud to decide")
        return EXIT_CLEAN
    return EXIT_WARNINGS


if __name__ == "__main__":
    sys.exit(main())
