"""RiddlePuzzle: brain-teaser riddles with multiple choice."""

import random
from .base_puzzle import BasePuzzle

RIDDLES: list[dict] = [
    {
        "question": "我有键却没有锁，我有空间却没有房间。你可以进入却不能走进去。我是什么？",
        "options": ["键盘", "房子", "汽车", "书"],
        "answer": 0,
    },
    {
        "question": "什么东西有手却不能拍手？",
        "options": ["钟表", "机器人", "猴子", "手套"],
        "answer": 0,
    },
    {
        "question": "什么东西有头有尾却没有身体？",
        "options": ["蛇", "硬币", "狗", "钉子"],
        "answer": 1,
    },
    {
        "question": "我没有嘴却能说话，没有耳朵却能听见。我没有身体，却随风而生。我是什么？",
        "options": ["鬼魂", "树", "回声", "旗帜"],
        "answer": 2,
    },
    {
        "question": "什么东西越擦越湿？",
        "options": ["海绵", "毛巾", "雨", "太阳"],
        "answer": 1,
    },
    {
        "question": "我可以被敲碎、编造、讲述和演奏。我是什么？",
        "options": ["笑话", "玻璃", "唱片", "鸡蛋"],
        "answer": 0,
    },
    {
        "question": "什么东西有很多牙齿却不能咬？",
        "options": ["狗", "锯子", "梳子", "齿轮"],
        "answer": 2,
    },
    {
        "question": "什么东西只升不降？",
        "options": ["气球", "年龄", "温度", "鸟"],
        "answer": 1,
    },
    {
        "question": "什么东西有一只眼却看不见？",
        "options": ["针", "海盗", "风暴", "相机"],
        "answer": 0,
    },
    {
        "question": "我不是活的，却会生长；我没有肺，却需要空气。我是什么？",
        "options": ["植物", "火", "水", "气球"],
        "answer": 1,
    },
    {
        "question": "什么东西可以环游世界却待在角落里？",
        "options": ["飞机", "邮票", "互联网", "卫星"],
        "answer": 1,
    },
    {
        "question": "什么东西有环却没有手指？",
        "options": ["电话", "星球", "钟", "树"],
        "answer": 0,
    },
]


class RiddlePuzzle(BasePuzzle):
    puzzle_name = "谜语"
    puzzle_type = "content"
    content_kind = "riddles"

    def _generate(self) -> None:
        # Prefer the content pack (data, editable without touching code); the
        # RIDDLES list above stays as the fallback for a pack-less checkout.
        item = self.pick_content()
        riddle = item if item is not None else random.choice(RIDDLES)
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
        return f"正确答案以'{first_char}'开头"
