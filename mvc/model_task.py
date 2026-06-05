"""
MVC — Task Model 层
任务数据定义 + TaskModel（任务列表管理）
"""


from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Task:
    """单个任务的数据"""
    id: str
    name: str
    desc: str
    target_value: int = 1        # 需要完成的数量（击杀/升级次数等）
    current_value: int = 0        # 当前进度
    done: bool = False
    reward_exp: int = 0           # 完成任务奖励经验池
    event_type: str = "kill"       # 触发事件类型：kill / level_up / rest / skill_kill
    monster_name: Optional[str] = None  # event_type=kill 时匹配怪物名
    skill_id: Optional[str] = None      # event_type=skill_kill 时匹配技能ID
    claimed: bool = False              # 是否已领取奖励

    def progress_text(self) -> str:
        return f"[{self.current_value}/{self.target_value}]"

    def is_complete(self) -> bool:
        return self.current_value >= self.target_value


MAX_ACTIVE_TASKS = 3  # 同时存在的最大活跃任务数


class TaskModel:
    """
    任务模型：管理所有任务的数据。
    不直接操作 UI，只管理数据和完成判定。
    最多同时存在 MAX_ACTIVE_TASKS 个活跃（未完成+可领取）任务。
    """
    def __init__(self) -> None:
        self.tasks: Dict[str, Task] = {}
        self._change_callback: Optional[Callable[[str], None]] = None

    def set_change_callback(self, cb: Callable[[str], None]) -> None:
        """当任务数据变化时调用 cb(task_id)"""
        self._change_callback = cb

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def get_active_tasks(self) -> List[Task]:
        """返回活跃任务（未完成 或 已完成未领取）"""
        return [t for t in self.tasks.values() if not t.claimed]

    def _trim_to_max(self) -> None:
        """清理多余任务：优先移除已领取的，再限制总数为 MAX_ACTIVE_TASKS"""
        # 先移除已领取的任务
        claimed_ids = [t.id for t in self.tasks.values() if t.claimed]
        for tid in claimed_ids:
            self.tasks.pop(tid, None)
        # 再限制总数
        active = self.get_active_tasks()
        if len(active) <= MAX_ACTIVE_TASKS:
            return
        # 按某种顺序裁剪（保留前面的）
        keep = set(t.id for t in active[:MAX_ACTIVE_TASKS])
        remove = [t.id for t in self.tasks.values() if t.id not in keep]
        for tid in remove:
            self.tasks.pop(tid, None)

    def update_progress(self, task_id: str, delta: int = 1) -> None:
        """增加任务进度，若完成则标记 done"""
        task = self.tasks.get(task_id)
        if task is None or task.done:
            return
        task.current_value += delta
        if task.is_complete():
            task.done = True
            if self._change_callback:
                self._change_callback(task_id)

    def claim_reward(self, task_id: str) -> int:
        """
        领取任务奖励，返回奖励经验池数量。
        只能领取一次（done=True 且未领取）。
        """
        task = self.tasks.get(task_id)
        if task is None or not task.done or task.claimed:
            return 0
        reward = task.reward_exp
        task.claimed = True
        task.name = task.name + " ✅"  # 标记已领取
        if self._change_callback:
            self._change_callback(task_id)
        return reward

    def replace_task(self, old_id: str, new_task: "Task") -> None:
        """替换一个已完成的任务为新任务"""
        self.tasks.pop(old_id, None)
        self.tasks[new_task.id] = new_task
        self._trim_to_max()
        if self._change_callback:
            self._change_callback(new_task.id)

    def initialize_default_tasks(self) -> None:
        """从 Excel 加载默认任务列表，若失败则用内置默认"""
        self.tasks.clear()
        try:
            from ecs.game_data import get_data
            data = get_data()
            task_list = data.get("tasks", [])
            if task_list:
                for row in task_list:
                    tid = row[0]
                    t = Task(
                        id=tid,
                        name=row[1],
                        desc=row[2],
                        target_value=int(row[3]),
                        reward_exp=int(row[4]),
                        event_type=row[5],
                        monster_name=row[6] if row[6] and row[5] == "kill" else (
                            "*" if row[5] == "kill" else None
                        ),
                        skill_id=row[7] if row[7] and row[5] == "skill_kill" else None,
                    )
                    self.add_task(t)
                # 限制同时存在的任务数量
                self._trim_to_max()
                return
        except Exception as e:
            print(f"[TaskModel] 从 Excel 加载任务失败：{e}，使用内置默认")

        # 兜底：内置默认任务
        defaults = [
            Task(id="t1", name="击杀任意怪物 x8", desc="击杀任意怪物",
                 target_value=8, reward_exp=20, event_type="kill",
                 monster_name="*"),
            Task(id="t2", name="升到 Lv.3", desc="角色等级达到 3",
                 target_value=3, reward_exp=25, event_type="level_up"),
            Task(id="t3", name="使用火焰斩击杀 x3", desc="使用火焰斩击杀怪物",
                 target_value=3, reward_exp=15, event_type="skill_kill",
                 skill_id="flame_slash"),
        ]
        for t in defaults:
            self.add_task(t)
        self._trim_to_max()

    def generate_random_task(self, player_level: int) -> Task:
        """根据玩家等级生成随机任务"""
        import random
        import uuid
        task_types = [
            ("kill", "*", random.randint(5, 10 + player_level)),
            ("level_up", str(player_level + 2), 1),
            ("skill_kill", random.choice(["flame_slash", "ice_shard", "poison_strike"]),
             random.randint(2, 4)),
        ]
        etype, target, target_v = random.choice(task_types)
        exp_reward = 10 + player_level * 5 + random.randint(0, 10)
        tid = "t" + uuid.uuid4().hex[:6]
        if etype == "kill":
            return Task(id=tid, name=f"击杀任意怪物 x{target_v}",
                        desc="击杀任意怪物", target_value=target_v,
                        reward_exp=exp_reward, event_type="kill",
                        monster_name="*")
        elif etype == "level_up":
            return Task(id=tid, name=f"升到 Lv.{target}",
                        desc=f"角色等级达到 {target}", target_value=int(target),
                        reward_exp=exp_reward, event_type="level_up")
        else:
            return Task(id=tid, name=f"使用技能击杀 x{target_v}",
                        desc=f"使用指定技能击杀怪物",
                        target_value=target_v, reward_exp=exp_reward,
                        event_type="skill_kill", skill_id=target)
