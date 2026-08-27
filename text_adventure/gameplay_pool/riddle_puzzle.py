"""RiddlePuzzle: brain-teaser riddles with multiple choice."""

import random
from .base_puzzle import BasePuzzle

RIDDLES: list[dict] = [
    {
        "question": "I have keys but no locks. I have space but no room. You can enter but can't go inside. What am I?",
        "options": ["A keyboard", "A house", "A car", "A book"],
        "answer": 0,
    },
    {
        "question": "What has hands but can't clap?",
        "options": ["A clock", "A robot", "A monkey", "A glove"],
        "answer": 0,
    },
    {
        "question": "What has a head and a tail but no body?",
        "options": ["A snake", "A coin", "A dog", "A nail"],
        "answer": 1,
    },
    {
        "question": "I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. What am I?",
        "options": ["A ghost", "A tree", "An echo", "A flag"],
        "answer": 2,
    },
    {
        "question": "What gets wetter the more it dries?",
        "options": ["A sponge", "A towel", "Rain", "The sun"],
        "answer": 1,
    },
    {
        "question": "I can be cracked, made, told, and played. What am I?",
        "options": ["A joke", "A glass", "A record", "An egg"],
        "answer": 0,
    },
    {
        "question": "What has many teeth but can't bite?",
        "options": ["A dog", "A saw", "A comb", "A gear"],
        "answer": 2,
    },
    {
        "question": "What goes up but never comes down?",
        "options": ["A balloon", "Your age", "Temperature", "A bird"],
        "answer": 1,
    },
    {
        "question": "What has one eye but can't see?",
        "options": ["A needle", "A pirate", "A storm", "A camera"],
        "answer": 0,
    },
    {
        "question": "I am not alive, but I grow; I don't have lungs, but I need air. What am I?",
        "options": ["A plant", "Fire", "Water", "A balloon"],
        "answer": 1,
    },
    {
        "question": "What can travel around the world while staying in a corner?",
        "options": ["An airplane", "A stamp", "The Internet", "A satellite"],
        "answer": 1,
    },
    {
        "question": "What has a ring but no finger?",
        "options": ["A phone", "A planet", "A bell", "A tree"],
        "answer": 0,
    },
]


class RiddlePuzzle(BasePuzzle):
    puzzle_name = "Riddle"
    puzzle_type = "content"

    def _generate(self) -> None:
        riddle = random.choice(RIDDLES)
        self.data = {
            "question": riddle["question"],
            "options": list(riddle["options"]),
            "answer": riddle["answer"],
        }

    def check_answer(self, answer: Any) -> bool:
        return int(answer) == self.data["answer"]

    def get_hint(self) -> str:
        answer_idx = self.data["answer"]
        first_char = self.data["options"][answer_idx][0]
        return f"The correct answer starts with '{first_char}'"
