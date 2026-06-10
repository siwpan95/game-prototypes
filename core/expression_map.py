"""
签到结果 → 表情映射
"""

RARITY_EXPRESSION_MAP = {
    "普通": "happy",
    "稀有": "excited",
    "史诗": "amazed",
    "传说": "surprised",
    "神话": "love",
}

NO_REWARD_EXPRESSION_MAP = {
    1: "bored",
    2: "disappointed",
    3: "sad",
    5: "worried",
    8: "annoyed",
    12: "angry",
}


def result_to_expression(result):
    """将签到结果映射为表情名"""
    if result["reinforced"]:
        rarity = result["reward"].get("rarity", "普通")
        return RARITY_EXPRESSION_MAP.get(rarity, "happy")
    else:
        streak = result["no_reward_streak"]
        expr = "bored"
        for threshold, e in sorted(NO_REWARD_EXPRESSION_MAP.items()):
            if streak >= threshold:
                expr = e
        return expr
