"""Render-agnostic view models: one builder per puzzle kind.

Why this exists: the pygame clients dispatch on ``isinstance`` in both the event
path and the draw path, 14 branches each, so a client can only ever render the
kinds it was compiled against. Here each kind publishes a *view model* instead —
plain JSON describing what to show and what can be clicked — so a client renders
a handful of primitives (text field, options, grid, board, keyboard, colours)
and new kinds arrive without touching client code.

Primitive catalogue (``views.build`` returns ``kind`` + ``nodes`` + ``actions``):

``text``      a prompt plus an input field (``answer_type`` says how to parse)
``options``   a prompt plus clickable choices
``sequence``  an ordered set of tokens, each optionally clickable (``move`` action)
``grid``      a 2-D table of cells; the client encodes clicks/typing into actions
``keyboard``  a letter keyboard for word games, letters carrying a state
``colors``    a colour palette; the client reports the colour it pressed
``board``     a directional game (2048): arrows plus a numeric board

View models never carry the solution: ``crossword`` sends the *player* grid and
the clues, not the filled words; ``sudoku`` sends the puzzle, not the solution.
"""

from __future__ import annotations

from typing import Any, Callable

from puzzle_service.registry import PuzzleKind

__all__ = ["build", "registered", "LABEL_KEYS"]

#: Label keys a client may have to render. The service emits a *key*; each client
#: supplies its own wording, because only the client knows what language its user
#: reads. ``text`` carries an English default so a client that has no table for a
#: key still shows something sensible instead of the raw key.
#:
#: Adding a key here is a contract change: the tests assert that every client that
#: translates labels covers this set.
LABEL_KEYS: dict[str, str] = {
    "answer": "Answer",
    "letter": "Letter",
    "word": "Word",
    "next_word": "Next word (one step at a time)",
}


def _is_zh(puzzle: Any) -> bool:
    """Whether the puzzle came from the Chinese build (decides literal labels)."""
    return str(puzzle.__class__.__module__).split(".", 1)[0].endswith("_zh")


def _label(puzzle: Any, zh: str, en: str) -> str:
    return zh if _is_zh(puzzle) else en


def _field(name: str, label_key: str, answer_type: str) -> dict[str, Any]:
    """A text-input node carrying a label key plus a language-neutral default."""
    return {
        "type": "field",
        "name": name,
        "label_key": label_key,
        "label": LABEL_KEYS.get(label_key, label_key),
        "answer_type": answer_type,
    }


def _cells_from(grid: list[list[Any]]) -> list[list[dict[str, Any]]]:
    """Turn a raw 2-D array into cell objects the client can render uniformly."""
    cells: list[list[dict[str, Any]]] = []
    for row_index, row in enumerate(grid):
        rendered_row: list[dict[str, Any]] = []
        for col_index, value in enumerate(row):
            text = "" if value is None else str(value)
            rendered_row.append(
                {
                    "row": row_index,
                    "col": col_index,
                    "text": text,
                    "value": value if isinstance(value, (int, float, bool)) else text,
                    "blank": value in (None, "", 0, False),
                }
            )
        cells.append(rendered_row)
    return cells


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_text(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    prompt = str(data.get("expression") or data.get("question") or data.get("rule") or "")
    nodes: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if kind.name == "guess_number" and data.get("last_hint"):
        nodes.append({"type": "text", "text": str(data["last_hint"]), "style": "muted"})
    nodes.append(_field("answer", "answer", kind.answer_type))
    return {"kind": kind.name, "interaction": "text", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_options(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    prompt = str(data.get("question") or data.get("rule") or "选一个")
    options = [str(option) for option in data.get("options", [])]
    nodes: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {
            "type": "options",
            "name": "answer",
            "items": [
                {"index": index, "text": text, "answer": index}
                for index, text in enumerate(options)
            ],
        },
    ]
    if kind.name == "pattern" and data.get("sequence"):
        nodes.insert(
            1, {"type": "sequence", "tokens": [str(v) for v in data["sequence"]]}
        )
    return {"kind": kind.name, "interaction": "choice", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_sequence(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    """Anagram: reorderable letters. Word ladder: the path so far."""
    data = puzzle.data
    if kind.name == "anagram":
        letters = [str(letter) for letter in data.get("player_letters", detail(data, "shuffled"))]
        nodes = [
            {"type": "text", "text": _label(puzzle, "重排字母拼出单词", "Rearrange the letters")},
            {
                "type": "sequence",
                "name": "letters",
                "tokens": letters,
                "clickable": True,
                "action": "swap_letters",
                "hint": "点两个字母交换位置",
            },
            _field("answer", "word", kind.answer_type),
        ]
        return {"kind": kind.name, "interaction": "sequence", "nodes": nodes,
                "actions": list(kind.actions) + ["submit", "hint"]}

    path = [str(word) for word in data.get("player_path", [])]
    nodes = [
        {"type": "text", "text": f"{data.get('start', '?')} → {data.get('end', '?')}"},
        {"type": "sequence", "name": "path", "tokens": path},
        _field("answer", "next_word", kind.answer_type),
    ]
    return {"kind": kind.name, "interaction": "sequence", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def detail(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a data key with a default (keeps the builders free of ``get`` chains)."""
    return data.get(key, default)


def build_crossword(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    player = _cells_from(data.get("player_grid", []))
    numbers = data.get("numbers", {})
    for row in player:
        for cell in row:
            number = numbers.get((cell["row"], cell["col"]))
            if number:
                cell["label"] = str(number)
    nodes = [
        {"type": "text", "text": "填写横向与纵向单词"},
        {"type": "grid", "name": "grid", "cells": player, "editable": True,
         "action": "set_cell", "input": "letter"},
        {"type": "list", "name": "across", "items": [str(c) for c in data.get("clues_across", [])]},
        {"type": "list", "name": "down", "items": [str(c) for c in data.get("clues_down", [])]},
    ]
    return {"kind": kind.name, "interaction": "grid", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_sudoku(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    puzzle_grid = data.get("puzzle", [])
    player = _cells_from(data.get("player_grid", puzzle_grid))
    for row_index, row in enumerate(player):
        for cell in row:
            given = puzzle_grid[row_index][cell["col"]] if row_index < len(puzzle_grid) else 0
            cell["fixed"] = bool(given)
    nodes = [
        {
            "type": "text",
            "text": f"{data.get('size', 9)}×{data.get('size', 9)} 数独：填 1–{data.get('size', 9)}",
        },
        {"type": "grid", "name": "grid", "cells": player, "editable": True,
         "action": "set_cell", "input": "digit", "box": [data.get("box_h", 2), data.get("box_w", 2)]},
    ]
    return {"kind": kind.name, "interaction": "grid", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_minesweeper(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    grid = data.get("grid", [])
    revealed = data.get("revealed", [])
    flagged = data.get("flagged", [])
    cells = _cells_from(grid)
    for row in cells:
        for cell in row:
            row_index, col_index = cell["row"], cell["col"]
            is_revealed = bool(revealed[row_index][col_index]) if revealed else False
            is_flagged = bool(flagged[row_index][col_index]) if flagged else False
            cell["revealed"] = is_revealed
            cell["flagged"] = is_flagged
            if not is_revealed:
                cell["text"] = "🚩" if is_flagged else ""
                cell["value"] = None
            elif cell["value"] == -1:
                cell["text"] = "💥"
            elif cell["value"] == 0:
                cell["text"] = ""
    nodes = [
        {
            "type": "text",
            "text": f"{data.get('rows')}×{data.get('cols')} 雷区：{data.get('mines')} 颗雷"
            f"，还剩 {data.get('mines', 0) - sum(sum(1 for f in row if f) for row in flagged)} 面旗",
        },
        {"type": "grid", "name": "grid", "cells": cells, "editable": True,
         "action": "reveal", "secondary_action": "toggle_flag", "input": "flag"},
    ]
    return {"kind": kind.name, "interaction": "grid", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_nonogram(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    player = _cells_from(data.get("player_grid", []))
    for row in player:
        for cell in row:
            cell["text"] = "■" if cell["value"] else ""
    nodes = [
        {"type": "text", "text": f"{data.get('size')}×{data.get('size')} 数织：按行/列线索填格"},
        {"type": "clues", "name": "row_clues", "items": data.get("row_clues", [])},
        {"type": "grid", "name": "grid", "cells": player, "editable": True,
         "action": "toggle_cell", "input": "toggle"},
        {"type": "clues", "name": "col_clues", "items": data.get("col_clues", [])},
    ]
    return {"kind": kind.name, "interaction": "grid", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_memory(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    grid = data.get("grid", [])
    revealed = data.get("revealed", [])
    matched = data.get("matched", [])
    cells = _cells_from([["" for _ in row] for row in grid])
    for row in cells:
        for cell in row:
            row_index, col_index = cell["row"], cell["col"]
            is_matched = bool(matched[row_index][col_index]) if matched else False
            is_revealed = bool(revealed[row_index][col_index]) if revealed else False
            cell["matched"] = is_matched
            cell["revealed"] = is_revealed or is_matched
            cell["symbol"] = (
                grid[row_index][col_index] if cell["revealed"] else None
            )
            cell["text"] = cell["symbol"] or ""
    nodes = [
        {
            "type": "text",
            "text": f"翻牌配对：{data.get('pairs_found', 0)}/{data.get('pairs', 0)} 对"
            f"，{data.get('moves', 0)} 步",
        },
        {"type": "grid", "name": "grid", "cells": cells, "editable": True,
         "action": "flip_card", "input": "flip"},
    ]
    return {"kind": kind.name, "interaction": "grid", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_keyboard(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    letters = [letter for letter in alphabet if letter.isalpha()]
    guessed = {str(letter).lower() for letter in puzzle.data.get("guessed", set())}
    wrong = {str(letter).lower() for letter in puzzle.data.get("wrong", set())}
    keys = [
        {
            "letter": letter.upper(),
            "state": "correct" if letter in guessed else "wrong" if letter in wrong else "unused",
        }
        for letter in letters
    ]
    nodes = [
        {"type": "text", "text": puzzle.get_display() if hasattr(puzzle, "get_display") else ""},
        {
            "type": "text",
            "text": f"错误 {len(wrong)}/{puzzle.data.get('max_wrong', 6)}",
            "style": "muted",
        },
        {"type": "keyboard", "name": "letters", "keys": keys, "action": "guess_letter"},
    ]
    return {"kind": kind.name, "interaction": "keyboard", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_colors(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    palette = ["red", "green", "blue", "yellow"]
    nodes = [
        {
            "type": "text",
            "text": _label(puzzle, "记住闪烁顺序，然后按顺序点颜色", "Watch the flash order, then press the colours in order"),
        },
        {"type": "text", "text": f"阶段 {data.get('phase', 'show')}，已输入 {data.get('player_index', 0)}",
         "style": "muted"},
        {
            "type": "colors",
            "name": "palette",
            "swatches": [{"color": name, "label": name} for name in palette],
            "action": "press_color",
        },
    ]
    return {"kind": kind.name, "interaction": "colors", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


def build_board(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    data = puzzle.data
    cells = _cells_from(data.get("board", []))
    nodes = [
        {
            "type": "text",
            "text": f"合到 {data.get('target')}：得分 {data.get('score', 0)}",
        },
        {"type": "board", "name": "board", "cells": cells, "action": "move",
         "directions": ["up", "down", "left", "right"], "input": "arrows"},
    ]
    return {"kind": kind.name, "interaction": "board", "nodes": nodes,
            "actions": list(kind.actions) + ["submit", "hint"]}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

#: kind name -> builder. Kinds are plugins: a new kind adds one entry (or falls
#: back to ``_by_interaction`` when its interaction model is already covered).
_BY_KIND: dict[str, Callable[[PuzzleKind, Any], dict[str, Any]]] = {
    "math": build_text,
    "riddle": build_options,
    "pattern": build_options,
    "guess_number": build_text,
    "crossword": build_crossword,
    "sudoku": build_sudoku,
    "minesweeper": build_minesweeper,
    "nonogram": build_nonogram,
    "memory": build_memory,
    "anagram": build_sequence,
    "word_ladder": build_sequence,
    "hangman": build_keyboard,
    "color_sequence": build_colors,
    "2048": build_board,
}

_BY_INTERACTION: dict[str, Callable[[PuzzleKind, Any], dict[str, Any]]] = {
    "text": build_text,
    "choice": build_options,
    "sequence": build_sequence,
    "keyboard": build_keyboard,
    "colors": build_colors,
    "board": build_board,
}


def registered() -> list[str]:
    """Kind names that have a dedicated view builder."""
    return sorted(_BY_KIND)


def build(kind: PuzzleKind, puzzle: Any) -> dict[str, Any]:
    """Build the view model for *kind*'s *puzzle*.

    A kind without a dedicated builder still works when its interaction model is
    one of the generic ones; only an unknown interaction is an error (loudly, so
    a half-added kind cannot silently render as an empty screen).
    """
    builder = _BY_KIND.get(kind.name)
    if builder is None:
        builder = _BY_INTERACTION.get(kind.interaction)
    if builder is None:
        raise NotImplementedError(
            f"no view builder for kind {kind.name!r} (interaction {kind.interaction!r}); "
            f"add one to puzzle_service.views._BY_KIND"
        )
    view = builder(kind, puzzle)
    view.setdefault("title", kind.title)
    view.setdefault("puzzle_id", getattr(puzzle, "puzzle_id", None))
    view["solved"] = bool(getattr(puzzle, "solved", False))
    return view
