import tkinter as tk
from tkinter import font
from typing import Callable, List, Optional

from common.fonts import cn_font
from .model_task import Task, TaskModel
from .controller_task import TaskController


class TaskView:
    """
    MVC — View 层（任务列表 UI）
    以 Tkinter Frame 形式嵌入主界面。
    展示任务列表 + 进度 + 领取奖励按钮。
    """

    def __init__(self, parent: tk.Widget, model: TaskModel,
                 controller: TaskController) -> None:
        self.model: TaskModel = model
        self.controller: TaskController = controller

        # 主 Frame
        self.frame = tk.LabelFrame(parent, text="📋 任务列表",
                                  font=cn_font(11))
        self.frame.pack(fill="x", padx=10, pady=5)

        self.task_rows: dict[str, dict] = {}  # task_id -> {widgets}

        # 初始渲染
        self.render()

        # 注册 Model 变更回调（任务进度/完成/领取时刷新）
        self.model.set_change_callback(self._on_task_changed)

    # ── UI 渲染 ──────────────────────────────────

    def render(self) -> None:
        """重新渲染整个任务列表"""
        # 清空前一次
        for child in self.frame.winfo_children():
            child.destroy()
        self.task_rows.clear()

        tasks: List[Task] = self.model.get_all_tasks()
        if not tasks:
            lbl = tk.Label(self.frame, text="(暂无任务)", font=cn_font(10))
            lbl.pack(anchor="w", padx=5, pady=2)
            return

        for task in tasks:
            row = tk.Frame(self.frame)
            row.pack(anchor="w", fill="x", padx=5, pady=2)

            # 任务名 + 进度
            text = f"{task.name}  {task.progress_text()}"
            if task.done and "✅" not in task.name:
                text = text + " ✅ 可领取"
            lbl = tk.Label(row, text=text, font=cn_font(10),
                           anchor="w", justify="left")
            lbl.pack(side="left", fill="x", expand=True)

            # 领取按钮（仅完成且未领取时显示）
            if task.done and not task.claimed and task.reward_exp > 0:
                btn = tk.Button(
                    row,
                    text=f"领取 {task.reward_exp} 经验池",
                    font=cn_font(9),
                    command=lambda tid=task.id: self._on_claim(tid),
                )
                btn.pack(side="right", padx=5)
                self.task_rows[task.id] = {"label": lbl, "claim_btn": btn}
            else:
                self.task_rows[task.id] = {"label": lbl}

    # ── 事件处理 ──────────────────────────────────

    def _on_claim(self, task_id: str) -> None:
        """点击领取奖励"""
        reward = self.controller.claim_reward(task_id)
        if reward > 0:
            # 奖励经验池 → 写入 GameModel（通过 controller 间接操作）
            self._add_reward_to_pool(reward)
            self.render()  # 刷新 UI

    def _add_reward_to_pool(self, amount: int) -> None:
        """
        将奖励加入经验池。
        通过 controller.game_model 操作 ECS World。
        """
        gm = self.controller.game_model
        if gm is None:
            return
        from ecs.components import ExpComponent
        exp_c = gm.world.get_component(gm.player_eid, ExpComponent)
        if exp_c:
            exp_c.exp_pool += amount

    # ── Model 回调 ──────────────────────────────

    def _on_task_changed(self, task_id: str) -> None:
        """任务数据变化，刷新 UI"""
        self.render()
