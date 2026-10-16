"""HangmanPuzzle: classic word guessing game."""

import random
from typing import Any
from .base_puzzle import BasePuzzle

# Word bank categorized by difficulty
WORD_BANK = {
    "easy": [
        "apple", "beach", "candy", "dance", "eagle", "flame", "grape", "happy",
        "igloo", "joker", "koala", "lemon", "magic", "noble", "ocean", "piano",
        "queen", "river", "smile", "tiger", "umbra", "vivid", "whale", "youth",
        "zebra", "angel", "brave", "crane", "dream", "frost",
    ],
    "medium": [
        "balloon", "captain", "diamond", "elephant", "fortune", "giraffe",
        "horizon", "injury", "justice", "kitchen", "lantern", "monster",
        "nursery", "october", "penguin", "quality", "rainbow", "shelter",
        "trouble", "universe", "village", "warrior", "anxiety", "bracket",
        "crystal", "dolphin", "emerald", "fantasy", "gravity", "harmony",
    ],
    "hard": [
        "labyrinth", "masterpiece", "nightingale", "orchestra",
        "philosopher", "quarantine", "revolution", "silhouette",
        "thermometer", "ultraviolet", "ventriloquy", "wonderland",
        "xylophone", "zoological", "abominable", "beneficial",
        "camouflage", "delinquent", "exaggerate", "fashionable",
        "gentlemanly", "holographic", "imaginative", "jurisdiction",
        "kaliedoscope", "lamentation", "magnificent", "negotiation",
        "opposition", "phenomenon",
    ],
}


class HangmanPuzzle(BasePuzzle):
    puzzle_name = "猜单词"
    puzzle_type = "content"
    content_kind = "hangman_words"

    def _generate(self) -> None:
        item = self.pick_content()
        if item is not None:
            word = str(item["word"])
        else:
            word = random.choice(WORD_BANK.get(self.difficulty, WORD_BANK["medium"]))
        self.data = {
            "word": word,
            "guessed": set[str](),
            "wrong": set[str](),
            "max_wrong": 6,
            "hint_used": False,
        }

    def guess_letter(self, letter: str) -> str:
        """Guess a letter. Returns 'correct', 'wrong', 'duplicate', or 'win'."""
        letter = letter.lower()
        if not letter.isalpha() or len(letter) != 1:
            return "invalid"

        if letter in self.data["guessed"] or letter in self.data["wrong"]:
            return "duplicate"

        if letter in self.data["word"]:
            self.data["guessed"].add(letter)
            if self._all_revealed():
                return "win"
            return "correct"
        else:
            self.data["wrong"].add(letter)
            if len(self.data["wrong"]) >= self.data["max_wrong"]:
                return "game_over"
            return "wrong"

    def _all_revealed(self) -> bool:
        return all(ch in self.data["guessed"] for ch in self.data["word"])

    def get_display(self) -> str:
        return " ".join(ch if ch in self.data["guessed"] else "_" for ch in self.data["word"])

    def check_answer(self, answer: Any) -> bool:
        return self._all_revealed()

    def get_hint(self) -> str:
        if not self.data["hint_used"]:
            self.data["hint_used"] = True
            # Reveal the first unrevealed letter
            for ch in self.data["word"]:
                if ch not in self.data["guessed"]:
                    return f"单词包含'{ch.upper()}'"
        return f"单词有{len(self.data['word'])}个字母: {self.get_display()}"
