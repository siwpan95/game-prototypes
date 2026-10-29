"""移动方向。

原始实现用裸字符串 ``'left' / 'right' / 'up' / 'down'`` 在函数间传递，
拼错只会静默地什么都不做。这里收敛成枚举，非法值在边界处立即报错。
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Direction"]


class Direction(Enum):
    """四个移动方向。

    枚举值保留为小写字符串，方便 CLI 直接传参与打印。
    """

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"

    @classmethod
    def parse(cls, value: "str | Direction") -> "Direction":
        """把用户输入（字符串或枚举）解析成 :class:`Direction`。

        :raises ValueError: 无法识别时抛出，并列出所有合法值。
        """
        if isinstance(value, cls):
            return value
        key = str(value).strip().lower()
        aliases = {
            "l": cls.LEFT,
            "r": cls.RIGHT,
            "u": cls.UP,
            "d": cls.DOWN,
            "a": cls.LEFT,
            "w": cls.UP,
            "s": cls.DOWN,
            "h": cls.LEFT,
            "j": cls.DOWN,
            "k": cls.UP,
        }
        if key in aliases:
            return aliases[key]
        for member in cls:
            if member.value == key:
                return member
        legal = ", ".join(m.value for m in cls)
        raise ValueError(f"无法识别的方向 {value!r}，合法取值为: {legal}")

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return self.value
