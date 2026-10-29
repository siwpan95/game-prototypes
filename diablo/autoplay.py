# -*- coding: utf-8 -*-
"""
托管挂机（Idle / Auto-Play）控制器
==================================

由状态机驱动：根据 ``gui.fsm.current_state`` 选择对应自动动作，
通过 tkinter 的 ``after()`` 循环不断步进，实现"放置挂机化"——
自动开局、自动探索、自动进战、自动攻击、自动拾取奖励、自动回城，循环往复。

每个状态对应一个策略方法（``_at_<state>``），返回"下一步的延时(ms)"。
状态机只负责"此刻在哪 / 能去哪"，本控制器负责"到了该状态要干什么"。

战斗决策已交给 ``idle_brain.IdleBrain``（基于 zhuangtaiji 行为树）：
残血逃跑 / 低血防御 / 有蓝重击 / 否则普攻，显著减少无谓暴毙、提升挂机收益。

**节奏优化：** 挂机开战即入、战斗决策 150ms、状态切换 80-100ms，
远快于手动游玩；GUI 侧也会感知 ``auto_play`` 跳过 dungeon 2.5s 动画。
"""
import random
from typing import Callable, Dict, Optional

from data import REGIONS
from storage import load_game
from idle_brain import IdleBrain


class AutoPlayer:
    """托管挂机控制器。

    速度参数（可通过 settings.json 的 ``idle_speed`` 调整：1=极速 3=正常）：
    - FAST_TICK:    状态间切换延时（主城→探索→进战 等）
    - COMBAT_TICK:  战斗每轮决策后延时
    - VICTORY_TICK: 胜利/死亡结算后延时
    """

    # 默认速度值（speed=2 折中）
    FAST_TICK = 80        # 状态切换（ms）
    COMBAT_TICK = 150     # 战斗决策间隔（ms）
    VICTORY_TICK = 100    # 结算后延时（ms）

    # 速度倍率表：speed=1 极速, speed=2 标准, speed=3 慢速（观察用）
    SPEED_SCALE = {1: 0.4, 2: 1.0, 3: 2.5}

    # 低于该等级不挑战 Boss 区（Hell's Throne），避免送死浪费时间
    BOSS_REGION = "Hell's Throne"
    BOSS_REGION_MIN_LEVEL = 15

    def __init__(self, gui):
        self.gui = gui
        self.running = False
        self._timer = None
        self.brain = IdleBrain()

        # 状态 -> 策略；覆盖 GAME_FSM_CONFIG 中的所有状态
        self.policy: Dict[str, Callable[[], int]] = {
            "preload": self._at_preload,
            "main_menu": self._at_main_menu,
            "hub": self._at_hub,
            "explore": self._at_explore,
            "dungeon": self._at_dungeon,
            "combat": self._at_combat,
            "victory": self._at_victory,
            "defeat": self._at_transient,
            "status": self._at_status,
            "workshop": self._at_workshop,
            "custom_combat": self._at_custom_combat,
            "custom_victory": self._at_victory,
            "custom_defeat": self._at_transient,
            "settings": self._at_settings,
        }

    def _speed_scale(self) -> float:
        """读取 settings 中的 idle_speed 并映射到倍率。"""
        speed = self.gui.settings.get("idle_speed", 2)
        return self.SPEED_SCALE.get(speed, 1.0)

    def _ft(self) -> int:
        """当前速度下的状态切换延时。"""
        return max(30, int(self.FAST_TICK * self._speed_scale()))

    def _ct(self) -> int:
        """当前速度下的战斗决策延时。"""
        return max(50, int(self.COMBAT_TICK * self._speed_scale()))

    def _vt(self) -> int:
        """当前速度下的结算延时。"""
        return max(40, int(self.VICTORY_TICK * self._speed_scale()))

    # ---------- 控制 ----------
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.gui.auto_play = True
        self._tick()

    def stop(self) -> None:
        self.running = False
        self.gui.auto_play = False
        if self._timer is not None:
            try:
                self.gui.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def _tick(self) -> None:
        if not self.running:
            return
        state = self.gui.fsm.current_state
        action = self.policy.get(state, self._at_transient)
        try:
            delay = action()
        except Exception:
            delay = 200
        if self.running:
            self._timer = self.gui.root.after(max(30, int(delay or 150)), self._tick)

    # ---------- 各状态策略（返回下一步延时 ms）----------
    def _at_preload(self) -> int:
        return self._ft()

    def _at_main_menu(self) -> int:
        if self.gui.player is not None and self.gui.player.is_alive():
            return self._ft()
        loaded = load_game()
        if loaded is not None:
            self.gui.player = loaded
            self.gui.fsm.goto("continue_game")
        else:
            self.gui.start_game("挂机者")
        return self._ct()

    def _at_hub(self) -> int:
        self.gui.maybe_autosave()
        self.gui.fsm.goto("explore")
        return self._ft()

    def _at_explore(self) -> int:
        regions = list(REGIONS.keys())
        if self.gui.player and self.gui.player.level < self.BOSS_REGION_MIN_LEVEL:
            regions = [r for r in regions if r != self.BOSS_REGION]
        region = random.choice(regions) if regions else self.BOSS_REGION
        self.gui.start_explore(region)
        return self._ft()

    def _at_dungeon(self) -> int:
        # dungeon 的 show_dungeon_view 检测到 auto_play 会秒进战斗，
        # 本 tick 只需触发转移；延时很短以防 race condition
        self.gui.fsm.goto("enter_battle")
        return self._ft()

    def _at_combat(self) -> int:
        action = self.brain.tick_combat(self.gui, "combat_action")
        if action and self.gui.auto_play:
            self.gui.add_log(f"[挂机AI] {action}")
        return self._ct()

    def _at_victory(self) -> int:
        # 胜利结算由 combat_victory 的 after() 链驱动跳转，这里空等
        return self._vt()

    def _at_transient(self) -> int:
        # 终态转移（defeat/custom_defeat）已由对应方法自行跳转
        return self._ft()

    def _at_status(self) -> int:
        self.gui.fsm.goto("return_hub")
        return self._ft()

    def _at_workshop(self) -> int:
        self.gui.fsm.goto("return_hub")
        return self._ft()

    def _at_custom_combat(self) -> int:
        action = self.brain.tick_combat(self.gui, "custom_combat_action")
        if action and self.gui.auto_play:
            self.gui.add_log(f"[挂机AI] {action}")
        return self._ct()

    def _at_settings(self) -> int:
        if self.gui.player:
            self.gui.fsm.goto("back_to_hub")
        else:
            self.gui.fsm.goto("back_to_menu")
        return self._ft()
