"""ColorSequencePuzzle: Simon Says memory sequence game."""

import random
from typing import Any
from .base_puzzle import BasePuzzle

COLORS = ["red", "blue", "green", "yellow"]
COLOR_CN = {
    "red": "红色",
    "green": "绿色",
    "blue": "蓝色",
    "yellow": "黄色",
}
CN_TO_EN = {v: k for k, v in COLOR_CN.items()}
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


class ColorSequencePuzzle(BasePuzzle):
    puzzle_name = "颜色序列"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            length, show_time = 3, 0.8
        elif self.difficulty == "medium":
            length, show_time = 5, 0.6
        else:
            length, show_time = 7, 0.4

        sequence = [random.choice(COLORS) for _ in range(length)]
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

    def get_hint(self) -> str:
        seq = self.data["sequence"]
        idx = self.data["player_index"]
        if idx < len(seq):
            remaining = [COLOR_CN.get(c, c) for c in seq[idx:]]
            shown = [COLOR_CN.get(c, c) for c in seq[:idx]]
            return f"已完成: {' '.join(shown) if shown else '无'} | 下一个: {remaining[0]}"
        return "已输入完整个序列！"
