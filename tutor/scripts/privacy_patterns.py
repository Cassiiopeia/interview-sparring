"""Personal data patterns: what counts as sensitive, which values are placeholders, how excerpts are masked.

Detected: Korean mobile and international phone numbers, email addresses, resident registration numbers.
Placeholders pass: 010-0000-0000, 000000-0000000, anything@example.com.
Excerpts never contain the full match (phone: 01X-****-XXXX, resident id: all masked, email: j***@***.com).
"""

import re
from typing import Callable, NamedTuple

# placeholder phone: the last 7 digits are zero (010-0000-0000, 011-000-0000, +1 555 000 0000)
PLACEHOLDER_PHONE_ZERO_DIGITS = 7
# placeholder email: reserved example domains (RFC 2606)
PLACEHOLDER_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
# not a person: ssh clone URLs (git@github.com:owner/repo.git) and GitHub noreply addresses
NON_PERSONAL_EMAIL_LOCAL_PARTS = {"git"}
NON_PERSONAL_EMAIL_DOMAIN_SUFFIX = "users.noreply.github.com"

# phone excerpt: leading and trailing characters left visible
PHONE_VISIBLE_HEAD_CHARACTERS = 3
PHONE_VISIBLE_TAIL_CHARACTERS = 4
# email excerpt: fixed-length mask so the real length stays hidden
EMAIL_MASK = "***"


class Finding(NamedTuple):
    """kind: phone, email or resident_id / line: 1-based / excerpt: the match with its middle masked"""

    kind: str
    line: int
    excerpt: str


class SensitivePattern(NamedTuple):
    """regex finds candidates; is_placeholder(text) drops fake values; mask(text) makes the printable excerpt"""

    kind: str
    regex: re.Pattern
    is_placeholder: Callable[[str], bool]
    mask: Callable[[str], str]


# ---------- masking and placeholders ----------


def mask_middle(text, visible_head, visible_tail):
    """Keep the first/last characters, replace letters and digits in between with * (separators stay)"""
    masked_end = len(text) - visible_tail
    return "".join(
        "*" if visible_head <= index < masked_end and character.isalnum() else character
        for index, character in enumerate(text)
    )


def mask_phone(text):
    """First 3 and last 4 characters stay: 01X-XXXX-XXXX > 01X-****-XXXX"""
    return mask_middle(text, PHONE_VISIBLE_HEAD_CHARACTERS, PHONE_VISIBLE_TAIL_CHARACTERS)


def mask_resident_id(text):
    """Nothing stays visible: YYMMDD-NNNNNNN > ******-*******"""
    return mask_middle(text, 0, 0)


def mask_email(text):
    """First local-part character and the TLD stay: jane.doe@example.com > j***@***.com"""
    local_part, _, domain = text.rpartition("@")
    top_level_domain = domain.rpartition(".")[2]
    return f"{local_part[:1]}{EMAIL_MASK}@{EMAIL_MASK}.{top_level_domain}"


def keep_digits_only(text):
    return re.sub(r"\D", "", text)


def is_placeholder_phone(text):
    return keep_digits_only(text).endswith("0" * PLACEHOLDER_PHONE_ZERO_DIGITS)


def is_placeholder_resident_id(text):
    return set(keep_digits_only(text)) == {"0"}


def is_placeholder_email(text):
    local_part, _, domain = text.lower().rpartition("@")
    is_example_domain = any(
        domain == placeholder or domain.endswith("." + placeholder) for placeholder in PLACEHOLDER_EMAIL_DOMAINS
    )
    return (
        is_example_domain
        or local_part in NON_PERSONAL_EMAIL_LOCAL_PARTS
        or domain.endswith(NON_PERSONAL_EMAIL_DOMAIN_SUFFIX)
    )


# ---------- patterns ----------

# (?<![0-9A-Za-z]) / (?![0-9A-Za-z]): digits inside hashes, ids and longer numbers are not a number of their own
# (Korean letters may touch the number: "<number>로 연락" is still found)
# one list on purpose: resident_id first so a match is never reported twice
SENSITIVE_PATTERNS = [
    # resident registration number: YYMMDD-NNNNNNN (6 digits - 7 digits)
    SensitivePattern(
        "resident_id",
        re.compile(r"(?<![0-9A-Za-z])\d{6}-\d{7}(?![0-9A-Za-z])"),
        is_placeholder_resident_id,
        mask_resident_id,
    ),
    # Korean mobile: 01X-XXXX-XXXX, 01XXXXXXXXXX, 01X-XXX-XXXX (separator - . or space)
    SensitivePattern(
        "phone",
        re.compile(r"(?<![0-9A-Za-z])01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?![0-9A-Za-z])"),
        is_placeholder_phone,
        mask_phone,
    ),
    # international: +<country code and number>, 10-15 digits, separators " .-()" allowed between digits
    SensitivePattern(
        "phone",
        re.compile(r"(?<![0-9A-Za-z+])\+\d(?:[ .()-]{0,2}\d){9,14}(?![0-9A-Za-z])"),
        is_placeholder_phone,
        mask_phone,
    ),
    SensitivePattern(
        "email",
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
        is_placeholder_email,
        mask_email,
    ),
]


def overlaps_any(span, taken_spans):
    start, end = span
    return any(start < taken_end and taken_start < end for taken_start, taken_end in taken_spans)


def scan_text(text: str) -> list[Finding]:
    """Personal data in text > findings (placeholders pass; excerpts are masked, never the full value)"""
    findings = []
    for line_number, line in enumerate(text.split("\n"), start=1):
        taken_spans = []
        for pattern in SENSITIVE_PATTERNS:
            for match in pattern.regex.finditer(line):
                if overlaps_any(match.span(), taken_spans):
                    continue
                # (placeholders reserve their span too: no second pattern re-reads them)
                taken_spans.append(match.span())
                if not pattern.is_placeholder(match.group()):
                    findings.append(Finding(pattern.kind, line_number, pattern.mask(match.group())))
    return findings
