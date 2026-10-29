# sequences.py
# 诡秘之主 序列核心系统 —— 数据驱动、途径切换、扮演消化
import random
from pollution import PollutionLevel, InsanityError, PollutionManager
from anchor import Anchor
from typing import List, Optional

# ============================================================
# BaseSequence —— 所有序列的抽象父类
# ============================================================
class BaseSequence:
    """
    所有序列的父类
    注意：此类本身就是一个巨大的技术债 —— 但已经是系统中最好用的技术债
    """
    SEQUENCE_NAME: str = "Unknown"
    LEVEL: int = 99
    PATHWAY_KEY: str = ""
    PATHWAY_NAME: str = ""

    def __init__(self):
        self.pollution: PollutionManager = PollutionManager(PollutionLevel.SANE)
        self.anchor: Optional[Anchor] = None
        self.abilities: List[str] = []
        self.digestion_actions: List[str] = []   # 已执行的扮演行为（历史）
        self.action_weight: dict = {}            # 各行为累积的消化权重（E5）
        self.required_actions: set = set()       # 本序列必须完成的行为名集合
        self._act_description: str = "我在行动。"  # act() 的默认描述
        self._ritual: Optional[str] = None       # 晋升本序列需要的仪式（序列5+）
        self._curse: Optional[str] = None        # 本序列的诅咒
        self._special: Optional[str] = None      # 特殊说明
        self.gender: str = "未指定"              # 角色性别
        self._hallucinating: bool = False        # 是否已陷入幻觉（污染达幻觉级）

    def act_catalog(self) -> List[str]:
        """子类覆盖：返回本序列可执行的所有扮演行为名"""
        return list(self.required_actions) if self.required_actions else []

    def perform_action(self, action_name: str, quality: str = "active"):
        """执行扮演行为，累积消化度（E5 质量维度）。

        quality:
          "active"    主动贴合扮演 → 权重 +1.0（默认，兼容旧调用）
          "passive"   被动剧情选择 → 权重 +0.5（可重复渐进消化）
          "divergent" 背离身份扮演 → 权重 -0.5（扣分）
        """
        weight = {"active": 1.0, "passive": 0.5, "divergent": -0.5}.get(quality, 1.0)
        if action_name in self.required_actions:
            self.add_digestion(action_name, weight)
        if self._hallucinating and random.random() < 0.3:
            print(f"[疯狂] {self.SEQUENCE_NAME} 看见了不存在的符文……")
        else:
            self.act()

    def add_digestion(self, action_name: str, weight: float = 1.0):
        """累积某行为的消化权重（被 perform_action 与事件结算共用）"""
        self.digestion_actions.append(action_name)
        self.action_weight[action_name] = self.action_weight.get(action_name, 0.0) + weight

    @property
    def digestion_ratio(self) -> float:
        """消化进度 0.0~1.0（按各行为的累积权重求均值，E5）"""
        if not self.required_actions:
            return 1.0
        s = sum(self.action_weight.get(a, 0.0) for a in self.required_actions)
        return max(0.0, min(s / len(self.required_actions), 1.0))

    @property
    def digested(self) -> bool:
        """扮演是否完全消化"""
        return self.digestion_ratio >= 1.0

    def check_sanity(self):
        """理智心跳检测，污染过高时触发疯狂"""
        if self.pollution.value >= PollutionLevel.LOST.value:
            raise InsanityError(f"{self.SEQUENCE_NAME} 已失控！")
        if self.pollution.value >= PollutionLevel.HALLUCINATING.value and not self._hallucinating:
            self._hallucinating = True
            if "不可名状的低语" not in self.abilities:
                self.abilities.append("不可名状的低语")

    def act(self):
        """执行行为（默认实现）"""
        print(self._act_description)

    @property
    def needs_ritual(self) -> bool:
        """本序列晋升是否需要仪式"""
        return self._ritual is not None

    @property
    def ritual(self) -> Optional[str]:
        return self._ritual

    @property
    def curse(self) -> Optional[str]:
        return self._curse

    @property
    def special(self) -> Optional[str]:
        return self._special

    def __repr__(self):
        return f"<{self.PATHWAY_NAME}途径·序列{self.LEVEL}·{self.SEQUENCE_NAME}>"


# ============================================================
# Sequence —— 数据驱动的序列类
# ============================================================
class Sequence(BaseSequence):
    """
    数据驱动的序列实例
    从 pathways_data 中读取序列配置，无需为每个序列写单独的类
    """

    def __init__(self, pathway_key: str, level: int, seq_data: dict,
                 pathway_data: dict, gender: str = "未指定"):
        super().__init__()
        self.PATHWAY_KEY = pathway_key
        self.PATHWAY_NAME = pathway_data["name"]
        self.TAROT = pathway_data.get("tarot", "?")
        self.GROUP_KEY = pathway_data["group"]
        self.SEQUENCE_NAME = seq_data["name"]
        self.LEVEL = level
        self.abilities = list(seq_data.get("abilities", []))
        self.required_actions = set(seq_data.get("required_actions", []))
        self._act_description = f"[{self.PATHWAY_NAME}·{self.SEQUENCE_NAME}] 执行序列行为……"
        self._ritual = seq_data.get("ritual")
        self._curse = seq_data.get("curse")
        self._special = seq_data.get("special")
        self.gender = gender

        # 从 pathway_data 推断性别转换
        self._gender_change_levels = set(pathway_data.get("gender_change", []))

    def act_catalog(self) -> List[str]:
        return list(self.required_actions)

    def act(self):
        """默认行为表现"""
        behaviors = {
            "偷窃": "我在观察，我在寻找机会……",
            "潜入": "我隐入阴影，无人察觉……",
            "编织谎言": "我在编织谎言，我在误导认知……",
            "欺诈他人": "信则有，不信则无……不过你已经信了。",
        }
        for action in self.required_actions:
            if action in behaviors:
                print(behaviors[action])
                return
        print(self._act_description)

    def will_gender_change_on_ascend(self, target_level: int) -> bool:
        """晋升到目标等级是否会改变性别"""
        return target_level in self._gender_change_levels

    @property
    def summary(self) -> str:
        """单行摘要"""
        parts = [
            f"{self.PATHWAY_NAME}途径(塔罗:{self.TAROT})",
            f"序列{self.LEVEL}·{self.SEQUENCE_NAME}",
        ]
        if self._curse:
            parts.append(f"[诅咒:{self._curse}]")
        if self._special:
            parts.append(f"[{self._special}]")
        if self.needs_ritual:
            parts.append("[需仪式晋升]")
        return " | ".join(parts)

    def full_report(self) -> str:
        """完整报告"""
        lines = [
            f"╔══════════════════════════════════════╗",
            f"║  {self.PATHWAY_NAME}途径 · 塔罗牌：{self.TAROT}",
            f"║  序列{self.LEVEL}：{self.SEQUENCE_NAME}",
            f"╠══════════════════════════════════════╣",
            f"║  性别：{self.gender}",
            f"║  能力：{'、'.join(self.abilities)}",
            f"║  扮演行为：{'、'.join(self.required_actions)}",
            f"║  消化度：{self.digestion_ratio:.0%}",
            f"║  污染等级：{self.pollution.name}",
        ]
        if self.anchor:
            lines.append(f"║  锚强度：{self.anchor.strength:.1f}")
        if self._curse:
            lines.append(f"║  诅咒：{self._curse}")
        if self._special:
            lines.append(f"║  特殊：{self._special}")
        if self._ritual:
            lines.append(f"║  晋升仪式：{self._ritual}")
        try:
            from pathway_groups import sealed_artifact_level
            sa = sealed_artifact_level(self.LEVEL)
            lines.append(f"║  对应封印物：{sa['name']}（{sa['corresponds']}）")
        except Exception:
            pass
        lines.append(f"╚══════════════════════════════════════╝")
        return "\n".join(lines)

    # ─── 序列化（E4 存档/读档）───
    def to_dict(self) -> dict:
        """导出角色动态状态（途径/等级等静态数据由 pathways_data 重建）"""
        return {
            "pathway_key": self.PATHWAY_KEY,
            "level": self.LEVEL,
            "gender": self.gender,
            "abilities": list(self.abilities),
            "digestion_actions": list(self.digestion_actions),
            "action_weight": dict(self.action_weight),
            "hallucinating": self._hallucinating,
            "pollution": self.pollution.to_dict(),
            "anchor": self.anchor.to_dict() if self.anchor else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Sequence":
        """从存档字典重建角色（先按途径/等级重建，再叠加动态状态）"""
        ch = make_sequence(d["pathway_key"], d["level"])
        ch.gender = d.get("gender", ch.gender)
        ch.abilities = list(d.get("abilities", ch.abilities))
        ch.digestion_actions = list(d.get("digestion_actions", []))
        ch.action_weight = dict(d.get("action_weight", {}))
        ch._hallucinating = d.get("hallucinating", False)
        ch.pollution = PollutionManager.from_dict(d.get("pollution"))
        if d.get("anchor"):
            ch.anchor = Anchor.from_dict(d["anchor"])
        return ch


# ============================================================
# 序列工厂 —— 从途径数据创建序列实例
# ============================================================
def make_sequence(pathway_key: str, level: int = 9) -> Sequence:
    """
    从途径数据工厂创建序列实例
    用法: klein = make_sequence("error", 9)   # 偷盗者
    """
    from pathways_data import get_sequence_data, get_pathway
    seq_data = get_sequence_data(pathway_key, level)
    pathway_data = get_pathway(pathway_key)

    # 检查途径组的性别转换规则
    gender = "未指定"
    if pathway_key == "red_priest":
        gender = "女"  # 初始女性，后续变性
    elif pathway_key == "chaos_witch":
        gender = "男"  # 初始男性，序列7变性
    elif pathway_key == "mother":
        gender = "男" if level >= 2 else "女"
    elif pathway_key == "moon":
        gender = "男" if level >= 1 else "女"

    return Sequence(pathway_key, level, seq_data, pathway_data, gender)


# ============================================================
# 向后兼容：保留原有 Thief / Fraudster 类
# 它们现在是 Sequence 的薄封装
# ============================================================
def define_sequence(level: int, name: str):
    """装饰器：快速设置序列名和等级（向后兼容）"""
    def decorator(cls):
        cls.SEQUENCE_NAME = name
        cls.LEVEL = level
        return cls
    return decorator

@define_sequence(level=9, name="偷盗者")
class Thief(Sequence):
    def __init__(self):
        from pathways_data import get_sequence_data, get_pathway
        seq_data = get_sequence_data("error", 9)
        pathway_data = get_pathway("error")
        super().__init__("error", 9, seq_data, pathway_data)

@define_sequence(level=8, name="诈骗师")
class Fraudster(Sequence):
    def __init__(self):
        from pathways_data import get_sequence_data, get_pathway
        seq_data = get_sequence_data("error", 8)
        pathway_data = get_pathway("error")
        super().__init__("error", 8, seq_data, pathway_data)
