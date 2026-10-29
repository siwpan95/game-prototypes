# uniqueness.py
# 唯一性系统 —— 序列0的权柄之争
import threading
from typing import Optional, Any

class Uniqueness:
    """
    唯一性：一条途径只能存在一个序列0的根源

    每一条途径都有且只有一个唯一性。
    谁持有唯一性，谁就是这条途径的真神候选人。
    唯一性之间会相互吸引，相近途径的唯一性会向同一方向聚合。
    """

    # 系统全局唯一性注册表
    _registry: dict[str, "Uniqueness"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, name: str, pathway_key: str = ""):
        """
        name: 唯一性名称（如"愚者唯一性"）
        pathway_key: 所属途径
        """
        self.name = name
        self.pathway_key = pathway_key
        self.lock = threading.Lock()
        self.owner: Optional[Any] = None
        self._history: list = []  # 持有者历史

        # 注册到全局表
        with self._registry_lock:
            self._registry[name] = self

    def bind(self, new_owner):
        """绑定唯一性到新的持有者"""
        with self.lock:
            if self.owner is not None and self.owner != new_owner:
                old_name = getattr(self.owner, 'SEQUENCE_NAME', '未知')
                raise RuntimeError(
                    f"唯一性[{self.name}]已被持有！\n"
                    f"  当前持有者：{old_name}\n"
                    f"  争夺者：{getattr(new_owner, 'SEQUENCE_NAME', '未知')}\n"
                    f"  争夺陷入死锁……"
                )
            old_owner = self.owner
            self.owner = new_owner
            self._history.append({
                "from": getattr(old_owner, 'SEQUENCE_NAME', '无人'),
                "to": getattr(new_owner, 'SEQUENCE_NAME', '未知'),
            })

    @property
    def is_bound(self) -> bool:
        return self.owner is not None

    @property
    def is_free(self) -> bool:
        return self.owner is None

    def unbind(self):
        """解除绑定（通常只在持有者死亡或放弃时发生）"""
        with self.lock:
            if self.owner:
                old_owner = getattr(self.owner, 'SEQUENCE_NAME', '未知')
                self._history.append({
                    "from": old_owner,
                    "to": "无人（解绑）",
                })
            self.owner = None

    @classmethod
    def get_by_name(cls, name: str) -> Optional["Uniqueness"]:
        """从全局注册表获取唯一性"""
        return cls._registry.get(name)

    @classmethod
    def get_or_create(cls, name: str, pathway_key: str = "") -> "Uniqueness":
        """
        获取已注册的同名唯一性；若不存在则创建。
        用于晋升序列0时自动集齐本途径唯一性。
        """
        if name in cls._registry:
            return cls._registry[name]
        return cls(name, pathway_key)

    @classmethod
    def _reset_state(cls):
        """清空全局注册表（仅供测试隔离使用）"""
        with cls._registry_lock:
            cls._registry.clear()

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有已创建的唯一性"""
        return list(cls._registry.keys())

    @property
    def history(self) -> str:
        """持有者变更历史"""
        if not self._history:
            return f"唯一性[{self.name}]尚未被绑定"
        lines = [f"唯一性[{self.name}] 持有者变更历史："]
        for i, entry in enumerate(self._history, 1):
            lines.append(f"  {i}. {entry['from']} → {entry['to']}")
        return "\n".join(lines)

    def __repr__(self):
        status = f"已被 {getattr(self.owner, 'SEQUENCE_NAME', '?')} 持有" if self.owner else "空闲"
        return f"<Uniqueness '{self.name}' ({status})>"


# ============================================================
# 序列1非凡特性
# ============================================================
class SequenceOneCharacteristic:
    """
    序列1非凡特性

    每条途径只有三份序列1非凡特性。
    集齐全部三份 + 唯一性 = 可晋升序列0。
    """

    # 全局序列1特性库存
    _inventory: dict[str, list["SequenceOneCharacteristic"]] = {}
    _inventory_lock = threading.Lock()

    def __init__(self, pathway_key: str, index: int = 1):
        """
        pathway_key: 所属途径
        index: 第几份（1/2/3）
        """
        self.pathway_key = pathway_key
        self.index = index
        self.owner: Optional[Any] = None

        with self._inventory_lock:
            if pathway_key not in self._inventory:
                self._inventory[pathway_key] = []
            self._inventory[pathway_key].append(self)

    def bind(self, new_owner):
        """绑定特性到持有者"""
        if self.owner is not None and self.owner != new_owner:
            raise RuntimeError(f"序列1特性[{self.pathway_key}#{self.index}]已被持有！")
        self.owner = new_owner

    def unbind(self):
        """解除绑定（持有者放弃/被击败时发生）"""
        self.owner = None

    @classmethod
    def available_count(cls, pathway_key: str) -> int:
        """某途径还有多少份可用（未被绑定的）序列1特性"""
        if pathway_key not in cls._inventory:
            return 3  # 尚未创建，全部可用
        return sum(1 for c in cls._inventory[pathway_key] if c.owner is None)

    @classmethod
    def owned_count(cls, pathway_key: str, owner) -> int:
        """某持有者拥有多少份序列1特性"""
        if pathway_key not in cls._inventory:
            return 0
        return sum(1 for c in cls._inventory[pathway_key] if c.owner is owner)

    @classmethod
    def ensure(cls, pathway_key: str, index: int = 1) -> "SequenceOneCharacteristic":
        """
        获取某途径指定序号的序列1特性；若不存在则创建。
        用于晋升序列0时集齐 3 份序列1特性。
        """
        for c in cls._inventory.get(pathway_key, []):
            if c.index == index:
                return c
        return cls(pathway_key, index)

    @classmethod
    def _reset_state(cls):
        """清空全局库存（仅供测试隔离使用）"""
        with cls._inventory_lock:
            cls._inventory.clear()

    def __repr__(self):
        status = "已绑定" if self.owner else "空闲"
        return f"<Seq1特性 {self.pathway_key}#{self.index} ({status})>"
