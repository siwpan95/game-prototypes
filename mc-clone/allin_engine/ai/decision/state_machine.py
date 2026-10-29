# -*- coding: utf-8 -*-
"""
通用状态机（GenericStateMachine）
================================

从 zhuangtaiji 项目移植并适配 allin_engine。

状态机是解决「状态爆炸」的核心范式：用明确的「状态 + 事件转移」替代
混乱的条件分支。本模块提供：
  - GenericStateMachine : 平面有限状态机（FSM）
  - HierarchicalStateMachine : 层次状态机（嵌套/历史/内部转移），见本包
  - create_state_machine : 工厂（按配置自动选择 FSM / HSM）
  - register_guard      : 声明式守卫注册表（config 只能写字符串名）

配合 allin_engine 的 ECS，可用 StateMachineComponent / BrainComponent 把状态机
挂到实体上（见 brain.py）。
"""
from __future__ import annotations

import time

from .hierarchical_state_machine import HierarchicalStateMachine


# ==========================================
# 守卫（Guard）注册表
# ==========================================
GUARD_REGISTRY: dict = {}


def register_guard(name: str, fn) -> None:
    """注册一个命名守卫函数，供 config 中的 guard 字段引用。"""
    GUARD_REGISTRY[name] = fn


# ==========================================
# 通用状态机（纯逻辑，支持多实例）
# ==========================================
class GenericStateMachine:
    def __init__(self, machine_name, full_config, on_action=None, guards=None):
        config = full_config["state_machines"].get(machine_name)
        if not config:
            raise ValueError(f"找不到状态机配置: {machine_name}")

        self.name = machine_name
        self.states = config["states"]
        self.current_state_id = config["initial"]
        self.on_action = on_action

        # 守卫函数表：实例级 guards 优先，其次全局 GUARD_REGISTRY
        self.guards = dict(GUARD_REGISTRY)
        if isinstance(guards, dict):
            self.guards.update(guards)

        # 转移历史
        self.history: list[dict] = []

        # 进入初始状态时触发 on_enter
        self._invoke_action("enter", self.current_state_id)

    # ---------- 事件驱动 ----------
    def trigger(self, event_name, context=None):
        context = context or {}
        current = self.states.get(self.current_state_id, {})
        transitions = current.get("transitions", {})

        target = transitions.get(event_name)
        if target is None:
            return None, f"状态 [{self.current_state_id}] 不支持事件 [{event_name}]"

        if isinstance(target, str):
            target_state_id = target
            guard_name = None
        elif isinstance(target, dict):
            target_state_id = target.get("target")
            guard_name = target.get("guard")
        else:
            return None, "转移配置格式错误"

        # 内部转移：target 以 "#" 开头表示「原地执行动作但不离开状态」
        if isinstance(target_state_id, str) and target_state_id.startswith("#"):
            real = target_state_id[1:]
            self._invoke_action("internal", self.current_state_id,
                                extra={"event": event_name, "to": real})
            content = self.states[self.current_state_id].get("content", "无内容")
            return self.current_state_id, content

        # 执行 guard 条件检查
        if guard_name:
            guard_fn = self.guards.get(guard_name)
            if callable(guard_fn) and not guard_fn(context):
                return None, f"Guard [{guard_name}] 条件不满足"

        self._invoke_action("exit", self.current_state_id)
        old_state = self.current_state_id

        self.current_state_id = target_state_id

        self.history.append({
            "from": old_state,
            "event": event_name,
            "to": target_state_id,
            "time": time.time(),
        })

        self._invoke_action("enter", self.current_state_id)
        self._invoke_action("transition", self.current_state_id,
                            extra={"from": old_state, "event": event_name})

        content = self.states[self.current_state_id].get("content", "无内容")
        return self.current_state_id, content

    def can_trigger(self, event_name):
        current = self.states.get(self.current_state_id, {})
        transitions = current.get("transitions", {})
        return event_name in transitions

    # ---------- 属性 ----------
    @property
    def current_content(self):
        return self.states[self.current_state_id].get("content", "")

    @property
    def available_events(self):
        current = self.states.get(self.current_state_id, {})
        return list(current.get("transitions", {}).keys())

    def get_state_info(self):
        state = self.states.get(self.current_state_id, {})
        return {
            "id": self.current_state_id,
            "content": state.get("content", ""),
            "on_enter": state.get("on_enter", ""),
            "on_exit": state.get("on_exit", ""),
            "available_events": self.available_events,
        }

    def get_history(self, limit=20):
        return self.history[-limit:]

    # ---------- 内部 ----------
    def _invoke_action(self, action_type, state_id, extra=None):
        state = self.states.get(state_id, {})
        description = state.get(f"on_{action_type}", "")
        if callable(self.on_action):
            detail = {"description": description}
            if extra:
                detail.update(extra)
            self.on_action(action_type, state_id, detail)


# ==========================================
# 工厂：自动选择 平面 / 层次 状态机
# ==========================================
def create_state_machine(machine_name, full_config, on_action=None, guards=None):
    """根据配置自动构造状态机实例。

    * 若某状态包含 "substates" 或配置 type == "hierarchical"，返回
      HierarchicalStateMachine；
    * 否则返回通用 GenericStateMachine。
    """
    config = full_config["state_machines"].get(machine_name, {})
    is_hier = config.get("type") == "hierarchical" or any(
        "substates" in s for s in config.get("states", {}).values()
    )
    if is_hier:
        return HierarchicalStateMachine(machine_name, full_config, on_action)
    return GenericStateMachine(machine_name, full_config, on_action, guards)
