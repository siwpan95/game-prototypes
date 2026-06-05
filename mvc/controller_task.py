"""
MVC — Task Controller 层
接收游戏事件（击杀/升级/休息），更新任务进度。
"""


class TaskController:
    """
    控制器：接收来自游戏 Model 的事件，驱动 TaskModel 更新进度。
    - on_monster_killed(monster_name)
    - on_level_up(new_level)
    - on_rest()
    """

    def __init__(self, model) -> None:
        """
        model: TaskModel 实例
        game_model: GameModel 实例（用于领取奖励后操作 ECS 数据）
        """
        self.model = model
        self.game_model = None  # 延迟注入（避免循环依赖）

    def bind_game_model(self, game_model) -> None:
        """注入 GameModel 引用（用于领取奖励时操作 ECS World）"""
        self.game_model = game_model

    # ── 事件处理 ──────────────────────────────

    def on_monster_killed(self, monster_name: str) -> None:
        """怪物被击杀时调用"""
        for task in self.model.get_all_tasks():
            if task.done:
                continue
            if task.event_type == "kill":
                if task.monster_name == "*" or task.monster_name == monster_name:
                    self.model.update_progress(task.id, delta=1)

    def on_skill_kill(self, skill_id: str) -> None:
        """使用技能击杀怪物时调用"""
        for task in self.model.get_all_tasks():
            if task.done:
                continue
            if task.event_type == "skill_kill" and task.skill_id == skill_id:
                self.model.update_progress(task.id, delta=1)

    def on_level_up(self, new_level: int) -> None:
        """玩家升级时调用"""
        for task in self.model.get_all_tasks():
            if task.done:
                continue
            if task.event_type == "level_up":
                # target_value = 目标等级
                if new_level >= task.target_value:
                    self.model.update_progress(task.id,
                                              delta=task.target_value)

    def on_rest(self) -> None:
        """休息时调用（示例事件）"""
        for task in self.model.get_all_tasks():
            if task.done:
                continue
            if task.event_type == "rest":
                self.model.update_progress(task.id, delta=1)

    # ── 奖励领取 ──────────────────────────────

    def claim_reward(self, task_id: str) -> int:
        """
        领取任务奖励，返回奖励经验池数量。
        领取完成后自动生成随机新任务替换，保持任务列表始终满额。
        """
        reward = self.model.claim_reward(task_id)
        if reward > 0 and self.game_model:
            player_state = self.game_model.get_player_state()
            player_level = player_state.get("level", 1)
            new_task = self.model.generate_random_task(int(player_level))
            self.model.replace_task(task_id, new_task)
        return reward
