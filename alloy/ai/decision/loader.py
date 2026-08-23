# -*- coding: utf-8 -*-
"""
决策配置加载器（数据驱动）
============================

把「声明式 JSON 配置」转化为可运行的决策引擎实例，让 alloy 的
行为树 / 状态机 / 决策树 可以像卡牌库、敌人库一样从数据文件加载。

同时内置一份 **默认决策配置**（移植自 zhuangtaiji 的故障自愈行为树、
请求路由决策树、设备层次状态机、差分预测器），无需额外文件即可试用。

用法：
    from alloy.ai.decision.loader import (
        default_brains_config, build_brain_from_spec, load_decision_config,
    )

    cfg = default_brains_config()
    bt = build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"])
    hsm = build_brain_from_spec(cfg["state_machines"]["SM_Hier"])
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .behavior_tree import build_behavior_tree, Blackboard
from .decision_tree import build_decision_tree
from .state_machine import create_state_machine
from .difference_engine import FiniteDifference


# ==========================================
# 默认内置配置（无需外部文件即可运行）
# ==========================================
DEFAULT_CONFIG: Dict[str, Any] = {
    "state_machines": {
        "SM_Hier": {
            "type": "hierarchical",
            "initial": "power",
            "description": "设备控制（层次状态机：含子状态/历史/内部转移）",
            "states": {
                "power": {
                    "initial": "off",
                    "history": "shallow",
                    "content": "电源总开关",
                    "on_enter": "上电自检",
                    "substates": {
                        "off": {"content": "设备已关机",
                                "transitions": {"turn_on": "on"}},
                        "on": {
                            "initial": "idle",
                            "content": "设备已开机",
                            "substates": {
                                "idle": {"content": "空闲待命",
                                         "transitions": {"run": "working",
                                                         "fault": "error"}},
                                "working": {"content": "运行中",
                                            "transitions": {"stop": "idle",
                                                            "fault": "error"}},
                                "error": {"content": "⚠ 故障态",
                                          "on_enter": "触发故障告警",
                                          "transitions": {"reset": "#on",
                                                          "power_off": "off"}},
                            },
                            "transitions": {"power_off": "off"},
                        }
                    },
                    "transitions": {"kill": "off"},
                }
            },
        }
    },
    "behavior_trees": {
        "BT_SelfHeal": {
            "name": "故障自愈行为树",
            "root": {
                "type": "selector", "name": "根·优先处理",
                "children": [
                    {"type": "sequence", "name": "故障处理", "children": [
                        {"type": "condition", "name": "检测到故障",
                         "key": "fault", "op": "truthy"},
                        {"type": "action", "name": "隔离故障", "kind": "set",
                         "key": "isolated", "value": True},
                        {"type": "action", "name": "尝试重启", "kind": "set",
                         "key": "restarted", "value": True},
                    ]},
                    {"type": "sequence", "name": "高负载处理", "children": [
                        {"type": "condition", "name": "负载过高",
                         "key": "load", "op": "gt", "value": 80},
                        {"type": "action", "name": "横向扩容", "kind": "set",
                         "key": "scaled", "value": True},
                    ]},
                    {"type": "action", "name": "维持常态", "kind": "set",
                     "key": "healthy", "value": True},
                ],
            },
        }
    },
    "decision_trees": {
        "DT_Route": {
            "name": "请求路由决策树",
            "root": {
                "type": "condition", "name": "是否VIP", "key": "vip", "op": "truthy",
                "true": {"type": "condition", "name": "VIP是否紧急", "key": "urgent",
                         "op": "truthy",
                         "true": {"type": "action", "name": "VIP加急通道",
                                  "label": "vip_urgent",
                                  "payload": {"queue": "priority"}},
                         "false": {"type": "action", "name": "VIP普通通道",
                                   "label": "vip_normal",
                                   "payload": {"queue": "vip"}}},
                "false": {"type": "condition", "name": "负载是否过高",
                          "key": "load", "op": "gt", "value": 80,
                          "true": {"type": "action", "name": "限流排队",
                                   "label": "throttle",
                                   "payload": {"queue": "wait"}},
                          "false": {"type": "action", "name": "普通处理",
                                    "label": "normal",
                                    "payload": {"queue": "default"}}},
            },
        }
    },
    "difference_engine": {
        "progress_predictor": {
            "initial_values": [0, 12, 28, 48],
            "note": "用历史进度点差分，预测后续进度（多项式递推）",
        }
    },
}


def default_brains_config() -> Dict[str, Any]:
    """返回默认内置决策配置的深拷贝（避免外部修改污染）。"""
    return json.loads(json.dumps(DEFAULT_CONFIG))


# ==========================================
# 构造器
# ==========================================
def build_behavior_tree_from_spec(spec: Dict[str, Any],
                                  blackboard: Optional[Blackboard] = None):
    return build_behavior_tree(spec, blackboard=blackboard)


def build_decision_tree_from_spec(spec: Dict[str, Any]):
    return build_decision_tree(spec)


def build_state_machine_from_spec(machine_name: str, config: Dict[str, Any],
                                  on_action=None):
    return create_state_machine(machine_name, config, on_action=on_action)


def build_brain_from_spec(spec: Dict[str, Any], blackboard: Optional[Blackboard] = None):
    """根据一段声明式规格构造对应引擎实例。

    自动识别包含 "root"（行为树）、"root"+"type":"condition|switch"（决策树）
    或 "states"（状态机）的规格。
    """
    if "states" in spec:
        name = spec.get("name", "SM")
        return create_state_machine(name, {"state_machines": {name: spec}}, None)
    if spec.get("type") in ("condition", "switch") or (
            "root" in spec and spec["root"].get("type") in ("condition", "switch")):
        return build_decision_tree(spec)
    return build_behavior_tree(spec, blackboard=blackboard)


def build_finite_difference_from_spec(spec: Dict[str, Any]) -> FiniteDifference:
    return FiniteDifference(spec.get("initial_values", []))


# ==========================================
# 文件 / 字典 加载
# ==========================================
def load_decision_config(source: Any) -> Dict[str, Any]:
    """从字典、JSON 字符串或文件路径加载决策配置。

    source 可以是：
      * dict            —— 直接返回（深拷贝）
      * str（JSON）    —— json.loads
      * str（路径）    —— 读取并解析文件
    """
    if isinstance(source, dict):
        return json.loads(json.dumps(source))
    if isinstance(source, str):
        if os.path.isfile(source):
            with open(source, "r", encoding="utf-8") as f:
                return json.load(f)
        return json.loads(source)
    raise ValueError("无法识别的决策配置来源")
