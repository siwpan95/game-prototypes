# rivals.py
# AI 对手非凡者系统（E8）
#
# Rival：一个随 tick 推进的 AI 非凡者，复用 sequences / ascension / uniqueness 的
#   真实模型（与玩家共用 uniqueness.py 的全局 owner 注册表，从而让「权柄争夺」变成
#   有实际对手的博弈 —— 你拖延时，对手会先占住唯一性/序列1 的 owner 槽位，你再去
#   收集时便要走「击败并夺取」的路径，逻辑完全复用现有控制器）。
# RivalSystem：管理 1–N 名对手，在「其它途径」上随时光推进。
#
# 纯逻辑模块，不依赖 tkinter，可被无头单测直接覆盖，并可随 GameSession 序列化（E4/E11）。
import random
from sequences import make_sequence, Sequence
from anchor import Anchor
from ascension import ascend
from uniqueness import Uniqueness, SequenceOneCharacteristic
from pathways_data import get_pathway


class Rival:
    """一个 AI 对手非凡者。"""

    def __init__(self, name, pathway_key, start_level=9, gender=None, aggression=1.0):
        self.name = name
        self.pathway_key = pathway_key
        self.aggression = float(aggression)
        self._claimed = False
        self.character = make_sequence(pathway_key, start_level)
        if gender is not None:
            self.character.gender = gender
        self._ensure_anchor()

    def _ensure_anchor(self):
        ch = self.character
        if ch.anchor is None:
            ch.anchor = Anchor(humanity=100, connections=20, name=f"{self.name}之锚")
            ch.anchor.add_believers(1_000_000)

    def advance_one_tick(self, rng=None, logs=None):
        """推进一个 tick：消化扮演；若已消化且非序列0则尝试晋升；序列1后争夺权柄。"""
        rng = rng or random
        logs = logs if logs is not None else []
        ch = self.character
        # 1. 扮演消化（按 aggression 决定每 tick 执行几个行为）
        catalog = ch.act_catalog()
        if catalog and not ch.digested:
            steps = max(1, int(round(self.aggression)))
            for _ in range(steps):
                if ch.digested:
                    break
                ch.perform_action(rng.choice(catalog))
        # 2. 已消化且非序列0 → 尝试晋升
        if ch.digested and ch.LEVEL > 0:
            try:
                self.character = ascend(ch, ritual_check=lambda: True)
                logs.append(f"⬆ {self.name} 晋升 → {self.character.SEQUENCE_NAME}")
            except Exception as e:
                logs.append(f"! {self.name} 晋升受阻：{e}")
        # 3. 抵达序列1 后尝试容纳本途径权柄（与玩家竞争唯一性/序列1 槽位）
        if self.character.LEVEL <= 1 and not self._claimed:
            self._try_claim_authority(logs)
        return logs

    def _try_claim_authority(self, logs):
        """争夺本途径唯一性 + 3 份序列1 特性（仅当槽位空闲，不掠夺玩家已持有者）。"""
        pk = self.pathway_key
        pname = get_pathway(pk)["name"]
        u = Uniqueness.get_or_create(f"{pname}唯一性", pk)
        if u.owner is None:
            u.bind(self.character)
            logs.append(f"🔒 {self.name} 容纳了 {pname}途径唯一性")
        for i in (1, 2, 3):
            c = SequenceOneCharacteristic.ensure(pk, i)
            if c.owner is None:
                c.bind(self.character)
        self._claimed = True

    def snapshot(self):
        ch = self.character
        pname = get_pathway(self.pathway_key)["name"]
        u = Uniqueness.get_or_create(f"{pname}唯一性", self.pathway_key)
        return {
            "name": self.name,
            "pathway_key": self.pathway_key,
            "pathway_name": ch.PATHWAY_NAME,
            "sequence_name": ch.SEQUENCE_NAME,
            "level": ch.LEVEL,
            "digestion": ch.digestion_ratio,
            "claimed": self._claimed,
            "owns_uniqueness": (u.owner is self.character),
        }

    def to_dict(self):
        return {
            "name": self.name,
            "pathway_key": self.pathway_key,
            "aggression": self.aggression,
            "claimed": self._claimed,
            "character": self.character.to_dict(),
        }

    @classmethod
    def from_dict(cls, d):
        r = cls.__new__(cls)
        r.name = d["name"]
        r.pathway_key = d["pathway_key"]
        r.aggression = float(d.get("aggression", 1.0))
        r._claimed = bool(d.get("claimed", False))
        r.character = Sequence.from_dict(d["character"])
        return r


# 默认对手名册（用于「添加对手」时随机抽取，避免与玩家同途径）
_RIVAL_NAMES = ["Amon", "Adam", "Bethel", "Megaira", "Zaratul",
                "Ouroboros", "Medicì", "Cheek", "Teneboro", "Salinger"]


class RivalSystem:
    """管理多名对手；随 tick 推进并在权柄上形成竞争。"""

    def __init__(self, rivals=None, seed=None, tick_count=0):
        self.rivals = list(rivals) if rivals else []
        self.rng = random.Random(seed)
        self.tick_count = tick_count

    def add_rival(self, pathway_key, name=None, start_level=9, aggression=1.0):
        if name is None:
            used = {r.name for r in self.rivals}
            name = next((n for n in _RIVAL_NAMES if n not in used),
                        f"对手{len(self.rivals)+1}")
        r = Rival(name, pathway_key, start_level=start_level, aggression=aggression)
        self.rivals.append(r)
        return r

    def tick(self, steps=1):
        logs = []
        for _ in range(steps):
            self.tick_count += 1
            for r in self.rivals:
                r.advance_one_tick(rng=self.rng, logs=logs)
        return logs

    def status(self):
        return [r.snapshot() for r in self.rivals]

    def count(self):
        return len(self.rivals)

    def to_dict(self):
        return {
            # Random 不可序列化：落盘后由 from_dict 重建为无种子实例
            "rivals": [r.to_dict() for r in self.rivals],
            "tick_count": self.tick_count,
        }

    @classmethod
    def from_dict(cls, d):
        rivals = [Rival.from_dict(rd) for rd in d.get("rivals", [])]
        sys = cls(rivals=rivals, tick_count=d.get("tick_count", 0))
        # 读档后让已「宣示权柄」的对手重新占用空闲槽位
        # （若玩家已持有则跳过，不掠夺）
        for r in rivals:
            if r._claimed:
                r._try_claim_authority([])
        return sys
