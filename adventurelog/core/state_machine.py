# -*- coding: utf-8 -*-
"""
通用状态机 — 纯逻辑，支持多实例
从 zhuangtaiji 整合而来，适配探险日志游戏流程
"""

import time
from typing import Optional, Callable


class GenericStateMachine:
    """通用状态机引擎。
    
    驱动游戏自动化流程的核心组件：每个游戏阶段对应一个状态机实例。
    事件驱动状态转移，支持 guard 条件、外部回调监听。
    """

    def __init__(self, machine_name: str, full_config: dict,
                 on_action: Optional[Callable] = None):
        """
        Args:
            machine_name: 状态机配置名称（对应 auto_config.json 中的 key）
            full_config:  完整配置字典
            on_action:    可选回调 (action_type, state_id, detail) -> None
                          用于外部监听 enter/exit/transition 等动作
        """
        config = full_config.get("state_machines", {}).get(machine_name)
        if not config:
            raise ValueError(f"找不到状态机配置: {machine_name}")

        self.name = machine_name
        self.states: dict = config["states"]
        self.current_state_id: str = config["initial"]
        self.pipeline_index: int = config.get("pipeline_index", 0)
        self.on_action: Optional[Callable] = on_action

        # 转移历史: [{"from":str, "event":str, "to":str, "time":float}, ...]
        self.history: list = []

        # 进入初始状态时触发 on_enter
        self._invoke_action("enter", self.current_state_id)

    # ==================== 事件驱动 ====================
    def trigger(self, event_name: str, context: dict = None) -> tuple:
        """触发事件，执行状态转移。
        
        Returns:
            (new_state_id, content) 或 (None, 拒绝原因)
        """
        context = context or {}
        current = self.states.get(self.current_state_id, {})
        transitions = current.get("transitions", {})

        # 查找匹配的转移
        target = transitions.get(event_name)
        if target is None:
            return None, f"状态 [{self.current_state_id}] 不支持事件 [{event_name}]"

        # 解析转移配置
        if isinstance(target, str):
            target_state_id = target
            guard_name = None
        elif isinstance(target, dict):
            target_state_id = target.get("target")
            guard_name = target.get("guard")
        else:
            return None, "转移配置格式错误"

        # 执行 guard 条件检查
        if guard_name:
            guard_fn = context.get("guards", {}).get(guard_name)
            if callable(guard_fn) and not guard_fn(context):
                return None, f"Guard [{guard_name}] 条件不满足"

        # 离开旧状态
        self._invoke_action("exit", self.current_state_id)
        old_state = self.current_state_id

        # 转移
        self.current_state_id = target_state_id

        # 记录历史
        self.history.append({
            "from": old_state,
            "event": event_name,
            "to": target_state_id,
            "time": time.time()
        })

        # 进入新状态
        self._invoke_action("enter", self.current_state_id)
        self._invoke_action("transition", self.current_state_id,
                            extra={"from": old_state, "event": event_name})

        content = self.states[self.current_state_id].get("content", "")
        return self.current_state_id, content

    def can_trigger(self, event_name: str) -> bool:
        """检查当前状态是否支持某个事件"""
        current = self.states.get(self.current_state_id, {})
        return event_name in current.get("transitions", {})

    def reset(self):
        """重置到初始状态"""
        first_state = list(self.states.keys())[0]
        self._invoke_action("exit", self.current_state_id)
        self.current_state_id = first_state
        self.history.clear()
        self._invoke_action("enter", self.current_state_id)

    # ==================== 属性 ====================
    @property
    def current_content(self) -> str:
        return self.states.get(self.current_state_id, {}).get("content", "")

    @property
    def available_events(self) -> list:
        current = self.states.get(self.current_state_id, {})
        return list(current.get("transitions", {}).keys())

    @property
    def is_finished(self) -> bool:
        """当前状态是否无可用事件（终态）"""
        return len(self.available_events) == 0

    def get_state_info(self) -> dict:
        state = self.states.get(self.current_state_id, {})
        return {
            "id": self.current_state_id,
            "content": state.get("content", ""),
            "on_enter": state.get("on_enter", ""),
            "on_exit": state.get("on_exit", ""),
            "available_events": self.available_events,
        }

    def get_history(self, limit: int = 20) -> list:
        return self.history[-limit:]

    # ==================== 内部方法 ====================
    def _invoke_action(self, action_type: str, state_id: str, extra: dict = None):
        """调用 on_enter / on_exit / transition 描述，并通知外部回调"""
        state = self.states.get(state_id, {})
        description = state.get(f"on_{action_type}", "")

        if callable(self.on_action):
            detail = {"description": description}
            if extra:
                detail.update(extra)
            self.on_action(action_type, state_id, detail)
