"""_engine — 统一到 alloy 引擎的通用能力（去重，复用引擎源码）。

MC2 原本内联了 alloy 的三个稳定基础能力（Serializable / JSONLoader /
InputManager）。整合后改为直接 re-export alloy 的对应实现，消除重复代码，
让 MC2 与引擎保持同一份真相源、随引擎升级自动受益：

  - Serializable  ← alloy.core.serializable
  - JSONLoader    ← alloy.utils.json_loader
  - InputManager  ← alloy.systems.input

要求 alloy 包可导入（MC2 启动时已将其父目录 D:/allin/MCclone 注入 sys.path，
测试时由 tests/conftest.py 与 tests/_testutil.py 注入）。
"""

from alloy.core.serializable import Serializable
from alloy.utils.json_loader import JSONLoader
from alloy.systems.input import InputManager

__all__ = ["Serializable", "JSONLoader", "InputManager"]
