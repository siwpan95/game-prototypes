"""MathPuzzle: arithmetic problems at varying difficulties."""

import random
from .base_puzzle import BasePuzzle


class MathPuzzle(BasePuzzle):
    puzzle_name = "数学题"
    puzzle_type = "content"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            a = random.randint(1, 20)
            b = random.randint(1, 20)
            op = random.choice(["+", "-"])
            if op == "-" and a < b:
                a, b = b, a
        elif self.difficulty == "medium":
            a = random.randint(2, 12)
            b = random.randint(2, 12)
            op = random.choice(["+", "-", "*"])
            if op == "-" and a < b:
                a, b = b, a
        else:  # hard
            a = random.randint(2, 15)
            b = random.randint(2, 15)
            op = random.choice(["+", "-", "*", "/"])
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
        length = len(str(ans))
        return f"答案有{length}位数，以{str(ans)[0]}开头"
