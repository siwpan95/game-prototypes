"""Python 端 GUI 层（tkinter）。

分层约定：本包**只**负责显示与输入，一切玩法逻辑都在 `fishtank/` 里。
所以 `fishtank/` 可以脱离 tkinter 在无头环境跑测试与压测。

🔴 本包内禁止中文字面量面向用户（准则 L6 与 §7.6）：
所有用户可见文案一律走 `data/ui_text.json`。代码里的中文只允许出现在
注释与 docstring 中。
"""

__all__ = []
