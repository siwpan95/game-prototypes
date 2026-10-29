"""ColorSequencePuzzle: remember and repeat a growing colour sequence.

The colour names in ``data`` are always the English keys (``red``, ...): the
pygame client maps them to screen colours through ``COLOR_RGB`` / ``COLOR_BRIGHT``
and shows the Chinese word from ``messages.COLOR_WORDS_ZH``. Only the *display*
differs per language, which is what ``get_hint`` handles.
"""

from typing import Any

from . import messages
from .base_puzzle import BasePuzzle

COLORS = ["red", "blue", "green", "yellow"]

COLOR_RGB = {
    "red": (220, 80, 80),
    "green": (80, 200, 120),
    "blue": (80, 140, 230),
    "yellow": (230, 200, 70),
}
COLOR_BRIGHT = {
    "red": (255, 120, 120),
    "green": (120, 255, 160),
    "blue": (120, 180, 255),
    "yellow": (255, 230, 120),
}

#: Kept for the pygame client, which uses it for on-screen labels and for mapping a
#: Chinese word back to the colour key. The authoritative table is in ``messages``.
COLOR_CN = dict(messages.COLOR_WORDS_ZH)
CN_TO_EN = {value: key for key, value in COLOR_CN.items()}


class ColorSequencePuzzle(BasePuzzle):
    kind = "color_sequence"
    puzzle_name = "颜色序列"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            length, show_time = 3, 0.8
        elif self.difficulty == "medium":
            length, show_time = 5, 0.6
        else:
            length, show_time = 7, 0.4

        sequence = [self._rng().choice(COLORS) for _ in range(length)]
        self.data = {
            "sequence": sequence,
            "player_index": 0,
            "phase": "show",       # show | input | feedback
            "current_flash": -1,    # index currently flashing during show phase
            "player_input": [],
            "correct": True,
            "length": length,
            "show_time": show_time,
            "round": 1,
        }

    def press_color(self, color: str) -> str:
        """Player presses a color during input phase.
        Returns 'continue', 'wrong', or 'win'."""
        if self.data["phase"] != "input":
            return "continue"

        if color not in COLORS:
            return "continue"

        seq = self.data["sequence"]
        idx = self.data["player_index"]

        if color != seq[idx]:
            self.data["correct"] = False
            self.data["phase"] = "feedback"
            return "wrong"

        self.data["player_index"] = idx + 1
        self.data["player_input"].append(color)

        if self.data["player_index"] >= len(seq):
            self.data["phase"] = "feedback"
            return "win"

        return "continue"

    def start_input_phase(self) -> None:
        """Switch from show phase to input phase."""
        self.data["phase"] = "input"
        self.data["player_index"] = 0
        self.data["player_input"] = []
        self.data["current_flash"] = -1

    def check_answer(self, answer: Any) -> bool:
        return self.data["correct"] and self.data["player_index"] >= len(self.data["sequence"])

    def color_label(self, color: str) -> str:
        """A colour as this language spells it.

        Public because clients render colour names too (the pygame client's status
        line, the terminal client's "your input" line); the two legacy builds
        disagreed here — Chinese used 红色/绿色, English used ``.title()`` — so both
        spellings are preserved rather than one being chosen.
        """
        if self.lang == "zh":
            return COLOR_CN.get(color, color)
        return color.title()

    def _color_label(self, color: str) -> str:
        """Backwards-compatible alias for :meth:`color_label`."""
        return self.color_label(color)

    def get_hint(self) -> str:
        seq = self.data["sequence"]
        idx = self.data["player_index"]
        if idx >= len(seq):
            return self.word("colors_done")
        shown = [self._color_label(colour) for colour in seq[:idx]]
        return self.msg(
            "colors_progress",
            shown=" ".join(shown) if shown else self.word("colors_none"),
            next=self._color_label(seq[idx]),
        )
