"""fishtank —— 懒人桌面养鱼模拟器的平台无关领域层（L1 + L2）。

分层铁律：
- 本包**严禁 import tkinter**（保证可无头单测，并可对照移植到 XJ380 C++ 端）。
- `economy.py` / `offline.py` 是 L1 纯函数层：无 I/O、无全局状态、无非确定性随机。
- `allin_engine` 只被 `engine_bootstrap.py` 一个模块 import，其余模块从它取符号。
- 所有玩法数值来自 `data/balance.json`，代码内零硬编码。
- 🔴 本包所有含 dataclass 的文件禁止 `from __future__ import annotations`（E6）。
"""

__version__ = "1.0.0"
__all__ = ["engine_bootstrap", "constants", "events"]
