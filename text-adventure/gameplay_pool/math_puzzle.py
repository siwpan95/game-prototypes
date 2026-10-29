"""MathPuzzle: arithmetic problems at varying difficulties."""

from typing import Any

from .base_puzzle import BasePuzzle


class MathPuzzle(BasePuzzle):
    kind = "math"
    puzzle_name = "数学题"  # default language; instance attribute picks the real one
    puzzle_type = "content"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            a = self._rng().randint(1, 20)
            b = self._rng().randint(1, 20)
            op = self._rng().choice(["+", "-"])
            if op == "-" and a < b:
                a, b = b, a
        elif self.difficulty == "medium":
            a = self._rng().randint(2, 12)
            b = self._rng().randint(2, 12)
            op = self._rng().choice(["+", "-", "*"])
            if op == "-" and a < b:
                a, b = b, a
        else:  # hard
            a = self._rng().randint(2, 15)
            b = self._rng().randint(2, 15)
            op = self._rng().choice(["+", "-", "*", "/"])
            if op == "/":
                a = a * b  # ensure clean division
            elif op == "-" and a < b:
                a, b = b, a

        expr = f"{a} {op} {b}"
        answer = eval(expr)
        self.data = {
            "expression": expr,
            "answer": int(answer),
        }

    def check_answer(self, answer: Any) -> bool:
        return int(answer) == self.data["answer"]

    def get_hint(self) -> str:
        ans = self.data["answer"]
        return self.msg("math_hint", length=len(str(ans)), first=str(ans)[0])
