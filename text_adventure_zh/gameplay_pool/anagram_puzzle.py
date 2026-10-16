"""AnagramPuzzle: unscramble shuffled letters to form a word."""

import random
from .base_puzzle import BasePuzzle

WORDS: list[str] = [
    "python", "puzzle", "game", "code", "brain", "think", "logic",
    "smart", "quick", "solver", "words", "letter", "shift", "mind",
    "focus", "spark", "craft", "digit", "pixel", "stack",
    "quest", "riddle", "clue", "hint", "solve", "grid", "path",
    "find", "seek", "match", "sort", "flip", "tile", "turn",
    "swap", "link", "chain", "step", "move", "play",
]


class AnagramPuzzle(BasePuzzle):
    puzzle_name = "字谜"
    puzzle_type = "content"
    content_kind = "anagram_words"

    def _generate(self) -> None:
        item = self.pick_content()
        if item is not None:
            word = str(item["word"])
        else:
            if self.difficulty == "easy":
                pool = [w for w in WORDS if len(w) <= 4]
            elif self.difficulty == "medium":
                pool = [w for w in WORDS if 4 <= len(w) <= 6]
            else:
                pool = [w for w in WORDS if len(w) >= 5]

            if not pool:
                pool = WORDS

            word = random.choice(pool)
        letters = list(word)
        shuffled = letters[:]
        attempts = 0
        while shuffled == letters and attempts < 50:
            random.shuffle(shuffled)
            attempts += 1

        self.data = {
            "word": word,
            "shuffled": shuffled,
            "player_letters": list(shuffled),
            "solved": False,
        }

    def check_answer(self, answer: Any) -> bool:
        candidate = "".join(self.data["player_letters"]).lower()
        return candidate == self.data["word"].lower()

    def get_hint(self) -> str:
        word = self.data["word"]
        return f"第一个字母是'{word[0].upper()}'"

    def swap_letters(self, idx1: int, idx2: int) -> None:
        letters = self.data["player_letters"]
        if 0 <= idx1 < len(letters) and 0 <= idx2 < len(letters):
            letters[idx1], letters[idx2] = letters[idx2], letters[idx1]
