"""
expand_shared — Hell Below 统一数据扩充工具集

BaseExpander 模式：
  1. 每个游戏的 expand/run.py 定义一个 Expander(BaseExpander) 子类
  2. 调用 expander.execute(dry_run=True/False) 执行扩充
  3. 自动备份 → 变更追踪 → UTF-8 安全写入

关键设计决策：
  - 使用 Python json模块读写 JSON（避免 Windows sed 的 UTF-8 破坏问题）
  - 所有文件操作通过 BaseExpander 统一管理
  - dry-run 模式仅预览不写入
"""

__version__ = "1.0.0"

from .base import BaseExpander
from .config import ExpanderConfig

__all__ = ["BaseExpander", "ExpanderConfig"]
