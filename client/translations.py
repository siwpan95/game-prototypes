"""Every string the desktop client draws, one table per language.

The two pygame clients were near-copies: 1755 vs 1763 lines, and the difference was
this table plus two layout choices. Extracting it here is what lets one client serve
both languages.

Missing strings fail loudly (``KeyError`` naming the key and the language), because a
silent fallback to the other language is how a half-translated build ships.
"""

from __future__ import annotations

__all__ = [
    "TEXT",
    "t",
    "tr",
    "mode_options",
    "hint_bar_at_bottom",
    "label_for_mode",
    "label_for_difficulty",
]

#: key -> {language: string}. ``{}``-style placeholders are filled by :func:`t`.
TEXT: dict[str, dict[str, str]] = {
    # --- window and menu ---
    "caption": {"en": "Puzzle Game", "zh": "解谜游戏"},
    "title": {"en": "Puzzle Game", "zh": "解密游戏"},
    "subtitle": {"en": "A Collection of Brain Teasers", "zh": "脑筋急转弯合集"},
    "section_mode": {"en": "Mode", "zh": "模式"},
    "section_difficulty": {"en": "Difficulty", "zh": "难度"},
    "start": {"en": "START", "zh": "开始"},
    "quit": {"en": "QUIT", "zh": "退出"},
    "mode_content_heavy": {"en": "Content Heavy", "zh": "内容为主"},
    "mode_balanced": {"en": "Balanced", "zh": "均衡模式"},
    "mode_generated_heavy": {"en": "Generated Heavy", "zh": "生成为主"},
    "mode_random": {"en": "Random", "zh": "随机"},
    "difficulty_easy": {"en": "Easy", "zh": "简单"},
    "difficulty_medium": {"en": "Medium", "zh": "中等"},
    "difficulty_hard": {"en": "Hard", "zh": "困难"},
    "difficulty_random": {"en": "Random", "zh": "随机"},
    # --- footer buttons (matched by key, never by their text) ---
    "btn_menu": {"en": "Menu", "zh": "菜单"},
    "btn_hint": {"en": "Hint", "zh": "提示"},
    "btn_skip": {"en": "Skip", "zh": "跳过"},
    "btn_next": {"en": "Next", "zh": "下一题"},
    "btn_check": {"en": "Check", "zh": "检查"},
    "btn_submit": {"en": "Submit", "zh": "提交"},
    "btn_undo": {"en": "Undo", "zh": "撤销"},
    "btn_shuffle": {"en": "Shuffle", "zh": "打乱"},
    "btn_delete": {"en": "Del", "zh": "删除"},
    "btn_ok": {"en": "OK", "zh": "确定"},
    # --- header ---
    "score_streak": {"en": "Score: {self.engine.state.score}  Streak: {self.engine.state.streak}", "zh": "分数: {self.engine.state.score}  连胜: {self.engine.state.streak}"},
    "time": {"en": "Time: {elapsed}s", "zh": "用时: {elapsed}秒"},
    # --- shared bars ---
    "hint_bar": {"en": "Hint: {text}", "zh": "提示: {text}"},
    "correct": {"en": "Correct!", "zh": "正确!"},
    "wrong": {"en": "Wrong!", "zh": "错误!"},
    "points": {"en": "+{points} points", "zh": "+{points} 分"},
    "bonus_detail": {
        "en": "Time bonus: +{time_bonus}  Streak bonus: +{streak_bonus}",
        "zh": "时间加成: +{time_bonus}  连胜加成: +{streak_bonus}",
    },
    "click_to_continue": {"en": "Click anywhere to continue", "zh": "点击任意位置继续"},
    # --- per puzzle ---
    "math_question": {"en": "{expression} = ?", "zh": "{expression} = ?"},
    "crossword_across": {"en": "ACROSS", "zh": "横向"},
    "crossword_down": {"en": "DOWN", "zh": "纵向"},
    "riddle_prompt": {"en": "What comes next?", "zh": "下一个是什么？"},
    "guess_prompt": {
        "en": "Guess a number between {data['low']} and {data['high']}",
        "zh": "猜一个 {data['low']} 到 {data['high']} 之间的数字",
    },
    "guess_attempts": {"en": "Attempts: {data['attempts']}/{data['max_attempts']}", "zh": "尝试次数: {data['attempts']}/{data['max_attempts']}"},
    "guess_range": {"en": "{low} — {high}", "zh": "{low} — {high}"},
    "guess_previous": {"en": "Guessed: {value}", "zh": "已猜: {value}"},
    "ladder_prompt": {"en": "Transform '{data['start'].upper()}' -> '{data['end'].upper()}'", "zh": "变换 '{data['start'].upper()}' → '{data['end'].upper()}'"},
    "ladder_input": {"en": "Type next word and press Enter:", "zh": "输入下一个单词后按回车:"},
    "mines_left": {"en": "Mines left: {mines_left}", "zh": "剩余地雷: {mines_left}"},
    "anagram_prompt": {"en": "Unscramble the word!", "zh": "拼出正确的单词！"},
    "anagram_current": {"en": "Current: {attempt}", "zh": "当前: {attempt}"},
    "anagram_instruction": {"en": "Click two letters to swap them", "zh": "点击两个字母交换位置"},
    "memory_moves": {
        "en": "Moves: {puzzle.data['moves']}  Pairs: {puzzle.data['pairs_found']}/{puzzle.data['pairs']}",
        "zh": "步数: {puzzle.data['moves']}  配对: {puzzle.data['pairs_found']}/{puzzle.data['pairs']}",
    },
    "pattern_question": {"en": "What comes next?", "zh": "下一个是什么？"},
    "hangman_prompt": {"en": "Guess the word!", "zh": "猜单词！"},
    "hangman_left": {"en": "Guesses left: {remaining}", "zh": "剩余猜测次数: {remaining}"},
    "board_score": {
        "en": "Score: {puzzle.data['score']}  |  Target: {puzzle.data['target']}",
        "zh": "分数: {puzzle.data['score']}  |  目标: {puzzle.data['target']}",
    },
    "board_instruction": {
        "en": "Arrow keys / WASD to move tiles",
        "zh": "方向键 / WASD 移动方块",
    },
    "board_game_over": {"en": "Game Over!", "zh": "游戏结束！"},
    "colors_prompt": {"en": "Repeat the Color Sequence!", "zh": "重复颜色序列！"},
    "colors_watch": {"en": "Watch the pattern...", "zh": "观察模式..."},
    "colors_progress": {
        "en": "Your input: {done}  ({idx}/{len(seq)})",
        "zh": "你的输入: {done}  ({idx}/{len(seq)})",
    },
    "colors_length": {"en": "Sequence length: {len(seq)}", "zh": "序列长度: {len(seq)}"},
    # --- transient messages ---
    "msg_wrong_try_again": {"en": "Wrong! Try again.", "zh": "错误！再试一次。"},
    "msg_not_quite_right": {"en": "Not quite right!", "zh": "不太对！"},
    "msg_not_quite_right_yet": {"en": "Not quite right yet!", "zh": "还没完全正确！"},
    "msg_not_complete_yet": {"en": "Not complete yet!", "zh": "尚未完成！"},
    "msg_not_right_word": {"en": "Not the right word yet!", "zh": "还不是正确的单词！"},
    "msg_invalid_step_letter": {
        "en": "Invalid step! One letter must change.",
        "zh": "无效步骤！必须改变一个字母。",
    },
    "msg_invalid_step": {"en": "Invalid step!", "zh": "无效步骤！"},
    "msg_boom": {"en": "BOOM! Game Over!", "zh": "轰！游戏结束！"},
    "msg_no_active_puzzle": {"en": "No active puzzle", "zh": "没有活动中的谜题"},
    "msg_no_active_puzzle_hint": {"en": "No active puzzle", "zh": "没有活动的谜题"},
    "msg_out_of_attempts": {"en": "Out of attempts", "zh": "次数用完了"},
    # --- hangman feedback (built in the draw path) ---
    "hangman_hit": {"en": "'{letter}' is in the word!", "zh": "'{letter}' 在单词中！"},
    "hangman_miss": {
        "en": "'{letter}' is wrong! ({wrong}/{total})",
        "zh": "'{letter}' 猜错了！({wrong}/{total})",
    },
    "hangman_over": {"en": "Game over! The word was {word}", "zh": "游戏结束！单词: {word}"},
    "hangman_repeat": {"en": "You already tried '{letter}'!", "zh": "你已经试过 '{letter}' 了！"},
    "hangman_wrong_prefix": {"en": "Wrong: ", "zh": "已错: "},
    # --- colour sequence ---
    "cs_correct": {"en": "Correct! Well done!", "zh": "正确！做得好！"},
    "cs_wrong": {"en": "Wrong sequence! Round failed.", "zh": "序列错误！当前回合失败。"},
    "cs_correct_marker": {"en": "Correct", "zh": "正确"},
    # Swatch labels: lowercase in English, because the legacy English client drew the
    # colour key itself ("red"), while the Chinese one drew its word (红色). Capitalised
    # English would be a silent restyle of that screen (caught by the pixel comparison).
    "color_red": {"en": "red", "zh": "红色"},
    "color_green": {"en": "green", "zh": "绿色"},
    "color_blue": {"en": "blue", "zh": "蓝色"},
    "color_yellow": {"en": "yellow", "zh": "黄色"},
}

#: Draw order of the colour-puzzle swatches. Both legacy clients drew a fixed order
#: (``red, green, blue, yellow``) that differs from
#: ``gameplay_pool.color_sequence.COLORS`` (``red, blue, green, yellow``) — same four
#: colours, different layout. The layout is a presentation choice, so it is preserved
#: here rather than inherited from the data order.
SWATCH_ORDER: tuple[str, ...] = ("red", "green", "blue", "yellow")

#: Mode choices per language. The two legacy clients genuinely differed here — the
#: Chinese one offered `random` only — so each language keeps its own list rather
#: than the merge silently changing what a user can pick.
MODE_OPTIONS: dict[str, list[str]] = {
    "en": ["content_heavy", "balanced", "generated_heavy", "random"],
    "zh": ["random"],
}
MODE_DEFAULT_INDEX: dict[str, int] = {"en": 1, "zh": 0}

#: Where the hint bar is drawn. The Chinese client moved it above the footer (where
#: it cannot cover the puzzle); the English one draws it mid-screen. Preserved per
#: language for the same reason as the mode list.
HINT_BAR_AT_BOTTOM: dict[str, bool] = {"en": False, "zh": True}


def t(key: str, language: str, **kwargs: object) -> str:
    """The string for *key* in *language*, with placeholders filled.

    Placeholders are substituted by name, not through :meth:`str.format`: the legacy
    clients spelled fields as Python expressions (``{self.engine.state.score}``,
    ``{puzzle.data['moves']}``), and ``str.format`` reads the dot as attribute access
    and rejects the brackets. Substituting by name keeps those spellings working
    verbatim, which is what makes the pixel comparison exact.
    """
    try:
        template = TEXT[key][language]
    except KeyError:
        raise KeyError(
            f"desktop client has no string {key!r} for language {language!r}; "
            f"known keys: {sorted(TEXT)}"
        ) from None
    for name, value in kwargs.items():
        template = template.replace("{" + name + "}", str(value))
    return template


def tr(key: str, language: str, **kwargs: object) -> str:
    """Alias of :func:`t` used by the UI.

    The draw methods use local variables named ``t`` for text surfaces, so the UI
    imports the helper as ``tr``; inside such a method ``t(...)`` would call a
    Surface. Two names for one function is cheaper than a shadowing bug that only
    fires on the screens using both.
    """
    return t(key, language, **kwargs)


def mode_options(language: str) -> list[str]:
    return list(MODE_OPTIONS.get(language, MODE_OPTIONS["en"]))


def hint_bar_at_bottom(language: str) -> bool:
    return HINT_BAR_AT_BOTTOM.get(language, False)


def label_for_mode(mode: str, language: str) -> str:
    """Display text for a mode id, falling back to a title-cased id."""
    key = f"mode_{mode}"
    if key in TEXT:
        return t(key, language)
    return mode.replace("_", " ").title()


def label_for_difficulty(difficulty: str, language: str) -> str:
    key = f"difficulty_{difficulty}"
    if key in TEXT:
        return t(key, language)
    return difficulty.title()
