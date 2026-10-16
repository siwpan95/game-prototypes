"""Report Button(...) constructions whose arguments don't line up.

A keyword inserted in the middle of a call can silently shift what a later positional
argument means: ``Button(rect, label, font, key="x", color=C_GREEN)`` is fine, but
``Button(rect, label, key="x", font, color=C_GREEN)`` passes the font as the colour.
This checks the *shape* of every call instead of trusting the edit.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: (positional index) -> parameter name, from client/ui.py's Button signature.
SIGNATURE = ["rect", "text", "font", "color", "hover_color", "text_color", "border_radius", "key"]


def check(path: Path) -> list[str]:
    problems: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "Button":
            continue
        seen_keyword = None
        for index, arg in enumerate(node.args):
            if seen_keyword is not None:
                problems.append(
                    f"{path.name}:{node.lineno}: positional argument after keyword "
                    f"{seen_keyword!r} (position {index} = {SIGNATURE[index] if index < len(SIGNATURE) else '?'})"
                )
        for keyword in node.keywords:
            if seen_keyword is not None:
                continue
            seen_keyword = keyword.arg
            if keyword.arg in SIGNATURE:
                position = SIGNATURE.index(keyword.arg)
                if len(node.args) > position:
                    problems.append(
                        f"{path.name}:{node.lineno}: {keyword.arg}= given but position "
                        f"{position} is already filled positionally"
                    )
    return problems


def main() -> int:
    problems: list[str] = []
    for name in ("client/ui.py", "text_adventure/ui.py", "text_adventure_zh/ui.py"):
        path = ROOT / name
        if path.is_file():
            problems.extend(check(path))
    if problems:
        print("BUTTON CALL PROBLEMS:")
        for line in problems:
            print("  " + line)
        return 1
    print("all Button(...) calls are well formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
