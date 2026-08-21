# -*- coding: utf-8 -*-
"""跨局技能树（Phase 6 剩余）：角色 8 节点 ×3 + 众神 3 节点 ×6。

节点用金币购买、永久生效于后续所有局；存档在 save.py 的
char_levels / god_levels（{key: [等级列表]}）。
"""
CHAR_NODES = [
    ("生命强化", "hp", 25, 3),      # +25 生命上限 / 级
    ("战斗本能", "dmg", 0.08, 3),   # +8% 伤害 / 级
    ("急速", "cdr", 0.04, 3),       # -4% 冷却 / 级
    ("疾风", "speed", 0.05, 3),     # +5% 移速 / 级
    ("技艺", "skill_cd", 0.06, 3),  # -6% 主动技冷却 / 级
    ("磁力", "pickup", 0.20, 3),    # +20% 拾取范围 / 级
    ("暴击", "crit", 0.03, 3),      # +3% 暴击率 / 级
    ("贤者", "xp", 0.10, 3),        # +10% 经验 / 级
]

GOD_NODES = {
    "odin": [("渡鸦凝视", "crit", 0.04, 3), ("智慧", "xp", 0.12, 3),
             ("符文", "dmg", 0.05, 3)],
    "thor": [("雷霆之躯", "hp", 20, 3), ("震怒", "crit", 0.03, 3),
             ("神力", "dmg", 0.05, 3)],
    "freya": [("生命礼赞", "hp", 20, 3), ("慈爱", "xp", 0.08, 3),
              ("迅风", "speed", 0.04, 3)],
    "loki": [("诡诈", "crit", 0.05, 3), ("掠夺", "xp", 0.10, 3),
             ("轻盈", "speed", 0.03, 3)],
    "heimdall": [("守望", "cdr", 0.03, 3), ("号角", "skill_cd", 0.05, 3),
                 ("鹰眼", "dmg", 0.04, 3)],
    "skadi": [("寒冬", "dmg", 0.05, 3), ("猎手", "speed", 0.04, 3),
              ("冰心", "hp", 18, 3)],
}

MAX_NODE_LEVEL = 3


def cost(level):
    """第 level 级 -> level+1 级的售价。"""
    return 400 * (level + 1)


def level_of(sd, mode, idx, node_idx):
    if mode == "char":
        return sd.char_levels.get(idx, [0] * len(CHAR_NODES))[node_idx]
    return sd.god_levels.get(idx, [0] * len(GOD_NODES[idx]))[node_idx]


def can_buy(sd, mode, idx, node_idx):
    lv = level_of(sd, mode, idx, node_idx)
    return lv < MAX_NODE_LEVEL and sd.gold >= cost(lv)


def buy(sd, mode, idx, node_idx):
    """购买一级；成功扣款并返回 True。"""
    if not can_buy(sd, mode, idx, node_idx):
        return False
    lv = level_of(sd, mode, idx, node_idx)
    sd.gold -= cost(lv)
    if mode == "char":
        lst = list(sd.char_levels.get(idx, [0] * len(CHAR_NODES)))
        lst[node_idx] += 1
        sd.char_levels[idx] = lst
    else:
        lst = list(sd.god_levels.get(idx, [0] * len(GOD_NODES[idx])))
        lst[node_idx] += 1
        sd.god_levels[idx] = lst
    return True


def bonus_of(sd):
    """汇总两棵树的等级为玩家 meta 加成字典（开局时应用到 Player）。"""
    b = dict(hp=0, dmg=0.0, cdr=0.0, speed=0.0, skill_cd=0.0,
             pickup=0.0, crit=0.0, xp=0.0)

    def add(key, val, lvl):
        if lvl <= 0:
            return
        b[key] += val * lvl

    for i, (name, key, val, mx) in enumerate(CHAR_NODES):
        add(key, val, level_of(sd, "char", "berserker", i))
    for g, nodes in GOD_NODES.items():
        for i, (name, key, val, mx) in enumerate(nodes):
            add(key, val, level_of(sd, "god", g, i))
    return b
