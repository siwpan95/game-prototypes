"""
叙事引擎：数据驱动的分支剧情系统。

融合 peasy-ai（原 easy-ai）叙事引擎的条件系统与数据模型，提供通用的分支剧情引擎。
支持场景跳转、撤销/重做、JSON 数据加载、条件表达式求值。

用法：
    from ai.narrative import NarrativeEngine, Scene, Option, ConditionEvaluator

    engine = NarrativeEngine("scenes.json")
    scene = engine.get_current_scene()
    options = engine.get_available_options()
    engine.choose_option(0)
    engine.save("save.json")
"""

import json
import random
import re
from dataclasses import dataclass, field
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================
# 数据模型
# ============================================================

@dataclass
class Option:
    """剧情选择项。

    Attributes:
        option_id: 选项唯一标识。
        text: 选项显示文本。
        next_scene: 选择后跳转的场景 ID。
        conditions: 选项可见条件，如 {"hp__gte": 50, "has_item": "sword"}。
        effects: 选择后的属性变化，如 {"hp": -10, "gold": 50}。
        flags_set: 选择后设置的标记列表。
    """
    option_id: str = ""
    text: str = ""
    next_scene: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)
    effects: Dict[str, int] = field(default_factory=dict)
    flags_set: List[str] = field(default_factory=list)


@dataclass
class Scene:
    """剧情场景。

    Attributes:
        scene_id: 场景唯一标识。
        title: 场景标题。
        text: 场景正文描述。
        options: 可选选项列表。
        speaker: 说话人（可选）。
        background: 背景标识（可选）。
        music: 背景音乐标识（可选）。
    """
    scene_id: str = ""
    title: str = ""
    text: str = ""
    options: List[Option] = field(default_factory=list)
    speaker: str = ""
    background: str = ""
    music: str = ""


@dataclass
class NarrativeState:
    """游戏运行状态。

    Attributes:
        current_scene_id: 当前场景 ID。
        attributes: 角色属性字典，如 {"hp": 80, "gold": 100}。
        flags: 已设置的事件标记集合。
        turn_count: 已进行的回合数。
        ending_triggered: 触发的结局 ID，None 表示未结束。
    """
    current_scene_id: str = ""
    attributes: Dict[str, int] = field(default_factory=dict)
    flags: Set[str] = field(default_factory=set)
    turn_count: int = 0
    ending_triggered: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """导出为可序列化字典。"""
        return {
            "current_scene_id": self.current_scene_id,
            "attributes": dict(self.attributes),
            "flags": sorted(self.flags),
            "turn_count": self.turn_count,
            "ending_triggered": self.ending_triggered,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NarrativeState":
        """从字典恢复状态。"""
        return cls(
            current_scene_id=data.get("current_scene_id", ""),
            attributes=data.get("attributes", {}),
            flags=set(data.get("flags", [])),
            turn_count=data.get("turn_count", 0),
            ending_triggered=data.get("ending_triggered"),
        )


# ============================================================
# 条件求值器
# ============================================================

# ── 已废弃别名 ──────────────────────────────────────────
# 原叙事状态类名 GameState 已于 2026-07-14 重命名为 NarrativeState。
# 保留此别名仅用于向后兼容下游复制副本；新代码请直接使用 NarrativeState。
GameState = NarrativeState


class ConditionEvaluator:
    """条件表达式求值器。

    支持的表达式格式：
    - 数值比较: "hp>=50"、"gold<=20"、"level>3"、"hp==100"
    - 大于/小于: "hp>10"、"hp<5"
    - 不等于: "rank!=1"
    - 标记检查: "has_item:sword" → 检查 flags 中是否有 "sword"
    - 标记排除: "!has_item:poison" → 检查 flags 中无 "poison"
    - 字典条件: {"hp__gte": 50, "flags__has": "sword"}

    表达式在 conditions 中可以为：
    - 字符串: "hp>=50"
    - 字典: {"hp__gte": 50, "has_item": "sword"}
    - 列表: ["hp>=50", "has_item:key"] (AND 逻辑)
    """

    # 数值比较模式：属性名 运算符 数值
    _NUM_PATTERN = re.compile(
        r'^(\w+)\s*(>=|<=|!=|==|>|<)\s*(\d+(?:\.\d+)?)$'
    )
    # 标记检查模式：has_item:标记名 或 !has_item:标记名
    _FLAG_PATTERN = re.compile(
        r'^(!?)has_item:(.+)$'
    )

    def check(self, conditions: Any, state: NarrativeState) -> bool:
        """检查条件是否满足。

        Args:
            conditions: 条件表达式。支持 str、dict、list、None。
            state: 当前游戏状态。

        Returns:
            True 表示条件满足（选项可见）。
        """
        # 无条件 → 总是满足
        if conditions is None:
            return True

        # 空列表/空字典 → 满足
        if isinstance(conditions, (list, dict)) and not conditions:
            return True

        # 字符串条件
        if isinstance(conditions, str):
            return self._check_string(conditions, state)

        # 字典条件
        if isinstance(conditions, dict):
            return self._check_dict(conditions, state)

        # 列表条件（AND 逻辑）
        if isinstance(conditions, list):
            return all(self.check(cond, state) for cond in conditions)

        return False

    def _check_string(self, expr: str, state: NarrativeState) -> bool:
        """求值单个字符串条件表达式。"""
        expr = expr.strip()

        # 标记检查：has_item:xxx 或 !has_item:xxx
        flag_match = self._FLAG_PATTERN.match(expr)
        if flag_match:
            negate = flag_match.group(1) == "!"
            flag_name = flag_match.group(2)
            has_flag = flag_name in state.flags
            return not has_flag if negate else has_flag

        # 数值比较：attr>=value
        num_match = self._NUM_PATTERN.match(expr)
        if num_match:
            attr = num_match.group(1)
            op = num_match.group(2)
            try:
                val = float(num_match.group(3))
            except ValueError:
                return False

            actual = state.attributes.get(attr, 0)
            return self._compare(actual, op, val)

        return False

    def _check_dict(self, cond: Dict[str, Any], state: NarrativeState) -> bool:
        """求值字典条件。支持 __gte、__lte、__gt、__lt、__eq、__ne、__has 后缀。"""
        for key, expected in cond.items():
            # has_item 特殊处理
            if key == "has_item":
                if expected not in state.flags:
                    return False
                continue

            # 按 __ 后缀解析
            if "__" in key:
                attr, op_suffix = key.rsplit("__", 1)
            else:
                # 无后缀 → 默认判断是否在 flags 中
                if expected not in state.flags:
                    return False
                continue

            actual = state.attributes.get(attr, 0)

            if op_suffix == "has":
                if expected not in state.flags:
                    return False
            elif op_suffix == "gte":
                if not (actual >= expected):
                    return False
            elif op_suffix == "lte":
                if not (actual <= expected):
                    return False
            elif op_suffix == "gt":
                if not (actual > expected):
                    return False
            elif op_suffix == "lt":
                if not (actual < expected):
                    return False
            elif op_suffix == "eq":
                if not (actual == expected):
                    return False
            elif op_suffix == "ne":
                if not (actual != expected):
                    return False
            else:
                return False

        return True

    @staticmethod
    def _compare(actual: float, op: str, expected: float) -> bool:
        """执行数值比较。"""
        ops = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        fn = ops.get(op)
        return fn(actual, expected) if fn else False


# ============================================================
# 场景历史（撤销/重做）
# ============================================================

@dataclass
class SceneHistory:
    """场景历史记录，支持撤销/重做。

    维护一个历史列表和当前位置指针。
    push 追加新场景；undo 回退；redo 前进。
    """
    history: List[str] = field(default_factory=list)
    position: int = -1

    def push(self, scene_id: str) -> None:
        """添加新场景到历史末尾，截断后续。"""
        if self.position < len(self.history) - 1:
            self.history = self.history[:self.position + 1]
        self.history.append(scene_id)
        self.position = len(self.history) - 1

    def undo(self) -> Optional[str]:
        """撤销一步，返回上一个场景 ID。"""
        if self.can_undo():
            self.position -= 1
            return self.history[self.position]
        return None

    def redo(self) -> Optional[str]:
        """重做一步，返回下一个场景 ID。"""
        if self.can_redo():
            self.position += 1
            return self.history[self.position]
        return None

    def can_undo(self) -> bool:
        """是否可撤销。"""
        return self.position > 0

    def can_redo(self) -> bool:
        """是否可重做。"""
        return self.position < len(self.history) - 1

    def clear(self) -> None:
        """清空历史。"""
        self.history.clear()
        self.position = -1

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典。"""
        return {"history": list(self.history), "position": self.position}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneHistory":
        """从字典恢复。"""
        return cls(
            history=data.get("history", []),
            position=data.get("position", -1),
        )


# ============================================================
# 叙事引擎
# ============================================================

class NarrativeEngine:
    """数据驱动的通用分支剧情引擎。

    从 JSON 文件加载场景数据，管理游戏状态、场景流转、选项选择。
    支持存档/读档、撤销/重做、条件过滤。

    用法：
        engine = NarrativeEngine("scenes.json")
        scene = engine.get_current_scene()
        for idx, opt in enumerate(engine.get_available_options()):
            print(f"[{idx}] {opt.text}")
        engine.choose_option(0)
    """

    VERSION = "1.0.0"

    def __init__(self, data_source: Any = None, *, start_scene: str = ""):
        """初始化叙事引擎。

        Args:
            data_source: 场景数据源。可以是 JSON 文件路径(str)、字典、或 None。
            start_scene: 指定起始场景 ID。为空时使用数据中第一个场景。
        """
        self._scenes: Dict[str, Scene] = {}
        self._start_scene: str = ""
        self.state = NarrativeState()
        self.evaluator = ConditionEvaluator()
        self.history = SceneHistory()

        # 事件回调列表
        self._listeners: List[Callable] = []

        # 加载数据
        if data_source is not None:
            if isinstance(data_source, str):
                self.load(data_source, start_scene=start_scene)
            elif isinstance(data_source, dict):
                self._load_from_dict(data_source, start_scene=start_scene)

    # ============================================================
    # 数据加载
    # ============================================================

    def load(self, filepath: str, *, start_scene: str = "") -> None:
        """从 JSON 文件加载场景数据。

        JSON 格式：
        {
            "start_scene": "beginning",
            "config": {
                "attribute_min": 0,
                "attribute_max": 100,
                "endings": {"end_death": "你死了...", "end_win": "你赢了！"}
            },
            "attributes": ["hp", "gold"],
            "attribute_default": 50,
            "scenes": [
                {
                    "scene_id": "beginning",
                    "title": "开始",
                    "text": "你来到了一个陌生的地方...",
                    "speaker": "",
                    "background": "forest",
                    "music": "calm_bgm",
                    "options": [
                        {
                            "option_id": "go_left",
                            "text": "向左走",
                            "next_scene": "left_path",
                            "conditions": {"hp__gte": 30},
                            "effects": {"hp": -5},
                            "flags_set": ["went_left"]
                        }
                    ]
                }
            ]
        }
        """
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._load_from_dict(data, start_scene=start_scene)

    def _load_from_dict(self, data: Dict[str, Any], *, start_scene: str = "") -> None:
        """从字典加载场景数据。"""
        scenes_list = data.get("scenes", [])

        # 构建场景字典
        self._scenes.clear()
        for raw in scenes_list:
            scene = self._parse_scene(raw)
            self._scenes[scene.scene_id] = scene

        # 确定起始场景
        self._start_scene = start_scene or data.get("start_scene", "")
        if not self._start_scene and self._scenes:
            self._start_scene = next(iter(self._scenes.keys()))

        # 初始化属性
        attrs = data.get("attributes", [])
        default_val = data.get("attribute_default", 50)
        self.state.attributes = {attr: default_val for attr in attrs}

        # 存储配置
        self._config = data.get("config", {})
        self._endings = self._config.get("endings", {})

        # 重置状态
        self.state.current_scene_id = self._start_scene
        self.state.flags.clear()
        self.state.turn_count = 0
        self.state.ending_triggered = None
        self.history.clear()
        self.history.push(self._start_scene)

    def _parse_scene(self, raw: Dict[str, Any]) -> Scene:
        """从字典解析单个场景。"""
        options = []
        for opt_raw in raw.get("options", []):
            conditions = opt_raw.get("conditions")
            # 将简单条件字符串包装为列表
            if isinstance(conditions, str):
                conditions = [conditions]

            option = Option(
                option_id=opt_raw.get("option_id", ""),
                text=opt_raw.get("text", ""),
                next_scene=opt_raw.get("next_scene", ""),
                conditions=conditions if conditions else {},
                effects=opt_raw.get("effects", {}),
                flags_set=opt_raw.get("flags_set", []),
            )
            options.append(option)

        return Scene(
            scene_id=raw.get("scene_id", ""),
            title=raw.get("title", ""),
            text=raw.get("text", ""),
            options=options,
            speaker=raw.get("speaker", ""),
            background=raw.get("background", ""),
            music=raw.get("music", ""),
        )

    # ============================================================
    # 核心接口
    # ============================================================

    def get_current_scene(self) -> Optional[Scene]:
        """获取当前场景。

        Returns:
            当前 Scene 对象，不存在时返回 None。
        """
        return self._scenes.get(self.state.current_scene_id)

    def get_available_options(self) -> List[Tuple[int, Option]]:
        """获取当前场景中条件满足的选项。

        Returns:
            [(原始索引, Option), ...] 过滤后仅保留条件满足的选项。
        """
        scene = self.get_current_scene()
        if scene is None:
            return []

        available: List[Tuple[int, Option]] = []
        for idx, option in enumerate(scene.options):
            if self.evaluator.check(option.conditions, self.state):
                available.append((idx, option))

        return available

    def choose_option(self, index: int) -> bool:
        """执行指定索引的选项。

        Args:
            index: 当前场景选项列表中的索引（0-based）。

        Returns:
            True 表示执行成功。
        """
        scene = self.get_current_scene()
        if scene is None or index < 0 or index >= len(scene.options):
            return False

        option = scene.options[index]

        # 检查条件
        if not self.evaluator.check(option.conditions, self.state):
            return False

        self.state.turn_count += 1

        # 应用属性效果
        for attr, delta in option.effects.items():
            if attr in self.state.attributes:
                self.state.attributes[attr] += delta
            else:
                self.state.attributes[attr] = delta

        # 设置标记
        for flag in option.flags_set:
            self.state.flags.add(flag)

        next_scene = option.next_scene

        # 检查结局场景
        if next_scene.startswith("end_"):
            self.state.ending_triggered = next_scene
            self._notify_listeners()
            return True

        # 检查属性触顶/触底
        if self._check_attribute_endings():
            self._notify_listeners()
            return True

        # 跳转场景
        if next_scene not in self._scenes:
            self.state.ending_triggered = "missing_scene"
            self._notify_listeners()
            return True

        self.state.current_scene_id = next_scene
        self.history.push(next_scene)
        self._notify_listeners()
        return True

    # ============================================================
    # 场景跳转
    # ============================================================

    def jump_to_scene(self, scene_id: str) -> bool:
        """直接跳转到任意场景。

        Args:
            scene_id: 目标场景 ID。

        Returns:
            True 表示跳转成功。
        """
        if scene_id not in self._scenes:
            return False

        self.state.current_scene_id = scene_id
        self.history.push(scene_id)
        self._notify_listeners()
        return True

    # ============================================================
    # 撤销/重做
    # ============================================================

    def undo(self) -> bool:
        """撤销到上一个场景。

        Returns:
            True 表示撤销成功。
        """
        prev = self.history.undo()
        if prev:
            self.state.current_scene_id = prev
            self._notify_listeners()
            return True
        return False

    def redo(self) -> bool:
        """重做到下一个场景。

        Returns:
            True 表示重做成功。
        """
        nxt = self.history.redo()
        if nxt:
            self.state.current_scene_id = nxt
            self._notify_listeners()
            return True
        return False

    def can_undo(self) -> bool:
        """是否可撤销。"""
        return self.history.can_undo()

    def can_redo(self) -> bool:
        """是否可重做。"""
        return self.history.can_redo()

    # ============================================================
    # 结局检查
    # ============================================================

    def _check_attribute_endings(self) -> bool:
        """检查属性是否触发结局。"""
        min_val = self._config.get("attribute_min", 0)
        max_val = self._config.get("attribute_max", 100)

        for attr, value in self.state.attributes.items():
            if value <= min_val:
                self.state.ending_triggered = f"low_{attr}"
                return True
            if value >= max_val:
                self.state.ending_triggered = f"high_{attr}"
                return True
        return False

    def get_ending_text(self) -> str:
        """获取当前结局文本。"""
        if not self.state.ending_triggered:
            return ""
        return self._endings.get(self.state.ending_triggered, self.state.ending_triggered)

    @property
    def is_ended(self) -> bool:
        """游戏是否已结束。"""
        return self.state.ending_triggered is not None

    # ============================================================
    # 存档/读档
    # ============================================================

    def save(self, filepath: str) -> None:
        """保存游戏进度到文件。"""
        data = {
            "version": self.VERSION,
            "state": self.state.to_dict(),
            "history": self.history.to_dict(),
            "config": self._config,
            "endings": self._endings,
            "start_scene": self._start_scene,
            "scene_ids": list(self._scenes.keys()),
        }
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, filepath: str) -> None:
        """从文件恢复游戏进度。"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.state = NarrativeState.from_dict(data.get("state", {}))
        self.history = SceneHistory.from_dict(data.get("history", {}))
        self._config = data.get("config", {})
        self._endings = data.get("endings", {})
        self._start_scene = data.get("start_scene", self._start_scene)
        self._notify_listeners()

    def restart(self) -> None:
        """重新开始游戏。"""
        self.state = NarrativeState()
        self.history.clear()
        self.state.current_scene_id = self._start_scene

        # 重新初始化属性
        attrs = list(self.state.attributes.keys())
        default_val = 50
        self.state.attributes = {attr: default_val for attr in attrs}

        self.history.push(self._start_scene)
        self._notify_listeners()

    # ============================================================
    # 场景管理
    # ============================================================

    def add_scene(self, scene: Scene) -> None:
        """动态添加场景。"""
        self._scenes[scene.scene_id] = scene

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取指定场景。"""
        return self._scenes.get(scene_id)

    def list_scenes(self) -> List[str]:
        """列出所有场景 ID。"""
        return list(self._scenes.keys())

    def scene_count(self) -> int:
        """场景总数。"""
        return len(self._scenes)

    # ============================================================
    # 事件监听
    # ============================================================

    def add_listener(self, callback: Callable) -> None:
        """注册状态变更监听器。"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """移除监听器。"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        """通知所有监听器。"""
        for cb in self._listeners:
            try:
                cb(self)
            except Exception:
                pass

    # ============================================================
    # 属性/信息
    # ============================================================

    @property
    def title(self) -> str:
        """剧情标题。"""
        return self._config.get("title", "未命名剧情")

    @property
    def current_scene_id(self) -> str:
        """当前场景 ID。"""
        return self.state.current_scene_id

    @property
    def turn_count(self) -> int:
        """已进行回合数。"""
        return self.state.turn_count

    def get_stats(self) -> Dict[str, Any]:
        """获取游戏统计信息。"""
        return {
            "turn_count": self.state.turn_count,
            "current_scene": self.state.current_scene_id,
            "attributes": dict(self.state.attributes),
            "flags": sorted(self.state.flags),
            "is_ended": self.is_ended,
            "ending": self.state.ending_triggered,
            "history_length": len(self.history.history),
        }

    def __repr__(self) -> str:
        return (
            f"<NarrativeEngine title='{self.title}' "
            f"scene='{self.state.current_scene_id}' "
            f"attrs={self.state.attributes} "
            f"ended={self.is_ended}>"
        )


# ============================================================
# 便捷工具函数
# ============================================================

def load_scenes_from_json(filepath: str) -> List[Scene]:
    """从 JSON 文件加载场景列表。

    JSON 中 scenes 数组会被解析为 Scene 对象列表。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes: List[Scene] = []
    for raw in data.get("scenes", data if isinstance(data, list) else []):
        if isinstance(raw, dict) and "scene_id" in raw:
            options = []
            for opt_raw in raw.get("options", []):
                conditions = opt_raw.get("conditions")
                if isinstance(conditions, str):
                    conditions = [conditions]
                option = Option(
                    option_id=opt_raw.get("option_id", ""),
                    text=opt_raw.get("text", ""),
                    next_scene=opt_raw.get("next_scene", ""),
                    conditions=conditions if conditions else {},
                    effects=opt_raw.get("effects", {}),
                    flags_set=opt_raw.get("flags_set", []),
                )
                options.append(option)

            scene = Scene(
                scene_id=raw.get("scene_id", ""),
                title=raw.get("title", ""),
                text=raw.get("text", ""),
                options=options,
                speaker=raw.get("speaker", ""),
                background=raw.get("background", ""),
                music=raw.get("music", ""),
            )
            scenes.append(scene)

    return scenes
