# -*- coding: utf-8 -*-
"""systems.jobs — DF 式挖掘/建造作业系统（M3，T-M3-09）。

提供：
  - JobConfig: 作业系统配置（挖掘/建造耗时、自增 id 起点）。
  - Job: 单个作业（挖掘/建造），含 id/类型/坐标/目标方块/进度/状态。
  - JobSystem: 玩家指派（assign_dig/assign_build）→ 队列 → 逐 tick 推进 →
    达 duration 改世界方块 + emit JOB_DONE（可取消）。

设计基线（architecture_m3.md §2.4 / T-M3-09 / §7.7）：
  - 作业是「指派 → 完成」范式（类似《矮人要塞》），由系统改世界，玩家不直接搬运。
  - 完成时调用 world_sim.mark_dirty_around（若已注入）使模拟重算该区域。
  - 发射 JOB_CREATED / JOB_DONE / JOB_CANCELLED 事件（接 EventBus）。

本模块零 pygame 依赖，headless 可断言。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from mcclone.core.block_registry import AIR
from mcclone.core.event_bus import EventBus, EventTypes


@dataclass
class JobConfig:
    """作业系统配置。"""

    dig_duration: float = 1.0          # 单个挖掘作业耗时（秒）
    build_duration: float = 1.0        # 单个建造作业耗时（秒）
    next_id: int = 1                   # 下一个作业自增 id 起点


@dataclass
class Job:
    """单个作业（挖掘或建造）。"""

    id: int
    type: str                          # 'dig' | 'build'
    x: int
    y: int
    z: int
    target_block_id: int               # dig=AIR；build=目标方块 id
    duration: float                    # 完成所需总时长（秒）
    progress: float = 0.0              # 已推进进度（秒）
    status: str = "queued"             # 'queued' | 'active' | 'cancelled' | 'done'

    def progress_ratio(self) -> float:
        """进度比例 [0, 1]。"""
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.progress / self.duration))


class JobSystem:
    """DF 式作业系统：指派 → 队列 → 逐 tick 推进 → 完成改世界。"""

    def __init__(self, world, registry, bus: "EventBus | None" = None,
                 cfg: "JobConfig | None" = None) -> None:
        self.world = world
        self.registry = registry
        self.bus = bus
        self.cfg = cfg if cfg is not None else JobConfig()
        # 活动作业（含 queued/active，完成或取消后移除）。
        self._jobs: Dict[int, Job] = {}
        # 完成回调（可选）。
        self.on_job_done: Optional[Callable[[Job], None]] = None
        # 世界模拟钩子（完成时 mark_dirty_around）；由 attach_sim 注入。
        self._world_sim = None

    # ── 模拟钩子 ──
    def attach_sim(self, world_sim) -> None:
        """注入 WorldSim，使作业完成时触发温度/流体重算。"""
        self._world_sim = world_sim

    # ── 指派 ──
    def assign_dig(self, x: int, y: int, z: int) -> int:
        """指派一个挖掘作业（目标格最终变 AIR）。返回作业 id。"""
        job = Job(id=self.cfg.next_id, type="dig", x=x, y=y, z=z,
                  target_block_id=AIR, duration=self.cfg.dig_duration)
        self.cfg.next_id += 1
        self._jobs[job.id] = job
        self._emit(EventTypes.JOB_CREATED, job)
        return job.id

    def assign_build(self, x: int, y: int, z: int, block_id: int) -> int:
        """指派一个建造作业（目标格最终变 block_id）。返回作业 id。"""
        job = Job(id=self.cfg.next_id, type="build", x=x, y=y, z=z,
                  target_block_id=block_id, duration=self.cfg.build_duration)
        self.cfg.next_id += 1
        self._jobs[job.id] = job
        self._emit(EventTypes.JOB_CREATED, job)
        return job.id

    # ── 取消 ──
    def cancel(self, job_id: int) -> bool:
        """取消一个作业（置 cancelled 并从队列移除）。返回是否成功取消。"""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.status = "cancelled"
        del self._jobs[job_id]
        self._emit(EventTypes.JOB_CANCELLED, job)
        return True

    def cancel_under(self, x: int, y: int, z: int) -> bool:
        """取消光标下的作业（同坐标者）。返回是否取消。"""
        for job in self._jobs.values():
            if job.x == x and job.y == y and job.z == z:
                return self.cancel(job.id)
        return False

    # ── 推进 ──
    def tick(self, dt: float) -> None:
        """逐 tick 推进所有活动作业；达 duration 则改世界 + emit JOB_DONE。"""
        done: List[int] = []
        for job in self._jobs.values():
            if job.status == "cancelled":
                continue
            job.status = "active"
            job.progress += dt
            if job.progress >= job.duration:
                self._complete(job)
                done.append(job.id)
        for jid in done:
            self._jobs.pop(jid, None)

    def _complete(self, job: Job) -> None:
        """完成一个作业：改世界 → 标脏 → 回调 → emit JOB_DONE。"""
        if job.type == "dig":
            self.world.set(job.x, job.y, job.z, AIR)
        else:
            self.world.set(job.x, job.y, job.z, job.target_block_id)
        # 触发模拟重算（若已注入 WorldSim）。
        if self._world_sim is not None:
            self._world_sim.mark_dirty_around(job.x, job.y, job.z)
        if self.on_job_done is not None:
            self.on_job_done(job)
        self._emit(EventTypes.JOB_DONE, job)
        job.status = "done"

    # ── 查询 ──
    def jobs(self) -> List[Job]:
        """返回活动作业列表（供 HUD 展示）。"""
        return list(self._jobs.values())

    # ── 事件 ──
    def _emit(self, etype: str, job: Job) -> None:
        """向事件总线发射作业事件（含 id/type/坐标/目标）。"""
        if self.bus is not None:
            self.bus.emit(etype, id=job.id, type=job.type,
                          x=job.x, y=job.y, z=job.z,
                          target=job.target_block_id)
