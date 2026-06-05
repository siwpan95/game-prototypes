"""
入口文件 — 罐头部游戏
架构：ECS（游戏逻辑）+ MVVM（UI 自动化）+ MVC（任务系统）+ 技能混合
内容：程序化怪物/词缀/装备/随机事件/Boss波/技能
"""

import tkinter as tk
from typing import List, Optional

# ECS
from ecs.entities import create_all_monsters, create_player
from ecs.systems import respawn_system
from ecs.world import World

# MVVM
from mvvm.model import GameModel
from mvvm.view import GameView
from mvvm.viewmodel import GameViewModel

# MVC（任务系统）
from mvc.controller_task import TaskController
from mvc.model_task import TaskModel
from mvc.view_task import TaskView

# 技能系统（混合架构）
from skills.skill_vm import SkillViewModel


class GameApp:
    """应用主类：组装所有模块，绑定跨层事件。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("文字传奇 · 罐头版  [MVP+ECS+MVVM]")
        self.root.geometry("680x720")

        # ── 1. ECS World ──────────────────────
        self.world = World()
        self.player_eid = create_player(self.world)
        self.monster_eids: List[int] = create_all_monsters(self.world)

        # ── 2. MVVM ────────────────────────
        self.model = GameModel(notify_fn=None)
        self.vm = GameViewModel(self.model)

        # ── 3. MVC 任务系统 ─────────────────
        self.task_model = TaskModel()
        self.task_model.initialize_default_tasks()
        self.task_controller = TaskController(self.task_model)
        self.task_controller.bind_game_model(self.model)

        # ── 4. 技能系统 ─────────────────────
        self.skill_vm = SkillViewModel(
            self.model.world, self.model.player_eid, notify_fn=None
        )
        # skill_vm 需要操作 model 的日志
        self.skill_log = self.model._log

        # ── 5. 组装 MVVM View ───────────────
        self.task_view = TaskView(
            self.root, self.task_model, self.task_controller
        )
        self.game_view = GameView(
            self.root, self.vm, task_view=self.task_view,
            on_skill_use=self._use_skill,
        )

        # ── 6. 绑定跨层事件 ──────────────────
        self._setup_event_hooks()

        # ── 7. 启动 tick 定时器 ──────────────
        self._start_tick()

    # ── 技能使用 ─────────────────────────────

    def _use_skill(self, skill_id: str, target_idx: int) -> None:
        """使用技能（View 回调）"""
        all_ids = (self.model.monster_eids +
                   ([self.model.boss_eid] if self.model.boss_eid else []))
        if target_idx < 0 or target_idx >= len(all_ids):
            return
        target_eid = all_ids[target_idx]
        self.skill_vm.cmd_use_skill(skill_id, target_eid, self.model._log)
        self.vm._notifier.emit("player_state")
        self.vm._notifier.emit("monster_states")
        self.vm._notifier.emit("skills")

    # ── 事件钩子 ─────────────────────────────

    def _setup_event_hooks(self) -> None:
        orig_log = self.model._log

        def _hooked_log(text: str) -> None:
            orig_log(text)
            self._dispatch_task_events(text)

        self.model._log = _hooked_log  # type: ignore[assignment]

    def _dispatch_task_events(self, log_text: str) -> None:
        if "死亡，获得" in log_text or "被击杀" in log_text:
            try:
                if "死亡，获得" in log_text:
                    part = log_text.split("🎉 ")[1].split(" 死亡")[0]
                else:
                    part = log_text.split("🎉 ")[1].split(" 被")[0]
                self.task_controller.on_monster_killed(part)
            except IndexError:
                pass
        if "升到 Lv." in log_text:
            try:
                part = log_text.split("升到 Lv.")[1].split()[0]
                lv = int(part)
                self.task_controller.on_level_up(lv)
                # 技能解锁：等级达标时自动解锁
                self.skill_vm.check_level_unlocks(lv, self.model._log)
            except (IndexError, ValueError):
                pass
        # Boss 被击杀 → 概率掉落技能书
        if "Boss 被击杀" in log_text:
            import random
            if random.random() < 0.35:
                self.skill_vm.random_unlock(self.model._log)
        # 技能击杀事件
        if "火焰斩击杀" in log_text:
            self.task_controller.on_skill_kill("flame_slash")
        if "冰锥" in log_text and "击杀" in log_text:
            self.task_controller.on_skill_kill("ice_shard")
        if "剧毒" in log_text and "击杀" in log_text:
            self.task_controller.on_skill_kill("poison_strike")

    # ── 定时器 ──────────────────────────────

    def _start_tick(self) -> None:
        self.skill_vm.tick_cooldowns(dt=1)
        # 通知技能 UI 刷新
        self.vm._notifier.emit("skills")
        self.root.after(1000, self._start_tick)


# ── 启动 ──────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    app = GameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
