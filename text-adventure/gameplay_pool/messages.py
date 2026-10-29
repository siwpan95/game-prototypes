"""Language layer for the puzzle modules: every user-facing string lives here.

Why this exists: the repository used to ship two parallel implementations of the
same 14 puzzles (``text_adventure/`` and ``text_adventure_zh/``). Measuring them
showed the divergence was **~200 lines and almost entirely message text** — the
logic was already identical. Two copies of the logic is the structural debt; two
copies of the strings is the actual reason it existed.

So the messages moved out of the classes:

* ``PUZZLE_NAMES`` — the display name of each kind, keyed by kind and language.
* ``LABELS`` — short static strings (hint fragments, status words).
* ``TEMPLATES`` — parameterised strings, formatted with ``.format(**kwargs)``.

A missing translation is a **loud** failure (``KeyError`` naming the key and the
language), because a silent fallback to another language is how a half-translated
build ships without anyone noticing.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "LANGUAGES",
    "DEFAULT_LANGUAGE",
    "normalise_language",
    "puzzle_name",
    "label",
    "text",
    "COLOR_WORDS_ZH",
]

#: Languages this package can speak. Adding one means adding a column here and in
#: the three tables below; nothing else in the puzzle modules is language-aware.
LANGUAGES: tuple[str, ...] = ("en", "zh")
DEFAULT_LANGUAGE = "zh"

#: Kind name -> display name, per language. The kind names are the registry ids.
PUZZLE_NAMES: dict[str, dict[str, str]] = {
    "math": {"en": "Math Puzzle", "zh": "数学题"},
    "riddle": {"en": "Riddle", "zh": "谜语"},
    "crossword": {"en": "Crossword", "zh": "填字游戏"},
    "sudoku": {"en": "Sudoku", "zh": "数独"},
    "guess_number": {"en": "Guess the Number", "zh": "猜数字"},
    "word_ladder": {"en": "Word Ladder", "zh": "单词接龙"},
    "minesweeper": {"en": "Minesweeper", "zh": "扫雷"},
    "nonogram": {"en": "Nonogram", "zh": "数织"},
    "anagram": {"en": "Anagram", "zh": "字谜"},
    "memory": {"en": "Memory Match", "zh": "记忆翻牌"},
    "pattern": {"en": "Pattern", "zh": "数列规律"},
    "hangman": {"en": "Hangman", "zh": "猜单词"},
    "2048": {"en": "2048", "zh": "2048"},
    "color_sequence": {"en": "Color Sequence", "zh": "颜色序列"},
}

#: Static strings.
LABELS: dict[str, dict[str, str]] = {
    # guess_number drives these into puzzle data as it is played
    "higher": {"en": "Higher!", "zh": "大一点！"},
    "lower": {"en": "Lower!", "zh": "小一点！"},
    "guess_even": {"en": "The number is even", "zh": "这个数是偶数"},
    "guess_odd": {"en": "The number is odd", "zh": "这个数是奇数"},
    # pattern rules
    "perfect_squares": {"en": "Perfect squares", "zh": "完全平方数"},
    "fibonacci": {"en": "Each number = sum of two before", "zh": "每个数 = 前两个数之和"},
    # fallbacks when a kind has nothing better to say
    "no_more_pairs": {"en": "No more pairs to find!", "zh": "没有更多配对了！"},
    "grid_looks_good": {"en": "Grid looks good!", "zh": "网格看起来不错！"},
    "almost_there": {"en": "You're almost there!", "zh": "快完成了！"},
    "grid_filled": {"en": "The grid is already filled!", "zh": "棋盘已填满！"},
    "all_mines_flagged": {"en": "All mines are flagged!", "zh": "所有地雷都已标记！"},
    "colors_done": {"en": "Already input full sequence!", "zh": "已输入完整个序列！"},
    "colors_none": {"en": "none", "zh": "无"},
    "crossword_done": {"en": "All words are filled in correctly!", "zh": "所有单词已正确填写！"},
    "crossword_look": {"en": "Look at the clues carefully!", "zh": "仔细看线索！"},
    "across": {"en": "Across", "zh": "横向"},
    "down": {"en": "Down", "zh": "纵向"},
    # 2048 advice
    "2048_advice": {
        "en": "Merge tiles by swiping in the same direction. Try corners!",
        "zh": "朝同一方向滑动来合并方块。试试角落策略！",
    },
}

#: Parameterised strings. ``{name}`` placeholders are filled by :func:`text`.
TEMPLATES: dict[str, dict[str, str]] = {
    "math_hint": {
        "en": "The answer has {length} digit(s) and starts with {first}",
        "zh": "答案有{length}位数，以{first}开头",
    },
    "guess_out_of_attempts": {
        "en": "Out of attempts! The answer was {target}",
        "zh": "次数用完了！答案是{target}",
    },
    "pattern_step_add": {"en": "+{step} each time", "zh": "每次 +{step}"},
    "pattern_step_mul": {"en": "x{step} each time", "zh": "每次 x{step}"},
    "pattern_powers": {"en": "Powers of {base}", "zh": "{base} 的幂"},
    "pattern_hint": {"en": "Rule: {rule}", "zh": "规律: {rule}"},
    "memory_hint": {
        "en": "Match at row {r1} col {c1} and row {r2} col {c2}",
        "zh": "第{r1}行第{c1}列 与 第{r2}行第{c2}列 匹配",
    },
    "nonogram_hint": {
        "en": "Row {row}, Col {col} should be filled",
        "zh": "第{row}行，第{col}列应该填充",
    },
    "sudoku_hint": {
        "en": "Row {row}, Col {col} is {value}",
        "zh": "第{row}行，第{col}列是{value}",
    },
    "minesweeper_hint": {
        "en": "Try flagging row {row}, col {col}",
        "zh": "试试在第{row}行第{col}列标记旗帜",
    },
    "hangman_contains": {
        "en": "Word contains '{letter}'",
        "zh": "单词包含'{letter}'",
    },
    "hangman_length": {
        "en": "Word has {count} letters: {display}",
        "zh": "单词有{count}个字母: {display}",
    },
    "anagram_hint": {
        "en": "The first letter is '{letter}'",
        "zh": "第一个字母是'{letter}'",
    },
    "riddle_hint": {
        "en": "The correct option starts with '{first}'",
        "zh": "正确答案以'{first}'开头",
    },
    "crossword_clue": {
        "en": "{number}. {clue} ({length} letters)",
        "zh": "{number}. {clue} ({length}个字母)",
    },
    "crossword_entry": {
        "en": "{direction}: {clue} ({length} letters)",
        "zh": "{direction}: {clue}（{length}个字母）",
    },
    "crossword_last_letter": {
        "en": "The last letter of '{word}' is '{letter}'",
        "zh": "'{word}' 的最后一个字母是 '{letter}'",
    },
    "word_ladder_position": {
        "en": "Change position {position} to '{letter}'",
        "zh": "把第{position}个位置改为'{letter}'",
    },
    # The two languages shape this sentence differently, so the words live in the
    # template as parameters rather than being concatenated in the puzzle.
    "colors_progress": {
        "en": "Done: {shown} | Next: {next}",
        "zh": "已完成: {shown} | 下一个: {next}",
    },
}

#: Words used by the Chinese build's colour display; kept for the pygame client,
#: which maps a colour name to its Chinese word for on-screen labels.
COLOR_WORDS_ZH: dict[str, str] = {
    "red": "红色",
    "green": "绿色",
    "blue": "蓝色",
    "yellow": "黄色",
}


def normalise_language(language: str | None) -> str:
    """Validate a language code, failing loudly on an unknown one."""
    if language is None:
        return DEFAULT_LANGUAGE
    code = str(language).strip().lower()
    if code not in LANGUAGES:
        raise ValueError(
            f"unsupported language {language!r}; this package speaks {list(LANGUAGES)}"
        )
    return code


def puzzle_name(kind: str, language: str | None = None) -> str:
    """Display name of *kind* in *language*."""
    code = normalise_language(language)
    try:
        return PUZZLE_NAMES[kind][code]
    except KeyError:
        raise KeyError(
            f"no display name for puzzle kind {kind!r} in {code!r}; "
            f"known kinds: {sorted(PUZZLE_NAMES)}"
        ) from None


def label(key: str, language: str | None = None) -> str:
    """A static string in *language*."""
    code = normalise_language(language)
    try:
        return LABELS[key][code]
    except KeyError:
        raise KeyError(f"no label {key!r} in {code!r}; known labels: {sorted(LABELS)}") from None


def text(key: str, language: str | None = None, **kwargs: Any) -> str:
    """A parameterised string in *language*, formatted with *kwargs*."""
    code = normalise_language(language)
    try:
        template = TEMPLATES[key][code]
    except KeyError:
        raise KeyError(
            f"no template {key!r} in {code!r}; known templates: {sorted(TEMPLATES)}"
        ) from None
    return template.format(**kwargs)
