"""Build the unified pygame client from the legacy sources, in one pass.

The first attempts edited the file through several independent passes, and the passes
fought each other: the keypad loop ended up with a label expression in its colour
argument and every digit tagged as the delete key. Rather than patch that state, this
script takes the legacy file as immutable input and applies the whole transform once,
with each edit either applying exactly or being reported.

Run without arguments to review the plan; ``--apply`` writes ``client/ui.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "text_adventure_zh" / "ui.py"
TARGET = ROOT / "client" / "ui.py"

KEYPAD_OLD = '''        for i, key in enumerate(keys):
            r, c = divmod(i, cols)
            rect = pygame.Rect(sx + c * (bw + gap), sy + r * (bh + gap), bw, bh)
            color = C_RED if key == "删除" else C_GREEN if key == "确定" else C_BTN
            self._puzzle_buttons.append(Button(rect, key, self.font_md, color=color))'''

KEYPAD_NEW = '''        for i, key in enumerate(keys):
            r, c = divmod(i, cols)
            rect = pygame.Rect(sx + c * (bw + gap), sy + r * (bh + gap), bw, bh)
            # The label is the value this button types, so the digit branch in the
            # handler reads `btn.text`; only delete/OK carry a dispatch key.
            if key == tr("btn_delete", self.lang):
                role, color = "btn_delete", C_RED
            elif key == tr("btn_ok", self.lang):
                role, color = "btn_ok", C_GREEN
            else:
                role, color = "", C_BTN
            self._puzzle_buttons.append(
                Button(rect, key, self.font_md, color=color, key=role)
            )'''

HEADER_OLD = """from shared import ensure_importable

ensure_importable()

from engine import Engine"""
HEADER_NEW = """from shared import ensure_importable

ensure_importable()

from client.engine import Engine
from client.translations import (
    MODE_DEFAULT_INDEX,
    SWATCH_ORDER,
    hint_bar_at_bottom,
    label_for_difficulty,
    label_for_mode,
    mode_options,
    tr,
)"""

FOOTER_OLD = '''    def _build_footer(self) -> None:
        self._footer_buttons = []
        labels = ["菜单", "提示", "跳过", "下一题"]'''
FOOTER_NEW = '''    def _build_footer(self) -> None:
        self._footer_buttons = []
        labels = [(key, tr(key, self.lang)) for key in FOOTER_KEYS]'''

FOOTER_LOOP_OLD = '''        for i, label in enumerate(labels):
            r = pygame.Rect(sx + i * (bw + gap), HEIGHT - FOOTER_H + 8, bw, 34)
            self._footer_buttons.append(Button(r, label, self.font_sm))'''
FOOTER_LOOP_NEW = '''        for i, (key, label) in enumerate(labels):
            r = pygame.Rect(sx + i * (bw + gap), HEIGHT - FOOTER_H + 8, bw, 34)
            self._footer_buttons.append(Button(r, label, self.font_sm, key=key))'''

CONSTANTS_OLD = """WIDTH, HEIGHT = 960, 720
FPS = 60
HEADER_H = 50
FOOTER_H = 50"""
CONSTANTS_NEW = '''WIDTH, HEIGHT = 960, 720
FPS = 60
HEADER_H = 50
FOOTER_H = 50

#: Footer buttons in draw order: dispatch keys (stable across languages) paired with
#: the translation key for their label.
FOOTER_KEYS: tuple[str, ...] = ("btn_menu", "btn_hint", "btn_skip", "btn_next")'''

BUTTON_OLD = """    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                 color: tuple = C_BTN, hover_color: tuple = C_BTN_HOV,
                 text_color: tuple = C_WHITE, border_radius: int = 6):
        self.rect = rect
        self.text = text
        self.font = font"""
BUTTON_NEW = """    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                 color: tuple = C_BTN, hover_color: tuple = C_BTN_HOV,
                 text_color: tuple = C_WHITE, border_radius: int = 6,
                 key: str = ""):
        self.rect = rect
        self.text = text
        #: Stable identity for dispatching clicks. The label cannot serve this role in
        #: a multi-language client: dispatching on displayed text means the branch
        #: changes when the wording does.
        self.key = key
        self.font = font"""

UI_INIT_OLD = """class UI:
    def __init__(self, engine: Engine):
        self.engine = engine
        pygame.init()"""
UI_INIT_NEW = """class UI:
    def __init__(self, engine: Engine, lang: str | None = None):
        self.engine = engine
        #: The language this client speaks. The engine and every puzzle are asked for
        #: it too, so hints and content match the interface.
        self.lang = lang or getattr(engine, "lang", None) or "zh"
        pygame.init()"""

FONT_OLD = '''def _load_font(size: int) -> pygame.font.Font:
    """跨平台加载 CJK 字体 — 用 SysFont 替代硬编码路径"""
    from shared.font_utils import load_cjk_font
    return load_cjk_font(size)'''
FONT_NEW = '''def _load_font(size: int, prefer_cjk: bool = True) -> pygame.font.Font:
    """Load a font by family name — no hard-coded font path (see shared/font_utils).

    ``prefer_cjk`` follows the language: the Chinese client always loaded a CJK family
    (and verified it really renders CJK), while the English client used the Latin
    family. Keeping that per language means the merged client draws what each old
    client drew, and an English screen stops picking up a different typeface.
    """
    from shared.font_utils import load_cjk_font, load_font

    return load_cjk_font(size) if prefer_cjk else load_font(size)'''

FONT_CALLS_OLD = """        self.font_lg = _load_font(32)
        self.font_md = _load_font(22)
        self.font_sm = _load_font(17)
        self.font_xs = _load_font(14)"""
FONT_CALLS_NEW = """        # Font family follows the language; see _load_font.
        prefer_cjk = self.lang == "zh"
        self.font_lg = _load_font(32, prefer_cjk=prefer_cjk)
        self.font_md = _load_font(22, prefer_cjk=prefer_cjk)
        self.font_sm = _load_font(17, prefer_cjk=prefer_cjk)
        self.font_xs = _load_font(14, prefer_cjk=prefer_cjk)"""

MODE_OLD = "        self._mode_options = [\"random\"]"
MODE_NEW = "        self._mode_options = mode_options(self.lang)"
MODE_IDX_OLD = "        self._mode_idx = 0\n"
MODE_IDX_NEW = "        self._mode_idx = MODE_DEFAULT_INDEX.get(self.lang, 0)\n"

MODE_LABELS_OLD = '''            mode_map = {
                "content_heavy": "内容为主",
                "balanced": "均衡模式",
                "generated_heavy": "生成为主",
                "random": "随机",
            }
            label = mode_map.get(mode, mode)'''
MODE_LABELS_NEW = "            label = label_for_mode(mode, self.lang)"

DIFF_LABELS_OLD = '''            diff_map = {
                "easy": "简单",
                "medium": "中等",
                "hard": "困难",
                "random": "随机",
            }
            label = diff_map.get(diff, diff)'''
DIFF_LABELS_NEW = "            label = label_for_difficulty(diff, self.lang)"

HINT_BAR_OLD = """            by = HEIGHT - FOOTER_H - 46
            pygame.draw.rect(self.screen, C_DARK, (bx, by, surf.get_width() + 20, 36),
                             border_radius=8)
            self.screen.blit(surf, (bx + 10, by + 6))"""
HINT_BAR_NEW = """            # Where the bar sits is a per-language choice: the Chinese client moved it
            # above the footer so it cannot cover the puzzle, the English one draws it
            # mid-screen. Preserved per language rather than picked for both.
            bottom = hint_bar_at_bottom(self.lang)
            by = (HEIGHT - FOOTER_H - 46) if bottom else (HEIGHT // 2 - 20)
            pygame.draw.rect(self.screen, C_DARK, (bx, by, surf.get_width() + 20, 36 if bottom else 40),
                             border_radius=8)
            self.screen.blit(surf, (bx + 10, by + (6 if bottom else 8)))"""

#: label literal -> translation key
LABELS: dict[str, str] = {
    "解谜游戏": "caption", "脑筋急转弯合集": "subtitle", "模式": "section_mode",
    "难度": "section_difficulty", "开始": "start", "退出": "quit",
    "点击任意位置继续": "click_to_continue", "输入下一个单词后按回车:": "ladder_input",
    "拼出正确的单词！": "anagram_prompt", "点击两个字母交换位置": "anagram_instruction",
    "下一个是什么？": "riddle_prompt", "猜单词！": "hangman_prompt",
    "方向键 / WASD 移动方块": "board_instruction", "游戏结束！": "board_game_over",
    "重复颜色序列！": "colors_prompt", "观察模式...": "colors_watch",
    "横向": "crossword_across", "纵向": "crossword_down",
    "错误！再试一次。": "msg_wrong_try_again", "不太对！": "msg_not_quite_right",
    "还没完全正确！": "msg_not_quite_right_yet", "尚未完成！": "msg_not_complete_yet",
    "还不是正确的单词！": "msg_not_right_word",
    "无效步骤！必须改变一个字母。": "msg_invalid_step_letter", "无效步骤！": "msg_invalid_step",
    "轰！游戏结束！": "msg_boom",
    "检查": "btn_check", "提交": "btn_submit", "撤销": "btn_undo", "打乱": "btn_shuffle",
    # Hangman feedback (built with f-strings in the draw path).
    "'{letter}' 在单词中！": "hangman_hit",
    "'{letter}' 猜错了！({wrong}/{total})": "hangman_miss",
    "游戏结束！单词: {word}": "hangman_over",
    "你已经试过 '{letter}' 了！": "hangman_repeat",
    "已错: ": "hangman_wrong_prefix",
    # Colour-sequence feedback and the swatch labels.
    "正确！做得好！": "cs_correct",
    "序列错误！当前回合失败。": "cs_wrong",
    "正确": "cs_correct_marker",
    "红色": "color_red", "绿色": "color_green", "蓝色": "color_blue", "黄色": "color_yellow",
}

#: Dispatch: displayed label -> stable key (line based, stripped text + indent).
DISPATCH: list[tuple[int, str, str]] = [
    (20, 'if btn.text == "提示":', 'if btn.key == "btn_hint":'),
    (20, 'elif btn.text == "跳过":', 'elif btn.key == "btn_skip":'),
    (20, 'elif btn.text == "菜单":', 'elif btn.key == "btn_menu":'),
    (20, 'elif btn.text == "下一题":', 'elif btn.key == "btn_next":'),
    (20, 'if digit == "删除":', 'if btn.key == "btn_delete":'),
    (20, 'elif digit == "确定":', 'elif btn.key == "btn_ok":'),
    (24, 'if btn.text == "检查":', 'if btn.key == "btn_check":'),
    (20, 'if btn.text == "确定":', 'if btn.key == "btn_ok":'),
    (20, 'elif btn.text == "删除":', 'elif btn.key == "btn_delete":'),
    (20, 'if btn.text == "提交":', 'if btn.key == "btn_submit":'),
    (20, 'elif btn.text == "撤销":', 'elif btn.key == "btn_undo":'),
    (20, 'if btn.text == "检查":', 'if btn.key == "btn_check":'),
    (20, 'elif btn.text == "打乱":', 'elif btn.key == "btn_shuffle":'),
]

#: f-strings that need their placeholders passed explicitly.
FSTRINGS: list[tuple[str, str]] = [
    ('f"分数: {self.engine.state.score}  连胜: {self.engine.state.streak}"',
     'tr("score_streak", self.lang, **{"self.engine.state.score": self.engine.state.score, "self.engine.state.streak": self.engine.state.streak})'),
    ('f"用时: {elapsed}秒"', 'tr("time", self.lang, elapsed=elapsed)'),
    ('f"提示: {hint}"', 'tr("hint_bar", self.lang, text=hint)'),
    ('msg = "正确!" if correct else "错误!"', 'msg = tr("correct" if correct else "wrong", self.lang)'),
    ('f"+{pts} 分"', 'tr("points", self.lang, points=pts)'),
    ('f"时间加成: +{tb}  连胜加成: +{sb}"', 'tr("bonus_detail", self.lang, time_bonus=tb, streak_bonus=sb)'),
    ('f"猜一个 {data[\'low\']} 到 {data[\'high\']} 之间的数字"',
     'tr("guess_prompt", self.lang, **{"data[\'low\']": data["low"], "data[\'high\']": data["high"]})'),
    ('f"尝试次数: {data[\'attempts\']}/{data[\'max_attempts\']}"',
     'tr("guess_attempts", self.lang, **{"data[\'attempts\']": data["attempts"], "data[\'max_attempts\']": data["max_attempts"]})'),
    ('f"已猜: {g}"', 'tr("guess_previous", self.lang, g=g)'),
    ('f"变换 \'{data[\'start\'].upper()}\' → \'{data[\'end\'].upper()}\'"',
     'tr("ladder_prompt", self.lang, **{"data[\'start\'].upper()": data["start"].upper(), "data[\'end\'].upper()": data["end"].upper()})'),
    ('f"剩余地雷: {mines_left}"', 'tr("mines_left", self.lang, mines_left=mines_left)'),
    ('f"当前: {attempt}"', 'tr("anagram_current", self.lang, attempt=attempt)'),
    ('f"步数: {puzzle.data[\'moves\']}  配对: {puzzle.data[\'pairs_found\']}/{puzzle.data[\'pairs\']}"',
     'tr("memory_moves", self.lang, **{"puzzle.data[\'moves\']": puzzle.data["moves"], "puzzle.data[\'pairs_found\']": puzzle.data["pairs_found"], "puzzle.data[\'pairs\']": puzzle.data["pairs"]})'),
    ('f"剩余猜测次数: {remaining}"', 'tr("hangman_left", self.lang, remaining=remaining)'),
    ('f"分数: {puzzle.data[\'score\']}  |  目标: {puzzle.data[\'target\']}"',
     'tr("board_score", self.lang, **{"puzzle.data[\'score\']": puzzle.data["score"], "puzzle.data[\'target\']": puzzle.data["target"]})'),
    ('f"你的输入: {done}  ({idx}/{len(seq)})"',
     'tr("colors_progress", self.lang, **{"done": done, "idx": idx, "len(seq)": len(seq)})'),
    ('f"序列长度: {len(seq)}"', 'tr("colors_length", self.lang, **{"len(seq)": len(seq)})'),
    # colour puzzle: delegate naming to the puzzle, which knows the language
    ('from gameplay_pool.color_sequence import COLOR_RGB, COLOR_BRIGHT, COLOR_CN, CN_TO_EN',
     'from gameplay_pool.color_sequence import COLOR_RGB, COLOR_BRIGHT, COLORS'),
    ('color_en = CN_TO_EN.get(color, color)\n                            result = puzzle.press_color(color_en)',
     'result = puzzle.press_color(color)'),
    ('done = ", ".join(COLOR_CN.get(c, c) for c in puzzle.data["player_input"])',
     'done = ", ".join(puzzle.color_label(c) for c in puzzle.data["player_input"])'),
    ('colors_en = ["red", "green", "blue", "yellow"]', 'colors_en = COLORS'),
]


def _label_call(key: str) -> str:
    """``"开始"`` in a render/Button call becomes ``tr("start", self.lang)``."""
    return f'tr("{key}", self.lang)'


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    source = SOURCE.read_text(encoding="utf-8")
    missing: list[str] = []
    applied = 0

    def swap(old: str, new: str, label: str) -> None:
        nonlocal source, applied
        if old not in source:
            missing.append(label)
            return
        source = source.replace(old, new)
        applied += 1

    swap(HEADER_OLD, HEADER_NEW, "header imports")
    swap(CONSTANTS_OLD, CONSTANTS_NEW, "constants/FOOTER_KEYS")
    swap(BUTTON_OLD, BUTTON_NEW, "Button key parameter")
    swap(FONT_OLD, FONT_NEW, "font loader")
    swap(FONT_CALLS_OLD, FONT_CALLS_NEW, "font call sites")
    swap(UI_INIT_OLD, UI_INIT_NEW, "UI.__init__ lang")
    swap(MODE_OLD, MODE_NEW, "mode options")
    swap(MODE_IDX_OLD, MODE_IDX_NEW, "mode default index")
    swap(MODE_LABELS_OLD, MODE_LABELS_NEW, "mode labels")
    swap(DIFF_LABELS_OLD, DIFF_LABELS_NEW, "difficulty labels")
    swap(HINT_BAR_OLD, HINT_BAR_NEW, "hint bar position")
    swap(FOOTER_OLD, FOOTER_NEW, "footer labels")
    swap(FOOTER_LOOP_OLD, FOOTER_LOOP_NEW, "footer button keys")
    swap(KEYPAD_OLD, KEYPAD_NEW, "keypad roles")
    swap('pygame.display.set_caption("解谜游戏")', 'pygame.display.set_caption(tr("caption", self.lang))', "window caption")
    swap('keys = [str(i) for i in range(10)] + ["删除", "确定"]',
         'keys = [str(i) for i in range(10)] + [tr("btn_delete", self.lang), tr("btn_ok", self.lang)]',
         "keypad key labels")
    swap('if "次数用完了" in hint:', 'if tr("msg_out_of_attempts", self.lang) in hint:', "out-of-attempts detection")
    swap('f"\'{letter}\' 在单词中！"', 'tr("hangman_hit", self.lang, **{"\'{letter}\'": letter})', "hangman hit")
    swap('f"\'{letter}\' 猜错了！({len(puzzle.data[\'wrong\'])}/{puzzle.data[\'max_wrong\']})"',
         'tr("hangman_miss", self.lang, **{"\'{letter}\'": letter, "len(puzzle.data[\'wrong\'])": len(puzzle.data["wrong"]), "puzzle.data[\'max_wrong\']": puzzle.data["max_wrong"]})',
         "hangman miss")
    swap('f"游戏结束！单词: {puzzle.data[\'word\'].upper()}"',
         'tr("hangman_over", self.lang, **{"puzzle.data[\'word\'].upper()": puzzle.data["word"].upper()})',
         "hangman over")
    swap('f"你已经试过 \'{letter}\' 了！"', 'tr("hangman_repeat", self.lang, **{"\'{letter}\'": letter})', "hangman repeat")
    swap('wrong_str = "已错: " + " ".join(sorted(puzzle.data["wrong"])).upper()',
         'wrong_str = tr("hangman_wrong_prefix", self.lang) + " ".join(sorted(puzzle.data["wrong"])).upper()',
         "hangman wrong prefix")
    swap('self._cs_feedback_msg = "正确！做得好！"', 'self._cs_feedback_msg = tr("cs_correct", self.lang)', "colour-sequence correct")
    swap('self._cs_feedback_msg = "序列错误！当前回合失败。"', 'self._cs_feedback_msg = tr("cs_wrong", self.lang)', "colour-sequence wrong")
    swap('color = C_GREEN if "正确" in self._cs_feedback_msg else C_RED',
         'color = C_GREEN if tr("cs_correct_marker", self.lang) in self._cs_feedback_msg else C_RED',
         "colour-sequence feedback colour")
    swap('colors = ["红色", "绿色", "蓝色", "黄色"]',
         'colors = [tr(f"color_{name}", self.lang) for name in SWATCH_ORDER]',
         "colour swatch labels")
    for old, new in FSTRINGS:
        swap(old, new, f"f-string {old[:34]}")

    # Dispatch first: it matches on the legacy label literals, so it must run before
    # the label sweep replaces them (running the sweep first rewrote the comparisons
    # into `if btn.text == tr(...)`, which is a tautology that never fires).
    lines = source.splitlines(keepends=True)
    for indent, stripped, replacement in DISPATCH:
        hit = 0
        for index, line in enumerate(lines):
            if line.strip() == stripped and line[: len(line) - len(line.lstrip())] == " " * indent:
                lines[index] = " " * indent + replacement + "\n"
                hit += 1
        if hit:
            applied += hit
        else:
            missing.append(f"dispatch {stripped}")
    source = "".join(lines)

    # Then the remaining label literals, in one sweep.
    for literal, key in LABELS.items():
        for pattern in (f'"{literal}"', f"'{literal}'"):
            if pattern in source:
                source = source.replace(pattern, _label_call(key))
                applied += 1

    leftovers = [line.strip() for line in source.splitlines() if re.search(r"[\u4e00-\u9fff]", line)
                 and not line.strip().startswith(("#", '"""', '"'))]
    print(f"{'applied' if apply else 'would apply'} {applied} edit(s)")
    if missing:
        print(f"\nNOT FOUND ({len(missing)}):")
        for line in missing:
            print("  " + line)
    if leftovers:
        print(f"\nCJK still in {len(leftovers)} code line(s):")
        for line in leftovers[:12]:
            print("  " + line[:78])
    if apply and not missing:
        TARGET.write_text(source, encoding="utf-8", newline="\n")
        print(f"\nwrote {TARGET.relative_to(ROOT)}")
    elif apply:
        print("\nrefusing to write while edits are unresolved")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
