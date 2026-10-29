"""gui/helpers.py — 面板 / 控制器共享的纯函数式辅助。

这些辅助不依赖 GUI 实例（无 self），因此面板自由函数与控制器方法都能复用，
避免「唯一性获取」逻辑在 panels 与 controllers 之间各写一份。
"""
from pathways_data import get_pathway
from uniqueness import Uniqueness


def get_pathway_uniqueness(pk: str) -> "Uniqueness":
    """获取（或创建）某途径的唯一性（与 ControllersMixin._pathway_uniqueness 等价）。"""
    return Uniqueness.get_or_create(f"{get_pathway(pk)['name']}唯一性", pk)
