"""GuessNumberPuzzle: guess a randomly generated number with hints."""

import random
from .base_puzzle import BasePuzzle


class GuessNumberPuzzle(BasePuzzle):
    puzzle_name = "猜数字"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            low, high = 1, 50
        elif self.difficulty == "medium":
            low, high = 1, 100
        else:
            low, high = 1, 500

        target = random.randint(low, high)
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
            self.data["last_hint"] = "大一点！"
            self.data["low"] = max(self.data["low"], guess + 1)
        else:
            self.data["last_hint"] = "小一点！"
            self.data["high"] = min(self.data["high"], guess - 1)

        if self.data["attempts"] >= self.data["max_attempts"]:
            self.data["last_hint"] = f"次数用完了！答案是{self.data['target']}"

        return False

    def get_hint(self) -> str:
        target = self.data["target"]
        if target % 2 == 0:
            return "这个数是偶数"
        return "这个数是奇数"
