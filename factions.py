# factions.py
# E7 组织 / 阵营 / 塔罗会社交层（Faction & Tarot Social）
#
# 阵营声望存于 GUIState.factions（纯 dict：faction_key -> reputation int），
# 这样可随 GameSession 直接序列化（与 E4 兼容，无需额外处理）。
#
# 本模块提供：
#   - FACTIONS   阵营元信息（名称 / 描述 / 配色）
#   - ACTIONS    可执行的社交动作（消耗声望，对 state 产生效果）
#   - FactionSystem  操作声望 dict 的包装类（含 do_action）
#   - grant_reputation(state, key, delta)  供 events.py 在事件结算里提升声望
#
# 纯逻辑模块，不依赖 tkinter，可被无头单测直接覆盖。
FACTIONS = {
    "tarot": {
        "label": "塔罗会",
        "desc": "灰雾之上的命运聚会，以声望换取非凡材料与隐秘情报。",
        "color": "#8b5cf6",   # 紫罗兰（神秘学）
    },
    "church": {
        "label": "教会",
        "desc": "正神的牧养者，可借净化仪式抚平理智的裂痕。",
        "color": "#3b82f6",   # 蓝
    },
    "secret": {
        "label": "隐秘组织",
        "desc": "盘根错节的暗处同盟，能加固你的人性之锚。",
        "color": "#e05a33",   # 暗红
    },
}

# 社交动作：消耗阵营声望，对 state 产生效果。
# effect 类型在 do_action 内按 action_key 分支处理（不把函数存进常量，便于序列化无关）。
ACTIONS = {
    "tarot_exchange": {
        "label": "以声望换取材料", "faction": "tarot", "cost": 10,
        "desc": "塔罗会赠予一份你晋升所需的缺失材料。",
    },
    "church_purify": {
        "label": "教会净化仪式", "faction": "church", "cost": 10,
        "desc": "在圣堂中涤荡低语，恢复 30 点理智。",
    },
    "secret_anchor": {
        "label": "隐秘组织加持", "faction": "secret", "cost": 10,
        "desc": "暗处同盟为你的人性之锚注入力量（+15 人性）。",
    },
}

DEFAULT_REP = 0


def grant_reputation(state, faction_key: str, delta: int):
    """供事件结算调用：提升某阵营声望。"""
    state.factions[faction_key] = state.factions.get(faction_key, DEFAULT_REP) + delta


class FactionSystem:
    """操作阵营声望 dict 的轻量包装（不侵入 state，可被重新赋值回去）。"""

    def __init__(self, data: dict = None):
        self.data = dict(data) if data else {}

    def reputation(self, key: str) -> int:
        return self.data.get(key, DEFAULT_REP)

    def earn(self, key: str, delta: int):
        self.data[key] = self.reputation(key) + delta

    def can_afford(self, action_key: str) -> bool:
        a = ACTIONS[action_key]
        return self.reputation(a["faction"]) >= a["cost"]

    def to_dict(self) -> dict:
        return dict(self.data)

    def do_action(self, state, action_key: str) -> list:
        """执行社交动作，返回日志行列表（副作用已应用到 state）。"""
        a = ACTIONS[action_key]
        fk = a["faction"]
        rep = self.reputation(fk)
        logs = []
        if rep < a["cost"]:
            logs.append(f"   ⚠ 在「{FACTIONS[fk]['label']}」声望不足（{rep}/{a['cost']}），"
                        f"无法执行「{a['label']}」")
            return logs

        self.data[fk] = rep - a["cost"]

        if action_key == "tarot_exchange":
            ch = state.character
            if ch and ch.LEVEL > 0:
                from pathways_data import get_potion_formula
                formula = get_potion_formula(ch.PATHWAY_KEY, ch.LEVEL - 1)
                miss = [m for m in [formula["main"]] + formula["supplementary"]
                        if state.inventory.count(m) < 1]
                mat = miss[0] if miss else formula["main"]
                state.inventory.add(mat, 1)
                logs.append(f"   🜂 塔罗会馈赠：获得材料「{mat}」（声望 -{a['cost']}）")
            else:
                logs.append("   🜂 塔罗会馈赠：你已立于序列之巅，无需材料（声望 -%d）" % a["cost"])

        elif action_key == "church_purify":
            ch = state.character
            if ch:
                before = ch.pollution.san
                ch.pollution.recover(30.0)
                logs.append(f"   🜂 教会净化：理智 {before:.0f} → {ch.pollution.san:.0f}"
                            f"（声望 -{a['cost']}）")
            else:
                logs.append("   🜂 教会净化：无角色，仪式落空")

        elif action_key == "secret_anchor":
            ch = state.character
            if ch and ch.anchor:
                ch.anchor.humanity = min(100.0, ch.anchor.humanity + 15.0)
                logs.append(f"   🜂 隐秘组织加持：人性之锚 +15 → {ch.anchor.humanity:.0f}"
                            f"（声望 -{a['cost']}）")
            elif ch:
                logs.append("   🜂 隐秘组织加持：你尚无人性之锚（请先建立锚）")
            else:
                logs.append("   🜂 隐秘组织加持：无角色，加持落空")

        return logs
