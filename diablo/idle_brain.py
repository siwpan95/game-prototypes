# -*- coding: utf-8 -*-
"""
挂机战斗决策大脑（Idle Brain）
============================

结合 ``<zhuangtaiji 仓根>/core`` 的**行为树（Behavior Tree）**引擎，
把原来"无脑平A"的挂机战斗换成有策略的决策：

    Selector(按优先级选第一个成立的)
      ├─ Sequence: 血量 < 15%            → 逃跑（保命优先）
      ├─ Sequence: 血量 < 40% 且敌人尚强 → 防御（减伤拖回合）
      ├─ Sequence: 蓝量够 且 敌人未残血   → 重击（爆发输出）
      └─ Action:                         → 普攻（兜底）

行为树每次 tick 读一块共享黑板（Blackboard）：玩家血量%、蓝量、敌人血量%，
选出一个动作直接驱动 GUI 的战斗方法。相比手写 if/elif，行为树的优势在于
"条件与动作可声明式组合、易扩展"（例如以后加"蓝量枯竭时嗑药"只加一个 Sequence）。

若 zhuangtaiji 引擎不可用（路径变更等），自动降级为"只普攻"，保证游戏仍可运行。
"""
import os
import sys

# ---- 接入 zhuangtaiji 的行为树内核（纯标准库，无第三方依赖）----
# 直接挂载其 core 目录并导入独立模块，避免触发整包 __init__，保持零耦合。
# 2026-09-23 去本地化：core 目录改为按「环境变量 → 仓内推导」候选列表解析，
# 不再使用已失效的本机绝对路径（原路径已不存在）。
# 候选优先级：
#   1) DIABLO_ZHUANGTAIJI_CORE —— 仓内既有变量名，直接指向 core 目录
#   2) ZHUANGTAIJI_ROOT        —— zhuangtaiji 仓根，取其下 core/
#   3) 仓内推导                 —— 与本仓同级的 zhuangtaiji 仓下 core/
_ZT_CORE_CANDIDATES = [
    os.environ.get("DIABLO_ZHUANGTAIJI_CORE", ""),
    (os.path.join(os.environ["ZHUANGTAIJI_ROOT"], "core")
     if os.environ.get("ZHUANGTAIJI_ROOT") else ""),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "zhuangtaiji", "core"),
]
# 取第一个真实存在的候选；一个都不存在则为空串，保持「引擎缺失即降级为纯普攻」的原语义
_ZT_CORE = next((c for c in _ZT_CORE_CANDIDATES if c and os.path.isdir(c)), "")
if _ZT_CORE and _ZT_CORE not in sys.path:
    sys.path.insert(0, _ZT_CORE)

try:
    from behavior_tree import (BehaviorTree, Blackboard, Selector, Sequence,
                               Condition, Action, Status)
    _HAS_BT = True
except Exception:  # pragma: no cover - 引擎缺失时降级
    _HAS_BT = False


class IdleBrain:
    """挂机决策大脑：基于行为树的战斗动作选择器。"""

    # 可调阈值（之后可下放进 settings.json 让用户自定义难度策略）
    HP_FLEE_PCT = 15       # 残血直接跑
    HP_DEFEND_PCT = 40     # 低血且敌人还硬 → 防御
    MP_HEAVY = 5           # 重击所需蓝量
    ENEMY_HEAVY_PCT = 25   # 敌人血量高于此才值得重击（残血普攻更省蓝）

    def __init__(self):
        self.enabled = _HAS_BT
        self.gui = None
        self._action_method = "combat_action"
        self._last_action = None
        self.blackboard = Blackboard() if self.enabled else None
        self.tree = self._build() if self.enabled else None
        if not self.enabled:
            print("提示：未找到 zhuangtaiji 行为树引擎，挂机战斗降级为纯普攻。"
                  "可用 DIABLO_ZHUANGTAIJI_CORE 指定其 core 目录，"
                  "或用 ZHUANGTAIJI_ROOT 指定 zhuangtaiji 仓根。")

    # ---------- 行为树构造 ----------
    def _build(self) -> "BehaviorTree":
        # 条件读黑板
        def hp_crit(ctx):
            return self.blackboard.get("hp_pct", 100) < self.HP_FLEE_PCT

        def hp_low_and_enemy_tough(ctx):
            return (self.blackboard.get("hp_pct", 100) < self.HP_DEFEND_PCT
                    and self.blackboard.get("enemy_hp_pct", 100) > self.ENEMY_HEAVY_PCT)

        def can_heavy(ctx):
            return (self.blackboard.get("mp", 0) >= self.MP_HEAVY
                    and self.blackboard.get("enemy_hp_pct", 100) > self.ENEMY_HEAVY_PCT)

        # 动作：驱动 GUI 战斗方法，并记录本次选择
        def do_flee(ctx):
            self._last_action = "flee"
            getattr(self.gui, self._action_method)("flee")
            return Status.SUCCESS

        def do_defend(ctx):
            self._last_action = "defend"
            getattr(self.gui, self._action_method)("defend")
            return Status.SUCCESS

        def do_heavy(ctx):
            self._last_action = "heavy"
            getattr(self.gui, self._action_method)("heavy")
            return Status.SUCCESS

        def do_attack(ctx):
            self._last_action = "attack"
            getattr(self.gui, self._action_method)("attack")
            return Status.SUCCESS

        root = Selector("combat_root", children=[
            Sequence("保命逃跑", [
                Condition("血量<15%", hp_crit),
                Action("逃跑", do_flee),
            ]),
            Sequence("低血防御", [
                Condition("低血且敌强", hp_low_and_enemy_tough),
                Action("防御", do_defend),
            ]),
            Sequence("蓝量重击", [
                Condition("可重击", can_heavy),
                Action("重击", do_heavy),
            ]),
            Action("普攻", do_attack),
        ])
        return BehaviorTree(root, self.blackboard)

    # ---------- 对外接口 ----------
    def tick_combat(self, gui, action_method: str = "combat_action") -> str:
        """推进一步战斗决策，返回本次选择的动作名。"""
        if not self.enabled:
            gui.combat_action("attack") if action_method == "combat_action" \
                else gui.custom_combat_action("attack")
            return "attack"

        self.gui = gui
        self._action_method = action_method
        self._last_action = None

        p = gui.player
        e = gui.current_enemy
        hp_pct = (p.hp / p.max_hp * 100) if p and p.max_hp else 100
        mp = p.mp if p else 0
        enemy_hp_pct = (e.hp / e.max_hp * 100) if e and e.max_hp else 100
        self.blackboard.update({
            "hp_pct": hp_pct,
            "mp": mp,
            "enemy_hp_pct": enemy_hp_pct,
        })

        try:
            self.tree.tick()
        except Exception:
            # 引擎异常也不卡死挂机，退回普攻
            getattr(gui, action_method)("attack")
            return "attack"
        return self._last_action or "attack"
