"""
记忆组件 — 类型安全版本。

标记实体为可触发的记忆物件。
使用 dataclass 实现，类型安全。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING

from core.ecs import Component
from core.paths import ROOT


if TYPE_CHECKING:
    from core.event_bus import EventBus


@dataclass
class Memory(Component):
    """
    记忆组件 — 标记实体为可触发的记忆物件。

    当玩家触碰到拥有此组件的实体时，
    会加载对应的记忆数据并发出 MEMORY_TRIGGERED 事件。
    """
    memory_id: str = ""
    discovered: bool = False
    data_loaded: bool = False
    cached_data: Dict[str, Any] = None

    def __post_init__(self):
        """初始化后处理。"""
        if self.cached_data is None:
            self.cached_data = {}

    def load_data(self) -> Dict[str, Any]:
        """
        加载记忆数据。

        返回：
            记忆数据字典，包含 name, sanity_cost, text 等字段。
        """
        if self.data_loaded and self.cached_data:
            return self.cached_data

        # 检查是否是问题类型
        if self.memory_id.startswith("q_"):
            data = self._load_question()
        else:
            data = self._load_memory_file()

        self.cached_data = data
        self.data_loaded = True
        return data

    def _load_memory_file(self) -> Dict[str, Any]:
        """从 JSON 文件加载记忆数据。"""
        path = ROOT / "data" / "memories" / f"{self.memory_id}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"name": "???", "sanity_cost": 0, "text": "..."}

    def _load_question(self) -> Dict[str, Any]:
        """从 mansion_objects.json 加载问题数据。"""
        obj_path = ROOT / "data" / "mansion_objects.json"
        try:
            with open(obj_path, encoding="utf-8") as f:
                obj_data = json.load(f)
            for q in obj_data.get("memory_questions", []):
                if q["id"] == self.memory_id:
                    return {
                        "id": self.memory_id,
                        "name": "记忆之问",
                        "sanity_cost": 0,
                        "text": q["text"],
                        "answer_card": q.get("answer_card", ""),
                    }
        except (json.JSONDecodeError, IOError):
            pass
        return {"id": self.memory_id, "name": "???", "sanity_cost": 0, "text": "..."}

    def trigger(self, event_bus: "EventBus") -> None:
        """
        触发记忆 — 标记 discovered=True 并发出事件。

        参数：
            event_bus: 事件总线实例
        """
        if not self.discovered:
            self.discovered = True
        data = self.load_data()
        event_bus.emit("MEMORY_TRIGGERED", data)

    def __repr__(self) -> str:
        status = "discovered" if self.discovered else "hidden"
        return f"Memory({self.memory_id!r}, {status})"
