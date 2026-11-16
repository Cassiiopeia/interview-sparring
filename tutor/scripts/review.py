#!/usr/bin/env python3
"""Recall cards and review schedule: tracks when to ask each question again.

Cards hold the question and its source only, never the answer.

    python3 tutor/scripts/review.py due                          cards to review today
    python3 tutor/scripts/review.py add <area> "question" "source"   add a card
    python3 tutor/scripts/review.py grade <id> o|t|x             grade (o correct / t partial / x wrong)
    python3 tutor/scripts/review.py list [<area>]                list all cards
    python3 tutor/scripts/review.py stats                        summary
"""

import sys
from datetime import date, timedelta

import common


def cards_path():
    """Card store: prep/profile/cards.md (root re-resolved on every call)"""
    return common.prep_dir() / "profile" / "cards.md"


# days until next review per stage (one step up per correct answer)
INTERVALS = [1, 3, 7, 21, 60]
COLS = ["id", "area", "question", "source", "stage", "next_review", "history"]

HEADER = """# Recall cards

Weak spots, slipped phrasing and pressure questions from practice pile up here and come back on schedule.
**Never write the answer** — only the question and its source. Seeing the answer turns recall into rereading.

`stage` counts correct answers. Stage 0 -> 1 day, 1 -> 3 days, 2 -> 7 days, 3 -> 21 days, 4 -> 60 days until the next review.
A wrong answer resets it to 0. `area` is a free label such as a story, a question set, vocab or facts (e.g. story-01, vocab).

`tutor/scripts/review.py` reads and writes this table. Hand edits are fine, but keep the column count.

"""


def today():
    return date.today().isoformat()


def esc(text):
    """Keep the table intact: | > /, newline > space"""
    return str(text).replace("|", "/").replace("\n", " ").strip()


def load():
    path = cards_path()
    if not path.exists():
        return []
    cards = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        # fail loudly: a skipped row would vanish on the next save
        if len(cells) != len(COLS):
            raise ValueError(f"{path.name} line {line_number}: expected {len(COLS)} cells, got {len(cells)}")
        # skip header and separator rows
        if cells[0] in ("id", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        cards.append(dict(zip(COLS, cells)))
    return cards


def save(cards):
    cards.sort(key=lambda card: (card["next_review"], card["id"]))
    out = [HEADER, "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    for card in cards:
        out.append("| " + " | ".join(esc(card[col]) for col in COLS) + " |")
    out.append("")
    # first save may run before prep/profile/ exists
    path = cards_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


def prefix(area):
    """Area > card id prefix (story-01 > story01, self-intro > si, vocab > voca)"""
    parts = [part for part in area.replace("_", "-").split("-") if part]
    if len(parts) == 2 and parts[1].isdigit():
        return (parts[0] + parts[1]).lower()
    if len(parts) == 1:
        return parts[0][:4].lower() or "c"
    return "".join(part[0] for part in parts)[:4].lower() or "c"


def cmd_add(area, question, source):
    cards = load()
    id_prefix = prefix(area)
    next_number = 1 + max(
        [int(card["id"].rsplit("-", 1)[1]) for card in cards if card["id"].startswith(id_prefix + "-")] or [0]
    )
    card_id = f"{id_prefix}-{next_number:02d}"
    cards.append({
        "id": card_id, "area": area, "question": question, "source": source,
        "stage": "0", "next_review": today(), "history": "",
    })
    save(cards)
    print(f"[+] {card_id}  {question}")
    print(f"    source: {source} | next review: today")


def cmd_grade(card_id, mark):
    if mark not in ("o", "t", "x"):
        print("grade must be one of o (correct) / t (partial) / x (wrong).", file=sys.stderr)
        raise SystemExit(2)
    cards = load()
    for card in cards:
        if card["id"] != card_id:
            continue
        stage = int(card["stage"] or 0)
        # o: one stage up / t: same stage, half interval / x: back to stage 0
        if mark == "o":
            stage = min(stage + 1, len(INTERVALS) - 1)
            days = INTERVALS[stage]
        elif mark == "t":
            days = max(1, INTERVALS[stage] // 2)
        else:
            stage, days = 0, 1
        card["stage"] = str(stage)
        card["next_review"] = (date.today() + timedelta(days=days)).isoformat()
        # keep the last 5 marks only
        history = [entry for entry in card["history"].split() if entry][-5:]
        history.append(f"{date.today():%m%d}{mark}")
        card["history"] = " ".join(history)
        save(cards)
        print(f"[+] {card_id} -> stage {stage}, next review {card['next_review']} (in {days} days)")
        return
    print(f"no such card: {card_id}", file=sys.stderr)
    raise SystemExit(1)


def cmd_due():
    cards = [card for card in load() if card["next_review"] <= today()]
    if not cards:
        print("No cards due today. Go straight to a new question.")
        return
    print(f"Due today: {len(cards)} card(s)\n")
    for card in cards:
        overdue = (date.fromisoformat(today()) - date.fromisoformat(card["next_review"])).days
        late = f"  ({overdue} days overdue)" if overdue > 0 else ""
        print(f"  [{card['id']}] {card['question']}")
        print(f"        source: {card['source']} | stage {card['stage']}{late}")
    print("\nGrade: python3 tutor/scripts/review.py grade <id> o|t|x")


def cmd_list(area=None):
    cards = [card for card in load() if not area or card["area"] == area]
    if not cards:
        print("No cards.")
        return
    for card in cards:
        print(f"  [{card['id']}] stage {card['stage']} {card['next_review']}  {card['question']}")
    print(f"\nTotal: {len(cards)} card(s)")


def cmd_stats():
    cards = load()
    if not cards:
        print("No cards.")
        return
    due_count = sum(1 for card in cards if card["next_review"] <= today())
    count_by_area = {}
    count_by_stage = {}
    for card in cards:
        count_by_area[card["area"]] = count_by_area.get(card["area"], 0) + 1
        count_by_stage[card["stage"]] = count_by_stage.get(card["stage"], 0) + 1
    print(f"Cards: {len(cards)} | due today: {due_count}\n")
    print("By area")
    for area, count in sorted(count_by_area.items()):
        print(f"  {count:3}  {area}")
    print("\nBy stage (higher = remembered longer)")
    for stage in sorted(count_by_stage):
        print(f"  stage {stage}: {count_by_stage[stage]}")


def run(args):
    if not args:
        print(__doc__)
        raise SystemExit(2)
    command = args[0]
    if command == "due":
        cmd_due()
    elif command == "add" and len(args) == 4:
        cmd_add(args[1], args[2], args[3])
    elif command == "grade" and len(args) == 3:
        cmd_grade(args[1], args[2])
    elif command == "list":
        cmd_list(args[1] if len(args) > 1 else None)
    elif command == "stats":
        cmd_stats()
    else:
        print(__doc__)
        raise SystemExit(2)


def main():
    common.use_utf8_console()
    try:
        run(sys.argv[1:])
    except ValueError as error:
        # corrupted cards.md: one-line error instead of a traceback
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
