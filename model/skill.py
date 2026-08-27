"""技能数据模型"""


class Skill:
    """技能"""

    def __init__(self, skill_data: "SkillData"):
        self.id = skill_data.id
        self.name = skill_data.name
        self.type = skill_data.type  # attack / defense / evade / special
        self.cost = skill_data.cost  # 消耗（HP 或 资源）
        self.effect = skill_data.effect  # 效果描述/效果值
        self.description = skill_data.description
        self.data = skill_data
