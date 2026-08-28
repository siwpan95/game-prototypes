"""
里程碑成就系统
依据 Duolingo 习惯研究：连续 7 天的用户完成课程的可能性提升 3.6 倍，
里程碑节点（7/14/30…）是习惯养成的关键锚点，应给予醒目庆祝。
"""

# (类型, 阈值) -> (标题, 描述, 表情)
STREAK_MILESTONES = [
    (3,   "小试牛刀", "连续签到 3 天", "happy"),
    (7,   "一周达人", "连续签到 7 天，习惯正在养成！", "excited"),
    (14,  "半月坚守", "连续签到 14 天", "proud"),
    (30,  "月度传奇", "连续签到 30 天，了不起！", "amazed"),
    (60,  "六十连击", "连续签到 60 天", "cool"),
    (100, "百日筑基", "连续签到 100 天，登峰造极！", "love"),
]

TOTAL_MILESTONES = [
    (10,  "初入江湖", "累计签到 10 次", "happy"),
    (50,  "轻车熟路", "累计签到 50 次", "proud"),
    (100, "百炼成钢", "累计签到 100 次", "amazed"),
    (365, "全年无休", "累计签到 365 次，硬核玩家！", "love"),
]


def check_new_milestones(n, c, unlocked):
    """
    检查本次签到解锁的新里程碑。
    n: 总签到次数, c: 当前连续天数, unlocked: 已解锁 id 集合
    返回 [milestone_dict, ...]，并把新 id 加入 unlocked
    """
    new = []
    for threshold, title, desc, expr in STREAK_MILESTONES:
        mid = f"streak_{threshold}"
        if c >= threshold and mid not in unlocked:
            unlocked.add(mid)
            new.append({"id": mid, "title": title, "desc": desc,
                        "expr": expr, "kind": "streak", "threshold": threshold})
    for threshold, title, desc, expr in TOTAL_MILESTONES:
        mid = f"total_{threshold}"
        if n >= threshold and mid not in unlocked:
            unlocked.add(mid)
            new.append({"id": mid, "title": title, "desc": desc,
                        "expr": expr, "kind": "total", "threshold": threshold})
    return new


def all_milestones():
    """返回全部里程碑定义（用于成就展示）"""
    out = []
    for threshold, title, desc, expr in STREAK_MILESTONES:
        out.append({"id": f"streak_{threshold}", "title": title, "desc": desc,
                    "kind": "streak", "threshold": threshold})
    for threshold, title, desc, expr in TOTAL_MILESTONES:
        out.append({"id": f"total_{threshold}", "title": title, "desc": desc,
                    "kind": "total", "threshold": threshold})
    return out
