"""
Language pack for Russian Roulette.
zh = Chinese (default), en = English.
All UI strings live here — main.py calls L("key") to get the current lang text.
"""

_current = "zh"

STRINGS = {
    # ── Window ───────────────────────────────────────────────
    "title": {
        "zh": "俄 罗 斯 轮 盘 赌  ——  3D6 决 策 版",
        "en": "Russian Roulette  —  3D6 Edition",
    },
    "caption": {
        "zh": "俄罗斯轮盘赌 - ECS版",
        "en": "Russian Roulette - ECS Edition",
    },

    # ── Phase names ───────────────────────────────────────────
    "phase_START":        {"zh": "主菜单",   "en": "Main Menu"},
    "phase_PLAYER_TURN":  {"zh": "你的回合", "en": "Your Turn"},
    "phase_ROLL1_DONE":   {"zh": "请丢第二颗骰子", "en": "Roll 2nd Die?"},
    "phase_END_TURN":     {"zh": "回合结束...", "en": "Turn ending..."},
    "phase_GAME_OVER":    {"zh": "游戏结束", "en": "Game Over"},

    # ── Labels ───────────────────────────────────────────────
    "phase_label":    {"zh": "阶段：", "en": "Phase: "},
    "turn_label":     {"zh": "回合：", "en": "Turn: "},
    "your_chamber":   {"zh": "你的弹巢", "en": "Your Chamber"},
    "opp_chamber":    {"zh": "乙方弹巢", "en": "B Chamber"},
    "msg_log":        {"zh": "消息记录", "en": "Message Log"},
    "bullet_live":    {"zh": "实",     "en": "L"},
    "bullet_blank":   {"zh": "空",     "en": "B"},
    "bullet_rubber":  {"zh": "胶",     "en": "R"},  # 橡胶弹
    "bullet_incendiary": {"zh": "燃",  "en": "I"},  # 燃烧弹
    "chamber_refill":  {"zh": "弹巢",  "en": "Chamber"},

    # ── Characters ───────────────────────────────────────────
    "char_player":    {"zh": "甲方",   "en": "Player A"},
    "char_opponent":  {"zh": "乙方",   "en": "Player B"},
    "hp_alive":       {"zh": "♥ HP: {hp}/3",  "en": "HP: {hp}/3"},
    "hp_dead":        {"zh": "✝ 死亡",   "en": "DEAD"},

    # ── Buttons ──────────────────────────────────────────────
    "btn_start":      {"zh": "开始游戏",       "en": "Start Game"},
    "btn_roll1":      {"zh": "丢骰子",        "en": "Roll Dice"},
    "btn_spin":       {"zh": "旋转弹巢",       "en": "Spin Chamber"},
    "btn_roll2":      {"zh": "丢骰子(第二颗)", "en": "Roll 2nd Die"},
    "btn_cancel":     {"zh": "取消",          "en": "Cancel"},
    "btn_restart":    {"zh": "再来一局",       "en": "Play Again"},
    "btn_lang":       {"zh": "EN",            "en": "中文"},

    # ── Messages ─────────────────────────────────────────────
    "msg_new_game":       {"zh": "=== 新游戏开始 ===",              "en": "=== New Game ==="},
    "msg_turn1":          {"zh": "第1回合：甲方先手",              "en": "Turn 1: A goes first"},
    "msg_chamber_info":   {"zh": "你的弹巢：{live}实 / {blank}空","en": "Chamber: {live} live / {blank} blank"},
    "msg_your_roll1":     {"zh": "你丢骰1(行动): {dice} → {total} [{label}]",
                           "en": "Your Roll 1(ACTION): {dice} -> {total} [{label}]"},
    "msg_roll1_spin":     {"zh": "旋转弹巢... 回合结束",    "en": "Spin chamber... turn ends"},
    "msg_roll1_shoot":    {"zh": "决定开枪！丢第二颗骰子决定射击目标",
                           "en": "Decided to shoot! Roll 2nd die for target"},
    "msg_roll1_precise":  {"zh": "精准射击！下一发必中实弹且不消耗！",
                           "en": "Precise shot! Next shot guaranteed live and free!"},
    "msg_your_roll2":     {"zh": "你丢骰2(目标): {dice} → {total} [{target_label}]",
                           "en": "Your Roll 2(TARGET): {dice} -> {total} [{target_label}]"},
    "msg_target_self":    {"zh": "朝自己", "en": "self"},
    "msg_target_opponent": {"zh": "朝对手", "en": "opponent"},
    "msg_opponent_target_self":   {"zh": "朝甲方", "en": "at A"},
    "msg_opponent_target_opponent": {"zh": "朝乙方", "en": "at B"},
    "msg_explosion":      {"zh": "💥 炸膛！大失败导致枪支爆炸！",  "en": "BOOM! Critical fail caused explosion!"},
    "msg_shoot":          {"zh": "{shooter}扣扳机... [{bullet}] → 朝{target}开枪！",
                           "en": "{shooter} pulls trigger... [{bullet}] -> shoots {target}!"},
    "msg_killed":         {"zh": "💀 {name} 被击杀！",           "en": "{name} is dead!"},
    "msg_refill":         {"zh": "弹巢补充1发 → {live}实 / {blank}空",
                           "en": "Refilled 1 -> {live} live / {blank} blank"},
    "msg_empty_chamber":  {"zh": "弹巢已空！",                    "en": "Chamber is empty!"},
    "msg_bang":           {"zh": "砰！",                         "en": "BANG!"},
    "msg_click":          {"zh": "咔！",                         "en": "Click!"},
    "msg_rubber_hit":     {"zh": "橡胶弹命中！{name}被眩晕，下回合无法行动",
                           "en": "Rubber bullet! {name} is stunned, can't act next turn"},
    "msg_incendiary_hit": {"zh": "燃烧弹命中！{name}被点燃，受到持续伤害",
                           "en": "Incendiary bullet! {name} is burning, taking damage over time"},
    "msg_blank_effect":   {"zh": "空包弹！{name}受到惊吓，但无大碍",
                           "en": "Blank! {name} is startled, but unharmed"},
    "msg_precise_no_bullet": {"zh": "精准射击生效！但是弹巢空了！",
                           "en": "Precise shot! But chamber is empty!"},
    "msg_explosion_kill": {"zh": "💥 {name} 炸膛死亡！",
                           "en": "{name} EXPLODED!"},
    "msg_opp_turn":       {"zh": "--- 乙方回合 ---",             "en": "--- Player B's Turn ---"},
    "msg_opp_roll1":      {"zh": "乙方丢骰1(行动): {dice} → {total} [{label}]",
                           "en": "B Roll 1(ACTION): {dice} -> {total} [{label}]"},
    "msg_opp_spin":       {"zh": "乙方旋转弹巢... 回合结束",    "en": "B spins... turn ends"},
    "msg_opp_roll2":      {"zh": "乙方丢骰2(目标): {dice} → {total} [{target_label}]",
                           "en": "B Roll 2(TARGET): {dice} -> {total} [{target_label}]"},
    "msg_opp_explosion":  {"zh": "💥 乙方炸膛！",               "en": "BOOM! B exploded!"},
    "msg_opp_precise":    {"zh": "乙方精准射击！",              "en": "B's precise shot!"},
    "msg_spin":           {"zh": "你旋转了弹巢... 回合结束",    "en": "You spin the chamber... turn ends"},
    "msg_you_win":        {"zh": "=== 你赢了！{detail} ===",    "en": "=== You Win! {detail} ==="},
    "msg_you_lose":       {"zh": "=== 你输了！{detail} ===",    "en": "=== You Lose! {detail} ==="},
    "detail_killed_opp":  {"zh": "对手被击杀",                  "en": "Opponent killed"},
    "detail_killed_self": {"zh": "你被击杀",                    "en": "You got killed"},
    "detail_explosion":   {"zh": "炸膛",                        "en": "Gun exploded"},
    "detail_burning":     {"zh": "燃烧伤害",                    "en": "Burn damage"},
    "detail_rubber":      {"zh": "橡胶弹眩晕",                  "en": "Rubber bullet stun"},
    "detail_burning":     {"zh": "燃烧伤害",                    "en": "Burn damage"},
    "detail_blank_skip":  {"zh": "空包弹跳过",                  "en": "Blank skip"},
    "msg_next_turn":      {"zh": "--- 第{n}回合：甲方回合 ---", "en": "--- Turn {n}: A's Turn ---"},
    "msg_stunned_skip":   {"zh": "{name} 处于眩晕状态，跳过回合", "en": "{name} is stunned, skipping turn"},

    # ── Achievement popup ────────────────────────────────────
    "ach_unlocked":   {"zh": "成就解锁：{name}！", "en": "Achievement: {name}!"},
    "btn_achievement": {"zh": "成就", "en": "Ach"},
    "ach_title":       {"zh": "已解锁成就", "en": "Unlocked Achievements"},
    "ach_progress":   {"zh": "进度：{unlocked}/{total}", "en": "Progress: {unlocked}/{total}"},
    "ach_none":        {"zh": "还没有解锁任何成就", "en": "No achievements unlocked yet"},
    "ach_close":       {"zh": "关闭", "en": "Close"},

    # ── Dice labels ──────────────────────────────────────────
    "dice_success":        {"zh": "success",  "en": "success"},
    "dice_critical_fail":  {"zh": "critical_fail", "en": "critical_fail"},
    "dice_fail":           {"zh": "fail",     "en": "fail"},
    "dice_critical_success":{"zh": "critical_success", "en": "critical_success"},
    "dice_result_prefix":  {"zh": "→ ",       "en": "-> "},
    "dice_decision_roll1": {"zh": "3=炸膛 4-7=旋转 8-17=开枪 18=精准", "en": "3=BOOM 4-7=Spin 8-17=Shoot 18=Precise"},
    "dice_decision_roll2": {"zh": "射击目标: ", "en": "Target: "},
    "target_self":         {"zh": "自己", "en": "Self"},
    "target_opponent":     {"zh": "对手", "en": "Opp"},
}


def set_lang(lang: str):
    global _current
    if lang in ("zh", "en"):
        _current = lang


def get_lang() -> str:
    return _current


def toggle_lang():
    global _current
    _current = "en" if _current == "zh" else "zh"


def L(key: str, **kwargs) -> str:
    """Get localized string. Supports .format() kwargs."""
    entry = STRINGS.get(key)
    if entry is None:
        return f"[?{key}]"
    text = entry.get(_current, entry.get("zh", f"[?{key}]"))
    if kwargs:
        text = text.format(**kwargs)
    return text


def L_bullet(bullet_type) -> str:
    """Localized bullet name."""
    if bullet_type == 1:
        return L("bullet_live")
    elif bullet_type == 2:
        return L("bullet_rubber")
    elif bullet_type == 3:
        return L("bullet_incendiary")
    else:
        return L("bullet_blank")


def L_target(target: str) -> str:
    """根据target返回对应的角色名称"""
    return L("char_player") if target == "self" else L("char_opponent")
