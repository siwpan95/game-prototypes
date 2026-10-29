"""_engine — 统一到 allin_engine 引擎的通用能力（去重，复用引擎源码）。

MC2 原本内联了 allin_engine 的三个稳定基础能力（Serializable / JSONLoader /
InputManager）。整合后改为直接 re-export allin_engine 的对应实现，消除重复代码，
让 MC2 与引擎保持同一份真相源、随引擎升级自动受益：

  - Serializable  ← allin_engine.core.serializable
  - JSONLoader    ← allin_engine.utils.json_loader
  - InputManager  ← allin_engine.systems.input

要求 allin_engine 包可导入（MC2 启动时已将其父目录 <仓库根> 注入 sys.path，
测试时由 tests/conftest.py 与 tests/_testutil.py 注入）。
"""

from allin_engine.core.serializable import Serializable
from allin_engine.utils.json_loader import JSONLoader
from allin_engine.systems.input import InputManager

__all__ = ["Serializable", "JSONLoader", "InputManager"]
