# achievements.py
# 成就 / 图鉴 / 多结局系统（E9）
#
# 纯逻辑模块，不依赖 tkinter。与 state（GUIState 或 types.SimpleNamespace）协作：
#   state.character       当前角色（Sequence 或 None）
#   state.old_one_info    晋升旧日摘要（dict 或 None）
#   state.factions        阵营声望 dict
#   state.seen_events     已遭遇事件标题集合
#   state.event_log       事件日志 list
#   state.achievements    AchievementSystem 实例
#   state.codex           CodexSystem 实例
#   state.rival_system    RivalSystem 实例或 None
#
# 与 E4/E11 的 GameSession 序列化兼容：AchievementSystem / CodexSystem 均提供
# to_dict / from_dict。
from pathways_data import PATHWAYS
from uniqueness import Uniqueness


# ───────────────────────── 成就注册表 ─────────────────────────
# 每个成就：{name, icon, desc, check(state)->bool}
ACHIEVEMENTS = {}

def _reg(key, name, icon, desc, check):
    ACHIEVEMENTS[key] = {"name": name, "icon": icon, "desc": desc, "check": check}


_reg("first_step",     "第一步",     "👣", "执行过第一次扮演行为",
     lambda s: bool(s.character and s.character.digestion_actions))
_reg("first_ascend",   "初次晋升",   "⬆", "将序列推进过序列9",
     lambda s: bool(s.character and s.character.LEVEL < 9))
_reg("true_god",       "真神登临",   "👑", "成为某途径序列0真神",
     lambda s: bool(s.character and s.character.LEVEL == 0))
_reg("old_one",        "旧日归来",   "🌟", "聚合权柄，晋升旧日",
     lambda s: bool(s.old_one_info))
_reg("first_loss",     "第一次失控", "💀", "污染达到失控等级",
     lambda s: bool(s.character and s.character.pollution.is_lost))
_reg("first_event",    "命运交汇",   "🎲", "遭遇过至少一次随机事件",
     lambda s: bool(getattr(s, "seen_events", None)))
_reg("full_digest",    "完美消化",   "✅", "将某一序列消化至 100%",
     lambda s: bool(s.character and s.character.required_actions and s.character.digested))
_reg("faction_friend", "塔罗会挚友", "🤝", "任一阵营声望 ≥ 50",
     lambda s: bool(any(v >= 50 for v in (s.factions or {}).values())))
_reg("collector",      "权柄收藏家", "🔑", "集齐全部 22 途径唯一性",
     lambda s: _owns_all_uniqueness(s.character) if s.character else False)
_reg("rivals_rise",    "群雄并起",   "⚔", "存在对手且至少一名推进到序列≤3",
     lambda s: bool(s.rival_system and any(r.character.LEVEL <= 3
                                           for r in s.rival_system.rivals)))


def _owns_all_uniqueness(character):
    for pk, p in PATHWAYS.items():
        u = Uniqueness.get_or_create(f"{p['name']}唯一性", pk)
        if u.owner is not character:
            return False
    return True


def state_tick_marker(state):
    """为成就解锁记录一个轻量标记（优先用 rival_system.tick_count，否则用日志条数）。"""
    try:
        if getattr(state, "rival_system", None) is not None:
            return state.rival_system.tick_count
        return len(getattr(state, "event_log", []) or [])
    except Exception:
        return 0


class AchievementSystem:
    """已解锁成就的集合与评估逻辑。"""

    def __init__(self, unlocked=None, unlocked_at=None):
        self.unlocked = set(unlocked or [])
        self.unlocked_at = dict(unlocked_at or {})

    def evaluate(self, state):
        """评估并解锁满足条件的成就，返回本次新解锁的 key 列表。"""
        newly = []
        for key, meta in ACHIEVEMENTS.items():
            if key in self.unlocked:
                continue
            try:
                if meta["check"](state):
                    self.unlocked.add(key)
                    self.unlocked_at[key] = state_tick_marker(state)
                    newly.append(key)
            except Exception:
                # 单个成就判定失败不应阻断整体
                pass
        return newly

    def is_unlocked(self, key):
        return key in self.unlocked

    def progress(self):
        return len(self.unlocked), len(ACHIEVEMENTS)

    def to_dict(self):
        return {"unlocked": sorted(self.unlocked), "unlocked_at": self.unlocked_at}

    @classmethod
    def from_dict(cls, d):
        return cls(unlocked=d.get("unlocked", []), unlocked_at=d.get("unlocked_at", {}))


# ───────────────────────── 图鉴系统 ─────────────────────────
class CodexSystem:
    """收集已见序列 / 能力 / 事件 / 阵营的进度。"""

    def __init__(self, sequences=None, abilities=None, events=None, factions=None):
        self.sequences = set(sequences or [])   # "pathway_key:level"
        self.abilities = set(abilities or [])
        self.events = set(events or [])
        self.factions = set(factions or [])

    def see_sequence(self, pathway_key, level):
        self.sequences.add(f"{pathway_key}:{level}")

    def see_ability(self, name):
        if name:
            self.abilities.add(name)

    def see_event(self, title):
        if title:
            self.events.add(title)

    def see_faction(self, key):
        if key:
            self.factions.add(key)

    def sequence_progress(self):
        total = sum(len(PATHWAYS[pk]["sequences"]) for pk in PATHWAYS)
        return len(self.sequences), total

    def to_dict(self):
        return {
            "sequences": sorted(self.sequences),
            "abilities": sorted(self.abilities),
            "events": sorted(self.events),
            "factions": sorted(self.factions),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(sequences=d.get("sequences", []), abilities=d.get("abilities", []),
                   events=d.get("events", []), factions=d.get("factions", []))


def record_codex(state):
    """根据当前 state 刷新图鉴（已见序列/能力/事件/阵营）。"""
    codex = getattr(state, "codex", None)
    if codex is None:
        return
    ch = state.character
    if ch is not None:
        codex.see_sequence(ch.PATHWAY_KEY, ch.LEVEL)
        for ab in ch.abilities:
            codex.see_ability(ab)
    for fk in (state.factions or {}):
        codex.see_faction(fk)
    for title in (getattr(state, "seen_events", None) or set()):
        codex.see_event(title)


def evaluate_achievements(state):
    """评估成就；返回新解锁成就的展示名列表。"""
    ach = getattr(state, "achievements", None)
    if ach is None:
        return []
    new_keys = ach.evaluate(state)
    return [ACHIEVEMENTS[k]["name"] for k in new_keys]


# ───────────────────────── 多结局判定 ─────────────────────────
ENDINGS = {
    "loss":     ("失控沉沦", "你在不可名状的低语中迷失了自我，人性被彻底吞噬。"),
    "old_one":  ("旧日归来", "你聚合了权柄体系的唯一性与源质，登临旧日之位。"),
    "true_god": ("真神登临", "你执掌一条途径的唯一性，成为执掌权柄的真神。"),
    "high":     ("高序列圣者", "你已触及天使位格，俯瞰凡尘的纷争。"),
    "wanderer": ("旅途未竟", "你的故事仍在继续，前路尚远。"),
}


def evaluate_ending(state):
    """根据当前 state 判定当前结局走向，返回 (key, title, text)。"""
    ch = state.character
    if ch is not None and ch.pollution.is_lost:
        return ("loss",) + ENDINGS["loss"]
    if state.old_one_info:
        return ("old_one",) + ENDINGS["old_one"]
    if ch is not None and ch.LEVEL == 0:
        return ("true_god",) + ENDINGS["true_god"]
    if ch is not None and ch.LEVEL <= 3:
        return ("high",) + ENDINGS["high"]
    return ("wanderer",) + ENDINGS["wanderer"]
