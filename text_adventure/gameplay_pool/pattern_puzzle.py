"""PatternPuzzle: identify the pattern in a number/shape sequence."""

import random
from .base_puzzle import BasePuzzle


class PatternPuzzle(BasePuzzle):
    puzzle_name = "Pattern"
    puzzle_type = "generated"

    def _generate(self) -> None:
        generators = [
            self._gen_arithmetic,
            self._gen_geometric,
            self._gen_square,
            self._gen_fibonacci,
            self._gen_power,
        ]

        if self.difficulty == "easy":
            gen = random.choice(generators[:2])
        elif self.difficulty == "medium":
            gen = random.choice(generators[:4])
        else:
            gen = random.choice(generators)

        sequence, answer, rule = gen()
        options = self._make_options(answer)

        self.data = {
            "sequence": sequence,
            "answer": answer,
            "rule": rule,
            "options": options,
        }

    def _gen_arithmetic(self) -> tuple[list[int], int, str]:
        start = random.randint(1, 10)
        diff = random.randint(2, 7)
        seq = [start + i * diff for i in range(6)]
        return seq[:5], seq[5], f"+{diff} each time"

    def _gen_geometric(self) -> tuple[list[int], int, str]:
        start = random.randint(1, 3)
        ratio = random.randint(2, 3)
        seq = [start * (ratio ** i) for i in range(6)]
        return seq[:5], seq[5], f"x{ratio} each time"

    def _gen_square(self) -> tuple[list[int], int, str]:
        offset = random.randint(0, 2)
        seq = [(i + offset) ** 2 for i in range(1, 7)]
        return seq[:5], seq[5], "Perfect squares"

    def _gen_fibonacci(self) -> tuple[list[int], int, str]:
        a, b = random.randint(1, 3), random.randint(1, 3)
        seq = [a, b]
        for _ in range(4):
            seq.append(seq[-1] + seq[-2])
        return seq[:5], seq[5], "Each number = sum of two before"

    def _gen_power(self) -> tuple[list[int], int, str]:
        base = random.randint(2, 4)
        seq = [base ** i for i in range(6)]
        return seq[:5], seq[5], f"Powers of {base}"

    def _make_options(self, answer: int) -> list[int]:
        options = {answer}
        while len(options) < 4:
            offset = random.choice([-3, -2, -1, 1, 2, 3, 5, -5])
            opt = answer + offset
            if opt > 0 and opt != answer:
                options.add(opt)
        opts = sorted(options)
        random.shuffle(opts)
        return opts

    def check_answer(self, answer: Any) -> bool:
        return int(answer) == self.data["answer"]

    def get_hint(self) -> str:
        return f"Rule: {self.data['rule']}"
