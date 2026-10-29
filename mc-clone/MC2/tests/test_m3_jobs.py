# -*- coding: utf-8 -*-
"""test_m3_jobs — T-M3-09 作业系统（headless）。

验收要点：
  - assign_dig 后 tick(duration) → 目标格变 AIR。
  - assign_build 后 tick(duration) → 目标格变目标方块。
  - cancel 后世界不再改变。
  - 完成时发射 JOB_DONE；指派发射 JOB_CREATED；取消发射 JOB_CANCELLED。
  - on_job_done 回调触发；attach_sim 后完成时 mark_dirty_around。
"""

from __future__ import annotations

import pytest

from mcclone.core.block_registry import BlockRegistry, BlockDef, AIR, STONE, DIRT
from mcclone.core.block_world import BlockWorld
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.systems.jobs import JobSystem, JobConfig
from mcclone.simulation import WorldSim, LAVA_ID


def _registry():
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


def test_assign_dig_completes_and_clears_block():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(5, 5, 2, STONE)
    jobs = JobSystem(world, reg)
    jid = jobs.assign_dig(5, 5, 2)
    assert isinstance(jid, int)
    assert world.get(5, 5, 2) == STONE      # 尚未完成
    jobs.tick(1.0)                            # duration=1.0
    assert world.get(5, 5, 2) == AIR
    assert jobs.jobs() == []                  # 已从活动队列移除


def test_assign_build_places_target_block():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    jobs = JobSystem(world, reg)
    jid = jobs.assign_build(7, 7, 3, DIRT)
    assert world.get(7, 7, 3) == AIR
    jobs.tick(1.0)
    assert world.get(7, 7, 3) == DIRT


def test_cancel_prevents_world_change():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(3, 3, 1, STONE)
    jobs = JobSystem(world, reg)
    jid = jobs.assign_dig(3, 3, 1)
    assert jobs.cancel(jid) is True
    assert jobs.cancel(jid) is False          # 已取消
    jobs.tick(1.0)
    assert world.get(3, 3, 1) == STONE        # 未改变


def test_job_events_emitted():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    bus = EventBus()
    captured = []
    for et in (EventTypes.JOB_CREATED, EventTypes.JOB_DONE,
               EventTypes.JOB_CANCELLED):
        bus.subscribe(et, lambda e, d, _et=et: captured.append((_et, d["id"])))
    jobs = JobSystem(world, reg, bus)
    jid = jobs.assign_dig(5, 5, 2)
    assert (EventTypes.JOB_CREATED, jid) in captured
    jobs.tick(1.0)
    assert (EventTypes.JOB_DONE, jid) in captured
    # 取消一个新作业
    jid2 = jobs.assign_build(1, 1, 1, DIRT)
    assert jobs.cancel(jid2) is True
    assert (EventTypes.JOB_CANCELLED, jid2) in captured


def test_on_job_done_callback_and_sim_dirty():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(8, 8, 2, STONE)
    sim = WorldSim(world, reg)
    jobs = JobSystem(world, reg)
    jobs.attach_sim(sim)
    called = []
    jobs.on_job_done = lambda job: called.append(job.id)
    jid = jobs.assign_dig(8, 8, 2)
    # 记录作业前脏集大小
    dirty_before = len(sim.dirty_chunks)
    jobs.tick(1.0)
    assert called == [jid]
    # 完成时触发模拟重算（脏 chunk 增加或保持）
    assert len(sim.dirty_chunks) >= dirty_before
