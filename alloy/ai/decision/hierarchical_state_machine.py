# -*- coding: utf-8 -*-
"""
层次状态机（Hierarchical State Machine, HSM）
============================================

从 zhuangtaiji 项目移植并适配 alloy。基于 UML 状态图（David Harel）。

在原有 GenericStateMachine 之上新增：
* 嵌套子状态 (substates)：父状态激活时内部有「当前子状态」。
* 历史伪状态 (history)：离开复合状态后再返回时回到上次子状态。
* 终态 (final)：子状态机到达 final 后向上抛出完成事件。
* 内部转移 (internal)：带前缀 "#" 的 target 表示「原地执行但不离开状态」。
* 事件冒泡 (bubbling)：当前子状态无法处理的事件逐级向祖先冒泡查找。

配置约定（config["state_machines"] 中可混用）：
    {
      "type": "hierarchical",
      "initial": "power",
      "states": {
        "power": {
          "initial": "off",
          "substates": {
            "off":  { "transitions": { "turn_on": "on" } },
            "on":   {
              "initial": "idle",
              "substates": {
                "idle": { "transitions": { "run": "working" } },
                "working": { "transitions": { "stop": "idle", "fault": "error" } },
                "error": { "transitions": { "reset": "#on" } }
              },
              "transitions": { "power_off": "off" }
            }
          },
          "transitions": { "kill": "off" }
        }
      }
    }
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional


class HierarchicalStateMachine:
    def __init__(self, machine_name: str, full_config: Dict[str, Any],
                 on_action: Optional[Callable] = None):
        config = full_config["state_machines"].get(machine_name)
        if not config:
            raise ValueError(f"找不到状态机配置: {machine_name}")

        self.name = machine_name
        self.config = config
        self.states = config["states"]
        self.on_action = on_action

        self.active_path: List[str] = [config["initial"]]
        self.history: List[Dict[str, Any]] = []
        self._history_cache: Dict[str, str] = {}
        self._deep_history_cache: Dict[str, List[str]] = {}

        self._enter_initial()

    # ---------- 路径工具 ----------
    def _child_node(self, parent: Dict[str, Any], seg: str) -> Dict[str, Any]:
        if seg in parent:
            return parent[seg]
        return parent["substates"][seg]

    def _node_config(self, path: List[str]) -> Dict[str, Any]:
        node = self.states
        for seg in path:
            node = self._child_node(node, seg)
        return node

    def _is_composite(self, path: List[str]) -> bool:
        return "substates" in self._node_config(path)

    @property
    def current_state_id(self) -> str:
        return "/".join(self.active_path)

    @property
    def current_leaf(self) -> str:
        return self.active_path[-1]

    # ---------- 进入 / 退出 ----------
    def _find_path(self, target, node_dict=None, prefix=None):
        if node_dict is None:
            node_dict = self.states
            prefix = []
        for name, node in node_dict.items():
            path = prefix + [name]
            if name == target:
                return path
            if "substates" in node:
                res = self._find_path(target, node["substates"], path)
                if res:
                    return res
        return None

    def _enter_node(self, path: List[str]):
        self._invoke("enter", path)
        if len(path) >= 2:
            parent = "/".join(path[:-1])
            self._history_cache[parent] = path[-1]

    def _enter_default_descendants(self, path: List[str]):
        node = self._node_config(path)
        if "substates" in node and node.get("initial"):
            child_path = path + [node["initial"]]
            self._enter_node(child_path)
            self.active_path = child_path
            self._enter_default_descendants(child_path)

    def _enter_specific_descendants(self, path: List[str], child: str):
        child_path = path + [child]
        self._enter_node(child_path)
        self.active_path = child_path
        self._enter_default_descendants(child_path)

    def _exit_path(self, path: List[str]):
        for depth in range(len(path) - 1, -1, -1):
            self._invoke("exit", path[: depth + 1])

    def _enter_initial(self):
        root = self.active_path[0]
        self._enter_node([root])
        self._enter_default_descendants([root])

    # ---------- 触发 ----------
    def trigger(self, event_name: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        for depth in range(len(self.active_path) - 1, -1, -1):
            prefix = self.active_path[: depth + 1]
            node = self._node_config(prefix)
            target = node.get("transitions", {}).get(event_name)
            if target is None:
                continue
            if isinstance(target, str) and target.startswith("#"):
                self._invoke("internal", prefix, extra={"event": event_name})
                return self.current_state_id, self._leaf_content()
            self._transition_to(prefix, target, event_name)
            return self.current_state_id, self._leaf_content()
        return None, f"无人处理事件 [{event_name}]（已冒泡至根）"

    def _transition_to(self, from_prefix: List[str], target: str, event: str):
        target_path = self._find_path(target)
        if not target_path:
            return
        self.active_path = list(target_path)
        common = 0
        while (common < len(from_prefix) and common < len(target_path)
               and from_prefix[common] == target_path[common]):
            common += 1
        for depth in range(len(from_prefix) - 1, common - 1, -1):
            self._invoke("exit", from_prefix[: depth + 1])
        for depth in range(common, len(target_path)):
            self._enter_node(target_path[: depth + 1])
        self._enter_default_descendants(target_path)
        self._invoke("transition", self.active_path,
                     extra={"from": "/".join(from_prefix), "event": event})

    def go_history(self, state_id: str):
        target_path = self._find_path(state_id)
        if not target_path or len(target_path) != 1:
            return
        node = self._node_config(target_path)
        if "substates" not in node:
            return
        self.active_path = list(target_path)
        self._enter_node(target_path)
        cached = self._history_cache.get(state_id)
        if cached:
            self._enter_specific_descendants(target_path, cached)
        elif node.get("initial"):
            self._enter_default_descendants(target_path)

    # ---------- 信息查询 ----------
    def _leaf_content(self) -> str:
        return self._node_config(self.active_path).get("content", f"[{self.current_leaf}]")

    def get_state_info(self) -> Dict[str, Any]:
        node = self._node_config(self.active_path)
        return {
            "id": self.current_leaf,
            "path": self.current_state_id,
            "content": node.get("content", ""),
            "on_enter": node.get("on_enter", ""),
            "on_exit": node.get("on_exit", ""),
            "available_events": self.available_events,
            "is_composite": self._is_composite(self.active_path),
        }

    @property
    def available_events(self) -> List[str]:
        events: List[str] = []
        for depth in range(len(self.active_path)):
            prefix = self.active_path[: depth + 1]
            node = self._node_config(prefix)
            events.extend(node.get("transitions", {}).keys())
        seen, out = set(), []
        for e in events:
            if e not in seen:
                seen.add(e)
                out.append(e)
        return out

    def can_trigger(self, event_name: str) -> bool:
        return event_name in self.available_events

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.history[-limit:]

    # ---------- 内部 ----------
    def _invoke(self, action_type: str, path: List[str], extra: Optional[Dict[str, Any]] = None):
        state_id = path[-1]
        node = self._node_config(path)
        description = node.get(f"on_{action_type}", "")
        if action_type == "transition":
            description = node.get("on_enter", "")
        if callable(self.on_action):
            detail = {"description": description, "path": "/".join(path)}
            if extra:
                detail.update(extra)
            self.on_action(action_type, state_id, detail)
        if action_type in ("enter", "exit", "internal", "transition"):
            self.history.append({
                "action": action_type,
                "state": "/".join(path),
                "event": (extra or {}).get("event", ""),
                "time": time.time(),
            })
