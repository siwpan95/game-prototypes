"""
可收集卡牌组件 — 类型安全版本。

标记实体为可收集的卡牌。
使用 dataclass 实现，类型安全。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING

from core.ecs import Component
from core.paths import ROOT


if TYPE_CHECKING:
    from core.event_bus import EventBus


@dataclass
class CardCollectible(Component):
    """
    可收集卡牌组件 — 标记实体为可收集的卡牌。

    当玩家触碰到拥有此组件的实体时，
    会标记 collected=True 并发出 CARD_COLLECTED 事件。
    """
    card_id: str = ""
    collected: bool = False
    data_loaded: bool = False
    cached_data: Dict[str, Any] = field(default_factory=dict)

    def load_data(self) -> Dict[str, Any]:
        """
        加载卡牌数据。

        返回：
            卡牌数据字典，包含 name, glyph, desc 等字段。
        """
        if self.data_loaded and self.cached_data:
            return self.cached_data

        path = ROOT / "data" / "cards" / f"{self.card_id}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    self.cached_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.cached_data = {"name": self.card_id, "glyph": "?"}
        else:
            self.cached_data = {"name": self.card_id, "glyph": "?"}

        self.data_loaded = True
        return self.cached_data

    def collect(self, event_bus: "EventBus") -> Dict[str, Any]:
        """
        收集此卡牌 — 标记 collected=True 并发出事件。

        参数：
            event_bus: 事件总线实例

        返回：
            卡牌数据字典
        """
        if not self.collected:
            self.collected = True
            data = self.load_data()
            event_bus.emit("CARD_COLLECTED", {
                "card_id": self.card_id,
                "name": data.get("name", self.card_id),
                "glyph": data.get("glyph", "?"),
            })
        return self.load_data()

    def __repr__(self) -> str:
        status = "collected" if self.collected else "uncollected"
        return f"CardCollectible({self.card_id!r}, {status})"
