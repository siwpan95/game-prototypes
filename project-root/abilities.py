# abilities.py
# E6 能力效果化（Ability Effects）
#
# 设计哲学：
#   角色的 abilities 仍是一串「能力名字符串」（便于随角色 to_dict 序列化），
#   本模块维护一张 ABILITY_EFFECTS 注册表（名字 → 效果描述）。
#   事件结算（events.resolve_choice）末尾按角色所拥有的能力名查表，
#   把「只是字符串」的能力变成「会在事件中真正产生差异的效果」。
#
# 效果字段（均为可选）：
#   san_relief      float  事件结算时安抚理智（恢复若干 SAN，封顶 100）
#   bonus_material  str    事件结算时额外获得一份该材料（与 E1 库存联动）
#   clue            bool   事件结算时揭示一条隐秘线索（纯叙事/情报）
#   desc            str    风味描述，用于角色面板展示
#
# 纯逻辑模块，不依赖 tkinter，可被无头单测直接覆盖。
ABILITY_EFFECTS = {
    "占卜": {
        "san_relief": 10.0,
        "bonus_material": "命运丝线",
        "clue": True,
        "desc": "窥见命运丝线：事件结算时安抚理智，并揭示隐秘线索",
    },
    "观众": {
        "san_relief": 5.0,
        "bonus_material": "情绪标本",
        "desc": "洞察他人情绪：更易取得额外材料，并稍缓理智流失",
    },
    "阅读者": {
        "san_relief": 8.0,
        "clue": True,
        "desc": "通读万物：从事件文本中读出被掩藏的真相",
    },
    "神秘学家": {
        "san_relief": 12.0,
        "desc": "神秘学造诣：危险面前精神更稳，理智流失更少",
    },
    "考古学家": {
        "bonus_material": "古代遗物",
        "clue": True,
        "desc": "发掘尘封：事件中常有意外的材料与线索入账",
    },
    "聆听": {
        "san_relief": 6.0,
        "clue": True,
        "desc": "聆听虚空低语：提前察觉异常，获得线索",
    },
}


def ability_desc(name: str):
    """返回能力的风味描述；无名则 None。"""
    e = ABILITY_EFFECTS.get(name)
    return e["desc"] if e else None


def has_effect(name: str) -> bool:
    """该能力是否在结算中真正拥有可调用效果。"""
    return name in ABILITY_EFFECTS


def effective_abilities(character) -> list:
    """返回角色所拥有、且具效果的能力 [(name, desc), ...]。"""
    out = []
    for name in getattr(character, "abilities", []) or []:
        d = ability_desc(name)
        if d:
            out.append((name, d))
    return out


def apply_ability_effects(character, state, logs: list):
    """在事件结算末尾调用：遍历角色能力，应用其在 ABILITY_EFFECTS 中的效果。

    副作用直接作用于 character（理智）与 state（库存），并把产生的行为
    追加到 logs（供 GUI 日志呈现）。
    """
    for name in getattr(character, "abilities", []) or []:
        e = ABILITY_EFFECTS.get(name)
        if not e:
            continue
        if e.get("san_relief"):
            before = character.pollution.san
            character.pollution.recover(e["san_relief"])
            gained = character.pollution.san - before
            if gained > 0:
                logs.append(f"   🜂 能力〔{name}〕：理智 +{gained:.0f}（{character.pollution.san_status()}）")
        if e.get("bonus_material"):
            state.inventory.add(e["bonus_material"], 1)
            logs.append(f"   🜂 能力〔{name}〕：获得额外材料「{e['bonus_material']}」")
        if e.get("clue"):
            logs.append(f"   🔍 能力〔{name}〕：窥见一条隐秘线索")
