# pollution.py
# 污染系统 —— 精神污染与失控的完整模型
from enum import Enum

# ============================================================
# 污染等级
# ============================================================
class PollutionLevel(Enum):
    SANE = 0           # 清醒 —— 精神正常，无污染迹象
    WHISPERING = 1     # 低语 —— 偶尔听到不可名状的耳语
    HALLUCINATING = 2  # 幻觉 —— 看见不存在的符文与景象
    LOST = 3           # 失控 —— 理性崩坏，行为失控
    GOD_FALLEN = 4     # 神殒 —— 彻底疯癫，神性吞噬人性

    @property
    def label_cn(self) -> str:
        labels = {
            0: "清醒",
            1: "低语",
            2: "幻觉",
            3: "失控",
            4: "神殒",
        }
        return labels.get(self.value, "未知")

    @property
    def danger_level(self) -> str:
        """危险等级描述"""
        dangers = {
            0: "安全 —— 精神稳定",
            1: "警惕 —— 耳语初现，需注意",
            2: "危险 —— 幻觉侵蚀，锚检定开始",
            3: "极度危险 —— 随时可能失控",
            4: "终结 —— 人性已被彻底吞噬",
        }
        return dangers.get(self.value, "未知")

# ============================================================
# 异常体系
# ============================================================
class SequenceError(Exception):
    """序列错误基类"""
    pass

class InsanityError(SequenceError):
    """失控异常：精神阈值溢出，非凡者已失控"""
    def __init__(self, message="非凡者已失控！"):
        super().__init__(f"💀 {message}")

class AnchorBreakError(SequenceError):
    """锚断裂异常：锚强度不足以支撑当前序列"""
    pass

class PollutionSurgeError(SequenceError):
    """污染爆发异常：污染突然加剧"""
    pass

class RitualFailureError(SequenceError):
    """仪式失败异常"""
    pass

# ============================================================
# 污染来源
# ============================================================
class PollutionSource:
    """污染来源追踪"""

    SOURCES = {
        "acting": "扮演过度 —— 过度扮演导致精神烙印苏醒",
        "ritual": "仪式反噬 —— 晋升仪式失败或不当",
        "battle": "战斗创伤 —— 与高位格存在战斗的精神冲击",
        "knowledge": "禁忌知识 —— 接触不该知道的神秘学知识",
        "artifact": "封印物 —— 使用高等级封印物的代价",
        "whisper": "旧日耳语 —— 直接倾听隐秘存在的低语",
        "pathway_conflict": "途径冲突 —— 相近途径非凡特性聚合导致",
    }

    def __init__(self, source_type: str, intensity: float = 0.1):
        self.type = source_type
        self.intensity = intensity
        self.description = self.SOURCES.get(source_type, "未知污染源")

    def __repr__(self):
        return f"PollutionSource({self.type}, intensity={self.intensity})"


# ============================================================
# 污染管理器
# ============================================================
class PollutionManager:
    """管理非凡者的污染状态（连续 SAN / 理智值 + 离散污染等级）。

    SAN（理智值）是 0–100 的连续量：服魔药、用非凡能力、接触诡异都会下降；
    在教堂/安全屋或使用镇定剂可恢复。污染等级由 SAN 反向推导（SAN 越低，
    污染越高）。所有旧 API（level / is_lost / try_purify / .value / .name /
    .label_cn / report）保持兼容，未破坏既有测试契约。
    """

    # 每 1 点污染对应损失的 SAN（污染点 0→SAN100，3→SAN40，5→SAN0）
    SAN_PER_POINT = 20.0

    # SAN 阈值 → 命名状态。阈值与上溢映射 san = 100 - points*20 完全对齐：
    #   清醒(SANE)      SAN ∈ (80, 100]
    #   低语(WHISPERING) SAN ∈ (60, 80]
    #   幻觉(HALLUCINATING) SAN ∈ (40, 60]
    #   失控(LOST)      SAN ∈ (20, 40]
    #   神殒(GOD_FALLEN) SAN ∈ [0, 20]
    # 使用严格大于，使边界（SAN 80/60/40/20）与离散等级一致。
    SAN_STATES = [
        (80, "清醒"), (60, "低语"), (40, "幻觉"), (20, "失控"), (0, "神殒"),
    ]

    def __init__(self, initial: PollutionLevel = PollutionLevel.SANE):
        self.level = initial
        self._points = float(initial.value)
        self.sources: list = []
        self._update_level()

    def accumulate(self, source: PollutionSource):
        """累积污染（SAN 同步下降）"""
        self._points += source.intensity
        self.sources.append(source)
        self._update_level()

    def recover(self, san_amount: float = 10.0):
        """恢复 SAN（安全区/镇定剂效果），返回恢复后的 SAN 值"""
        self._points = max(0.0, self._points - san_amount / self.SAN_PER_POINT)
        self._update_level()
        return self.san

    def _update_level(self):
        """根据点数更新污染等级与连续 SAN"""
        new_level = min(int(self._points + 1e-9), PollutionLevel.GOD_FALLEN.value)
        previous = self.level
        self.level = PollutionLevel(new_level)
        self.san = max(0.0, 100.0 - self._points * self.SAN_PER_POINT)
        if previous != self.level:
            print(f"  ⚡ 污染等级变化：{previous.label_cn} → {self.level.label_cn}")
            print(f"     {self.level.danger_level}")

    # ─── 兼容属性：让 ch.pollution.value / .name / .label_cn 继续可用 ───
    @property
    def value(self) -> int:
        return self.level.value

    @property
    def name(self) -> str:
        return self.level.name

    @property
    def label_cn(self) -> str:
        return self.level.label_cn

    def san_status(self) -> str:
        """SAN 落入的命名状态（与污染等级 label_cn 完全对齐）"""
        for threshold, label in self.SAN_STATES:
            if self.san > threshold:
                return label
        return "神殒"

    @property
    def is_sane(self) -> bool:
        return self.level == PollutionLevel.SANE

    @property
    def is_lost(self) -> bool:
        return self.level.value >= PollutionLevel.LOST.value

    @property
    def is_god_fallen(self) -> bool:
        return self.level == PollutionLevel.GOD_FALLEN

    def try_purify(self, amount: float = 0.5) -> bool:
        """
        尝试净化污染（如使用无暗者能力）
        返回是否净化成功
        """
        self._points = max(0, self._points - amount)
        self._update_level()
        return self._points < PollutionLevel.LOST.value

    def report(self) -> str:
        lines = [
            f"污染等级: {self.level.label_cn} ({self.level.name})",
            f"污染点数: {self._points:.1f}",
            f"状态: {self.level.danger_level}",
        ]
        if self.sources:
            lines.append(f"污染来源次数: {len(self.sources)}")
            # 显示最近3个来源
            for src in self.sources[-3:]:
                lines.append(f"  - {src.description}")
        return "\n".join(lines)

    # ─── 序列化（E4 存档/读档）───
    def to_dict(self) -> dict:
        return {
            "points": self._points,
            "level": self.level.value,
            "sources": [{"type": s.type, "intensity": s.intensity}
                        for s in self.sources],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PollutionManager":
        """从存档字典重建污染管理器（不触发等级变化日志）"""
        pm = cls(PollutionLevel.SANE)
        if not d:
            return pm
        pm._points = float(d.get("points", 0.0))
        pm.sources = [PollutionSource(s["type"], float(s["intensity"]))
                      for s in d.get("sources", [])]
        # 直接由点数推导等级与 SAN，避免恢复时打印「等级变化」
        lvl = min(int(pm._points + 1e-9), PollutionLevel.GOD_FALLEN.value)
        pm.level = PollutionLevel(lvl)
        pm.san = max(0.0, 100.0 - pm._points * cls.SAN_PER_POINT)
        return pm
