"""Verify the desktop client's translation table against the two legacy clients.

The merge is only safe if *every* string the old clients drew is still reachable.
This extracts each ``render(...)`` template from both clients, formats it with the
client's own sample values, and looks the result up in the table — reporting any
string that no key produces. It catches typos, dropped keys and drift, which a
diff-based review of 226 lines reliably misses.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client import translations  # noqa: E402

RENDER = re.compile(r"""\.render\(\s*(f?)(["'])(.*?)\2""", re.S)
FORMAT_FIELD = re.compile(r"\{[^}]*\}")

#: Sample values for the placeholders the client formats at run time. Chosen so the
#: *rendered* string can be compared as plain text.
SAMPLES = {
    "name": "Math",
    "expr": "1 + 1",
    "pts": "10",
    "tb": "5",
    "sb": "1",
    "hint": "HINT",
    "text": "HINT",
    "elapsed": "7",
    "g": "12",
    "mines_left": "3",
    "attempt": "abc",
    "remaining": "5",
    "done": "red",
    "idx": "1",
    "index": "1",
    "len(seq)": "3",
    "length": "5",
    "score": "20",
    "streak": "2",
    "moves": "4",
    "found": "2",
    "total": "6",
    "low": "1",
    "high": "50",
    "used": "2",
    "total_attempts": "8",
    "points": "10",
    "time_bonus": "5",
    "streak_bonus": "1",
    "value": "12",
    "start": "CAT",
    "end": "DOG",
    "target": "32",
}

#: The old clients spell placeholders as Python expressions inside f-strings
#: (``{data['low']}``); the table uses plain names. Normalise before comparing.
FIELD_ALIASES = {
    "self.engine.state.score": "score",
    "self.engine.state.streak": "streak",
    "data['low']": "low",
    "data['high']": "high",
    "data['attempts']": "used",
    "data['max_attempts']": "total_attempts",
    "data['start'].upper()": "start",
    "data['end'].upper()": "end",
    "puzzle.data['moves']": "moves",
    "puzzle.data['pairs_found']": "found",
    "puzzle.data['pairs']": "total",
    "puzzle.data['score']": "score",
    "puzzle.data['target']": "target",
    "len(seq)": "length",
    "idx": "index",
}


def render_with_samples(template: str) -> str:
    """Format a legacy f-string template with sample values."""
    def replace(match: re.Match) -> str:
        field = match.group(0)[1:-1]
        name = FIELD_ALIASES.get(field, field.split(".")[-1].split("[")[0].strip("'\""))
        return SAMPLES.get(name, f"<{name}>")

    return FORMAT_FIELD.sub(replace, template)


def table_strings(language: str) -> set[str]:
    """Every string the table can produce for *language*, formatted with samples."""
    produced: set[str] = set()
    for key in translations.TEXT:
        template = translations.TEXT[key][language]
        produced.add(render_with_samples(template))
        produced.add(template)  # also accept the raw template
    for mode in ("content_heavy", "balanced", "generated_heavy", "random"):
        produced.add(translations.label_for_mode(mode, language))
    for difficulty in ("easy", "medium", "hard", "random"):
        produced.add(translations.label_for_difficulty(difficulty, language))
    return produced


def main() -> int:
    problems: list[str] = []
    checked = 0
    for directory, language in (("text_adventure", "en"), ("text_adventure_zh", "zh")):
        produced = table_strings(language)
        for name in ("ui.py", "engine.py"):
            path = ROOT / directory / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for match in RENDER.finditer(text):
                literal = match.group(3)
                checked += 1
                rendered = render_with_samples(literal)
                if rendered in produced or literal in produced:
                    continue
                # Dynamic labels the client builds from data (puzzle names, digits,
                # the keyboard's number keys) are not table strings.
                if literal in {"  {name}", "|", "?", "{expr} = ?"}:
                    continue
                problems.append(f"{directory}/{name}: no table entry renders {rendered!r}")
    print(f"checked {checked} render strings from both clients")
    if problems:
        print("\nMISSING FROM THE TABLE:")
        for line in problems:
            print("  " + line)
        return 1
    print("every legacy render string is reachable from the translation table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
