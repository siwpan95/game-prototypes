"""
DataLibrary — 通用 JSON 数据驱动库基类。

消除 CardLibrary / EnemyLibrary 中的重复加载逻辑。
泛型参数 T 为库中的数据项类型（如 Card、Enemy）。

使用方式：

    from core.data_library import DataLibrary

    class CardLibrary(DataLibrary[Card]):
        def __init__(self):
            super().__init__(item_key="cards", item_name="卡牌", factory=Card.from_dict)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class DataLibrary(Generic[T]):
    """通用数据驱动库。

    特性：
    - 从 JSON 文件/目录加载数据项
    - 按 ID 注册与查询
    - 批量加载接口
    - Mod 目录支持

    子类需要提供：
        item_key: JSON 中数据列表所在的键名（如 "cards", "enemies"）
        factory: 从字典构建 T 的工厂函数（如 Card.from_dict, Enemy.from_dict）
    """

    item_key: str = "items"
    """JSON 文件中数据列表的键名。"""

    item_name: str = "数据项"
    """数据项的中文名称（用于日志）。"""

    def __init__(
        self,
        factory: Callable[[dict], T],
        item_key: str = "items",
        item_name: str = "数据项",
        logger: Any = None,
    ):
        """
        :param factory: 从 dict 构建数据项的工厂函数
        :param item_key: JSON 数据中的列表键名
        :param item_name: 数据项中文名
        :param logger: 可选的 Logger 实例（None 则使用 print）
        """
        self._items: dict[str, T] = {}
        self._factory = factory
        self.item_key = item_key
        self.item_name = item_name
        self._logger = logger

    def _log(self, msg: str) -> None:
        """记录警告/错误信息。"""
        tag = f"[{self.item_name}库]"
        if self._logger:
            self._logger.warning(f"{tag} {msg}")
        else:
            print(f"{tag} {msg}")

    # ── 加载 ──

    def load_from_json(self, source: str | Path | list[dict]) -> None:
        """从 JSON 数据加载。

        :param source:
            - str/Path: JSON 文件或目录路径
            - list[dict]: 数据项字典列表
        """
        if isinstance(source, list):
            self._load_from_list(source)
        elif isinstance(source, (str, Path)):
            path = Path(source)
            if path.is_dir():
                for f in sorted(path.glob("*.json")):
                    self._load_from_file(f)
            elif path.is_file():
                self._load_from_file(path)

    def load_from_mod_dir(self, mod_dir: str | Path, subdir: str = "") -> int:
        """从 Mod 目录加载。
        
        :param mod_dir: Mod 根目录
        :param subdir: 子目录名（默认使用 item_key，如 "cards", "enemies"）
        :returns: 加载的数据项数量
        """
        before = len(self._items)
        sub = subdir or self.item_key
        target_dir = Path(mod_dir) / sub
        if target_dir.exists():
            self.load_from_json(target_dir)
        return len(self._items) - before

    def _load_from_file(self, path: Path) -> None:
        """从单个 JSON 文件加载。"""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._load_from_list(data)
            elif isinstance(data, dict):
                if self.item_key in data:
                    self._load_from_list(data[self.item_key])
                elif "id" in data:
                    self._load_from_list([data])
        except (json.JSONDecodeError, OSError) as e:
            self._log(f"加载失败 {path}: {e}")

    def _load_from_list(self, data: list[dict]) -> None:
        """从字典列表批量加载。"""
        for item_data in data:
            item = self._factory(item_data)
            # 使用 id 字段作为键（兼容 card.id / enemy.id）
            # 注意：必须用 `is not None` 判断，避免 id 为 0（合法数值 ID）时被 falsy 丢弃
            item_id = getattr(item, "id", None)
            if item_id is not None:
                self._items[item_id] = item

    # ── 注册 ──

    def register(self, item: T) -> None:
        """注册单个数据项。"""
        item_id = getattr(item, "id", None)
        if item_id is not None:
            self._items[item_id] = item

    def register_batch(self, items: list[T]) -> None:
        """批量注册数据项。"""
        for item in items:
            self.register(item)

    # ── 查询 ──

    def get(self, item_id: str) -> Optional[T]:
        """按 ID 获取数据项。"""
        return self._items.get(item_id)

    def has(self, item_id: str) -> bool:
        """检查数据项是否存在。"""
        return item_id in self._items

    def list_all(self) -> list[T]:
        """列出所有数据项。"""
        return list(self._items.values())

    def list_by_metadata(self, key: str, value: Any) -> list[T]:
        """按 metadata 字段筛选。"""
        return [
            item for item in self._items.values()
            if getattr(item, "metadata", {}).get(key) == value
        ]

    # ── 属性 ──

    @property
    def all_items(self) -> dict[str, T]:
        """返回所有数据项（只读副本）。"""
        return dict(self._items)

    @property
    def count(self) -> int:
        """数据项种类数。"""
        return len(self._items)

    # ── 工厂方法 ──

    @classmethod
    def from_json(
        cls,
        source: str | Path,
        factory: Callable[[dict], T],
        item_key: str = "items",
        item_name: str = "数据项",
    ) -> "DataLibrary[T]":
        """从 JSON 创建 DataLibrary。

        :param source: JSON 文件/目录路径
        :param factory: 从 dict 构建 T 的工厂函数
        :param item_key: 数据列表键名
        :param item_name: 数据项名称
        """
        lib = cls(factory=factory, item_key=item_key, item_name=item_name)
        lib.load_from_json(source)
        return lib
