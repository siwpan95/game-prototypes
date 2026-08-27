# lore.py
# 主题沉浸包装（E10）——「灰雾之上」源堡框架的考据文案库。
#
# 纯数据模块：为每条途径 / 序列组提供一句考据（设定向的文本），
# 供 character_view 等面板以「考据」形式呈现，强化诡秘之主的神秘学氛围。
# 不依赖 tkinter，可被无头单测覆盖。
from pathways_data import PATHWAYS, PATHWAY_GROUPS, get_pathway


# 每条途径一句考据（灰雾之上的低语）
PATHWAY_LORE = {
    "fool":            "愚者途径源出源堡，是「诡秘之主」权柄的根基；占卜、欺诈与巧合皆为其表。",
    "error":           "错误途径亲近「门」与「愚者」，偷盗者在巧合中窃取命运的一角。",
    "door":            "门途径掌握空间与灵界，学徒终将推开那扇不属于此世的大门。",
    "tyrant":          "暴君途径源自「空想之龙」，风暴与海洋在序列之上咆哮。",
    "hanged_man":      "倒吊人途径亲近太阳与暴君，于痛苦与束缚中窥见知识与秩序。",
    "visionary":       "空想家途径由「空想之龙」分化，以精神与想象扭曲现实。",
    "white_tower":     "白塔途径崇尚知识与智慧，祈祷者以纯粹理智丈量神秘。",
    "sun":             "太阳途径是暴君的对立面，歌颂者以光明驱散隐匿的阴霾。",
    "darkness":        "黑暗途径与「永恒之暗」同源，不眠者在长夜中守候禁忌。",
    "eternal_sleeper": "永眠者途径向「永恒之暗」沉坠，于沉睡中承接衰败与终结。",
    "dusk_giant":      "黄昏巨人途径执掌衰败与力量，巨人在落日中举起火把。",
    "bound_one":       "束缚者途径源自「永恒之暗」，以封印与禁锢镇压失控的权柄。",
    "abyss":           "深渊途径与「堕落母神」相连，罪犯在欲望中折翼成堕天使。",
    "hermit":          "隐者途径亲近「知识之妖」，学者以信息与诡辩编织网络。",
    "paragon":         "完美者途径源自「知识之妖」，工匠以技艺逼近完美之境。",
    "mother":          "母亲途径与「堕落母神」同源，耕种者在丰饶与腐朽间轮回。",
    "moon":            "月亮途径是母神的倒影，药师于变异中孕育美与畸变。",
    "judge":           "审判者途径源自「上帝」，以律法与平衡裁决罪与罚。",
    "black_emperor":   "黑皇帝途径出自「上帝」，以律法与领土构筑秩序的王座。",
    "red_priest":      "红祭司途径源自「上帝」，猎人在战争中点燃铁与血。",
    "chaos_witch":     "混沌魔女途径与黑暗相连，于混乱中孕育恶作剧与新生。",
    "wheel_of_fortune": "命运之轮途径亲近「命运女神」，于变动中拨弄机运的丝线。",
}


# 序列组考据（权柄体系层面的沉浸文案）
GROUP_LORE = {
    gk: (f"{g['name']}：{g.get('description', '')}")
    for gk, g in PATHWAY_GROUPS.items()
}


def pathway_lore(pathway_key: str) -> str:
    """返回某途径的考据文案（未知途径回退为通用提示）。"""
    if pathway_key in PATHWAY_LORE:
        return PATHWAY_LORE[pathway_key]
    p = get_pathway(pathway_key) if pathway_key in PATHWAYS else None
    return f"{p['name']}途径的奥秘散落在亵渎石板之外，尚需你亲自揭开。" if p else "未知途径。"


def group_lore(pathway_key: str) -> str:
    """返回某途径所属权柄体系的考据文案。"""
    p = get_pathway(pathway_key) if pathway_key in PATHWAYS else None
    if not p:
        return ""
    return GROUP_LORE.get(p["group"], "")
