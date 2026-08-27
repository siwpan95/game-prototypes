# anchor.py
# 锚系统 —— 人性之锚，对抗失控的最后防线
from typing import List, Optional

class Anchor:
    """
    锚：非凡者维系人性的纽带

    锚的强度决定了非凡者对抗失控的能力。
    天使位格以上，锚不仅需要人类羁绊，还需要更宏大的集体意识锚定。
    """

    # 各等级最低锚强度要求
    LEVEL_ANCHOR_REQUIREMENTS = {
        (9, 8): 0,        # 低序列：不需要锚
        (7, 6, 5): 30,    # 中序列：开始需要锚
        (4, 3): 60,       # 圣者：锚至关重要
        (2, 1): 100,      # 天使：无锚无法存在
        (0,): 200,        # 真神：需要宏大锚定
    }

    def __init__(self,
                 humanity: float = 80,
                 connections: int = 5,
                 name: str = "未命名"):
        """
        humanity: 人性值 (0-100)
        connections: 羁绊数量（家人、朋友、爱人等）
        name: 锚的名称标识
        """
        self.humanity = max(0, min(100, humanity))
        self.connections = max(0, connections)
        self.name = name
        self._believers: int = 0          # 信徒数量（天使级以上重要）
        self._legacy: float = 0.0         # 传说/诗歌/荣誉传承度
        self._mind_impressions: int = 0   # 千千万万人脑海中的印象数

    @property
    def strength(self) -> float:
        """锚强度计算"""
        base = self.humanity * (1 + 0.1 * self.connections)
        legacy_bonus = self._legacy * 0.5
        believer_bonus = self._believers * 0.001
        return base + legacy_bonus + believer_bonus

    @classmethod
    def required_for_level(cls, level: int) -> float:
        """获取某等级所需的最低锚强度"""
        for levels, req in cls.LEVEL_ANCHOR_REQUIREMENTS.items():
            if level in levels:
                return req
        return 0

    def add_connection(self, name: str = ""):
        """增加一个羁绊"""
        self.connections += 1
        if name:
            print(f"  💚 新羁绊：{name}（羁绊数：{self.connections}）")

    def lose_connection(self, name: str = ""):
        """失去一个羁绊"""
        if self.connections > 0:
            self.connections -= 1
            if name:
                print(f"  💔 失去羁绊：{name}（羁绊数：{self.connections}）")

    def add_believers(self, count: int):
        """增加信徒（用于天使/真神级锚定）"""
        self._believers += count

    def spread_legacy(self, amount: float):
        """传播传说/荣誉（用于天使/真神级锚定）"""
        self._legacy += amount

    def add_mind_impressions(self, count: int):
        """增加大众脑海中的印象"""
        self._mind_impressions += count

    @property
    def status(self) -> str:
        """锚状态评估"""
        s = self.strength
        if s >= 200:
            return "坚不可摧 —— 足以支撑真神位格"
        elif s >= 100:
            return "稳固 —— 足以支撑天使位格"
        elif s >= 60:
            return "可靠 —— 足以支撑圣者位格"
        elif s >= 30:
            return "可用 —— 足以支撑中序列"
        else:
            return "脆弱 —— 仅能支撑低序列"

    def report(self) -> str:
        """锚状态报告"""
        lines = [
            f"锚「{self.name}」:",
            f"  人性值: {self.humanity}",
            f"  羁绊数: {self.connections}",
            f"  强度:   {self.strength:.1f}",
            f"  状态:   {self.status}",
        ]
        if self._believers > 0:
            lines.append(f"  信徒:   {self._believers}")
        if self._legacy > 0:
            lines.append(f"  传承:   {self._legacy:.1f}")
        return "\n".join(lines)

    def __repr__(self):
        return f"Anchor('{self.name}', strength={self.strength:.1f})"

    # ─── 序列化（E4 存档/读档）───
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "humanity": self.humanity,
            "connections": self.connections,
            "believers": self._believers,
            "legacy": self._legacy,
            "mind_impressions": self._mind_impressions,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Anchor":
        if not d:
            return cls()
        a = cls(humanity=d.get("humanity", 80),
                connections=d.get("connections", 5),
                name=d.get("name", "未命名"))
        a._believers = d.get("believers", 0)
        a._legacy = d.get("legacy", 0.0)
        a._mind_impressions = d.get("mind_impressions", 0)
        return a
