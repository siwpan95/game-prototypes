# pathway_groups.py
# 途径组体系 —— 互换规则、旧日等级、权柄架构
from pathways_data import (
    PATHWAYS, PATHWAY_GROUPS,
    get_pathway, get_compatible_pathways, get_interchange_at,
    get_sequence_data, will_gender_change, get_gender_change_message,
)
from pollution import SequenceError
from uniqueness import Uniqueness, SequenceOneCharacteristic

# ============================================================
# 旧日等级体系
# ============================================================
class OldOneTier:
    """旧日位阶"""
    NORMAL = "普通旧日"
    HALF_PILLAR = "半支柱旧日"
    PILLAR = "支柱级旧日"

# 四支柱定义
FOUR_PILLARS = {
    "god_almighty": {
        "name": "上帝、创造者、造物主、全知全能者、星界之主",
        "core_source_quality": "混沌海",
        "group": "god_almighty",
    },
    "lord_of_mysteries": {
        "name": "诡秘之主、时空之王、命运道标、源堡化身、灵界支配者",
        "core_source_quality": "源堡",
        "group": "lord_of_mysteries",
    },
    "fallen_mother": {
        "name": "堕落母神、邪恶之始、不灭者、污秽的母巢",
        "core_source_quality": "未知源质",
        "group": "root_god",
    },
    "eternal_darkness": {
        "name": "永恒之暗、万物奇点、时空归一者",
        "core_source_quality": "永暗之河与灾祸之城",
        "group": "eternal_darkness",
    },
}

# ============================================================
# 途径互换核心逻辑
# ============================================================

class PathwaySwitchValidator:
    """途径切换验证器"""

    @staticmethod
    def can_switch(from_pathway: str, to_pathway: str, current_level: int) -> tuple[bool, str]:
        """
        检查是否可以在两条途径间切换
        返回 (是否可切换, 原因说明)
        """
        if from_pathway not in PATHWAYS:
            return False, f"未知途径: {from_pathway}"
        if to_pathway not in PATHWAYS:
            return False, f"未知途径: {to_pathway}"
        if from_pathway == to_pathway:
            return False, "不能切换到相同途径"

        from_pathway_data = get_pathway(from_pathway)
        to_pathway_data = get_pathway(to_pathway)
        from_group = from_pathway_data["group"]
        to_group = to_pathway_data["group"]

        # 必须是同一途径组
        if from_group != to_group:
            # 特殊例外：黑暗途径可转混沌魔女
            if from_pathway == "darkness" and to_pathway == "chaos_witch":
                pass  # 允许
            else:
                return False, f"{from_pathway_data['name']}途径({PATHWAY_GROUPS[from_group]['name']})与{to_pathway_data['name']}途径({PATHWAY_GROUPS[to_group]['name']})不属于同一途径组"

        # 检查当前等级是否达到互换要求
        interchange_at = get_interchange_at(from_pathway)
        if interchange_at is None:
            return False, f"{from_pathway_data['name']}途径不支持互换"

        if current_level > interchange_at:
            return False, f"当前序列等级({current_level})低于互换要求(序列{interchange_at})"

        return True, f"可在{from_pathway_data['name']}途径序列{current_level}切换至{to_pathway_data['name']}途径"

    @staticmethod
    def get_switch_target_level(from_pathway: str, to_pathway: str, from_level: int) -> int | None:
        """获取切换后的目标等级（通常同级切换）"""
        valid, _ = PathwaySwitchValidator.can_switch(from_pathway, to_pathway, from_level)
        if not valid:
            return None
        # 同级切换
        return from_level


class OldOnePath:
    """旧日晋升路径计算"""

    @staticmethod
    def required_for_old_one(group_key: str) -> dict:
        """
        计算晋升旧日所需的条件
        返回 {uniqueities, sequence_1_characteristics, source_quality}
        """
        if group_key not in PATHWAY_GROUPS:
            raise KeyError(f"未知途径组: {group_key}")

        group = PATHWAY_GROUPS[group_key]
        pathway_keys = group["pathways"]

        required = {
            "pathways": [PATHWAYS[k]["name"] for k in pathway_keys],
            "source_quality": group["source_quality"],
            "sequence_0": [f"{PATHWAYS[k]['name']}序列0唯一性" for k in pathway_keys],
            "sequence_1": [],
            "note": group["description"],
        }

        # 收集所有需要的序列1非凡特性
        for pk in pathway_keys:
            pathway = PATHWAYS[pk]
            seq1 = get_sequence_data(pk, 1)
            required["sequence_1"].append(f"{pathway['name']}途径：{seq1['name']}非凡特性（共3份，需要全部）")

        return required

    @staticmethod
    def pillar_requirements(pillar_key: str) -> dict:
        """计算支柱级旧日所需条件"""
        if pillar_key not in FOUR_PILLARS:
            raise KeyError(f"未知支柱: {pillar_key}")
        pillar = FOUR_PILLARS[pillar_key]
        old_one_req = OldOnePath.required_for_old_one(pillar["group"])
        old_one_req["pillar_name"] = pillar["name"]
        old_one_req["tier"] = OldOneTier.PILLAR
        return old_one_req


# ============================================================
# 序列等级描述
# ============================================================

LEVEL_DESCRIPTIONS = {
    (9, 8): "低序列 —— 拥有些许超越常人的奇异能力与灵性灵感",
    (7, 6, 5): "中序列 —— 经验丰富，能处理小范围非凡事件，灵感灵性接近人类巅峰",
    (4, 3): "高序列/圣者 —— 不完整的神话生物，展现神话形态可致目视者混乱崩溃",
    (2, 1): "天使 —— 完整神话生物，掌握部分神灵权柄，能粉碎非凡特性祛除污染",
    (0,): "真神 —— 神灵位阶，拥有本途径不可撼动的影响力与权柄掌控力",
}

def get_level_description(level: int) -> str:
    """获取序列等级的文字描述"""
    for levels, desc in LEVEL_DESCRIPTIONS.items():
        if level in levels:
            return desc
    return "超越序列 —— 旧日位阶"


# ============================================================
# 封印物等级
# ============================================================
SEALED_ARTIFACT_LEVELS = {
    3: {"name": "3级封印物", "corresponds": "低序列", "description": "拥有对应序列部分能力，负面效果易抵御"},
    2: {"name": "2级封印物", "corresponds": "中序列", "description": "需一定方法规避负面效果"},
    1: {"name": "1级封印物", "corresponds": "圣者", "description": "拥有多项半神能力，负面效果恐怖，需规范使用和制衡保存"},
    0: {"name": "0级封印物", "corresponds": "天使及以上", "description": "拥有几乎全部神话生物能力，许多有灵智，半神以下不可打听不可知晓"},
}


def sealed_artifact_level(sequence_level: int) -> dict:
    """根据序列等级返回对应的封印物等级信息（接入 SEALED_ARTIFACT_LEVELS）"""
    if sequence_level >= 7:
        return SEALED_ARTIFACT_LEVELS[3]
    if sequence_level >= 5:
        return SEALED_ARTIFACT_LEVELS[2]
    if sequence_level >= 3:
        return SEALED_ARTIFACT_LEVELS[1]
    return SEALED_ARTIFACT_LEVELS[0]


def promote_to_old_one(group_key: str, character) -> dict:
    """
    晋升旧日：聚合途径组内所有途径的唯一性 + 3 份序列1非凡特性到同一持有者。

    参数:
        group_key: 途径组 key（如 "lord_of_mysteries"）
        character: 已晋升到序列0、且属于该组的非凡者

    返回:
        旧日构成摘要 dict

    异常:
        KeyError    未知途径组
        SequenceError  角色不属于该组 / 尚未达到序列0
        RuntimeError   唯一性或序列1特性已被他人持有（权柄争夺）
    """
    if group_key not in PATHWAY_GROUPS:
        raise KeyError(f"未知途径组: {group_key}")
    group = PATHWAY_GROUPS[group_key]
    if character.PATHWAY_KEY not in group["pathways"]:
        raise SequenceError(f"角色不属于途径组「{group['name']}」，无法晋升该旧日")
    if character.LEVEL != 0:
        raise SequenceError(f"晋升旧日需先成为序列0真神（当前序列{character.LEVEL}）")

    composition = {
        "group": group["name"],
        "owner": getattr(character, "SEQUENCE_NAME", "?"),
        "pathways": [],
        "tier": None,
        "pillar": None,
    }

    # 接入 OldOnePath / pillar_requirements 计算并校验需求
    if group_key in FOUR_PILLARS:
        pillar = OldOnePath.pillar_requirements(group_key)
        composition["tier"] = pillar.get("tier")
        composition["pillar"] = FOUR_PILLARS[group_key]["name"]
    req = OldOnePath.required_for_old_one(group_key)
    composition["requirements"] = req

    # 真正执行：聚合组内每条途径的唯一性 + 3 份序列1特性
    for pk in group["pathways"]:
        pname = PATHWAYS[pk]["name"]
        u = Uniqueness.get_or_create(f"{pname}唯一性", pk)
        u.bind(character)
        seq1 = []
        for i in (1, 2, 3):
            c = SequenceOneCharacteristic.ensure(pk, i)
            c.bind(character)
            seq1.append(f"{c.index}号")
        composition["pathways"].append({
            "pathway": pname,
            "uniqueness": u.name,
            "sequence_1": seq1,
        })
    return composition
