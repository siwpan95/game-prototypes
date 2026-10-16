"""GuessNumberPuzzle: guess a randomly generated number with hints."""

from typing import Any

from .base_puzzle import BasePuzzle


class GuessNumberPuzzle(BasePuzzle):
    kind = "guess_number"
    puzzle_name = "猜数字"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            low, high = 1, 50
        elif self.difficulty == "medium":
            low, high = 1, 100
        else:
            low, high = 1, 500

        target = self._rng().randint(low, high)
        self.data = {
            "target": target,
            "low": low,
            "high": high,
            "guesses": [],
            "last_hint": "",
            "attempts": 0,
            "max_attempts": 10 if self.difficulty == "easy" else 8 if self.difficulty == "medium" else 6,
        }

    def check_answer(self, answer: Any) -> bool:
        guess = int(answer)
        self.data["attempts"] += 1
        self.data["guesses"].append(guess)

        if guess == self.data["target"]:
            return True
        elif guess < self.data["target"]:
            self.data["last_hint"] = self.word("higher")
            self.data["low"] = max(self.data["low"], guess + 1)
        else:
            self.data["last_hint"] = self.word("lower")
            self.data["high"] = min(self.data["high"], guess - 1)

        if self.data["attempts"] >= self.data["max_attempts"]:
            self.data["last_hint"] = self.msg(
                "guess_out_of_attempts", target=self.data["target"]
            )

        return False

    def get_hint(self) -> str:
        return self.word("guess_even" if self.data["target"] % 2 == 0 else "guess_odd")
