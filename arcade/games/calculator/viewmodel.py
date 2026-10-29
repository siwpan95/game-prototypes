"""
CalculatorViewModel — MVVM ViewModel 层
职责：
  1. 持有可观察属性（Observable），供 View 绑定。
  2. 作为 Model 的唯一观察者，将 Model 原始状态映射为 View 需要的展现状态。
  3. 暴露 on_button(token) 命令方法供 View 调用，内部委托给 Model。
  4. 通过 add_side_effect_handler 向外（main.py）传递 quit / shuffle /
     achievement 信号，ViewModel 自身不执行 OS 级副作用。

View 只看 ViewModel，永不直接访问 Model。
ViewModel 只调用 Model，永不引用任何 tkinter 组件。
"""

from __future__ import annotations
from typing import Callable, Any


# ─────────────────────────────────────────────────────────────
#  Observable 属性帮助类
# ─────────────────────────────────────────────────────────────
class Observable:
    """单个可观察属性。值变更时通知所有已注册的侦听器。"""

    def __init__(self, initial: Any = None):
        self._value = initial
        self._listeners: list[Callable[[Any], None]] = []

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        if self._value != new_val:
            self._value = new_val
            self._notify(new_val)

    def bind(self, listener: Callable[[Any], None]) -> None:
        """注册侦听器；值变更时以新值为参数调用。"""
        self._listeners.append(listener)

    def _notify(self, val: Any) -> None:
        for listener in self._listeners:
            listener(val)


# ─────────────────────────────────────────────────────────────
#  CalculatorViewModel
# ─────────────────────────────────────────────────────────────
class CalculatorViewModel:
    """
    MVVM ViewModel：

    可观察属性（View 绑定）:
      display_text    — 主显示文字
      expression_text — 表达式行文字（= 后显示历史表达式）
      char_limit      — 是否触发字符上限（影响按钮禁用）
      digit_limit     — 是否触发数字键上限
      crypto_mode     — 当前密码学模式（"" 表示普通计算）
      achievement     — 最近解锁的成就 id（"" 表示无）

    命令（View 调用）:
      on_button(token) — 处理按钮点击

    副作用信号（main.py 注册）:
      add_side_effect_handler(action, handler) — 注册 quit / shuffle / achievement 处理器
    """

    def __init__(self, model):
        # ── 可观察属性 ────────────────────────────────────────────
        self.display_text:    Observable = Observable("0")
        self.expression_text: Observable = Observable("")
        self.char_limit:      Observable = Observable(False)
        self.digit_limit:     Observable = Observable(False)
        self.crypto_mode:     Observable = Observable("")
        self.achievement:     Observable = Observable("")

        # ── 内部引用 ──────────────────────────────────────────────
        self._model = model
        self._side_effect_handlers: dict[str, list[Callable[[], None]]] = {}

        # 向 Model 注册自己作为观察者
        model.add_observer(self._on_model_change)

    # ── 副作用注册 ────────────────────────────────────────────────
    def add_side_effect_handler(self, action: str, handler: Callable[[], None]) -> None:
        """
        注册特定 action 的副作用处理器。
        action: "quit" | "shuffle" | "achievement"
        同一 action 可注册多个处理器，按注册顺序调用。
        """
        self._side_effect_handlers.setdefault(action, []).append(handler)

    def _emit_side_effect(self, action: str) -> None:
        for handler in self._side_effect_handlers.get(action, []):
            handler()

    # ── 命令 ──────────────────────────────────────────────────────
    def on_button(self, token: str) -> None:
        """View 按钮点击的统一入口。将 token 推入 Model，由 Model 通知变更。"""
        self._model.push(token)

    # ── Model 观察者回调 ──────────────────────────────────────────
    def _on_model_change(self) -> None:
        """
        当 Model 状态改变时被调用。
        将 Model 的原始数据映射为 View 友好的展现属性，
        并触发需要外部处理的副作用信号。
        """
        m = self._model

        # 1. 更新主显示
        self.display_text.value = m.display_text or "0"

        # 2. 更新表达式行
        if m.last_action == "result":
            self.expression_text.value = m.last_eval_expr + " ="
        elif m.last_action in ("reset", "shuffle"):
            self.expression_text.value = ""
        else:
            self.expression_text.value = ""

        # 3. 更新限制标志
        self.char_limit.value  = m.char_limit
        self.digit_limit.value = m.digit_limit

        # 4. 更新当前模式（供 View 切换配色）
        self.crypto_mode.value = m._crypto_mode

        # 5. 检查是否解锁了成就
        last_ach = m.get_last_achievement()
        if last_ach:
            self.achievement.value = last_ach
            self._emit_side_effect("achievement")

        # 6. 触发副作用信号（不在 ViewModel 内处理，委托给注册者）
        if m.last_action in ("quit", "shuffle"):
            self._emit_side_effect(m.last_action)

    # ── 查询方法 ──────────────────────────────────────────────────
    def get_achievements(self) -> list[str]:
        """返回当前已解锁的成就 id 列表。"""
        return self._model.get_achievements()

    @property
    def alchemia_active(self) -> bool:
        """是否处于 Alchemia 解密游戏模式。"""
        return self._model.alchemia_active
