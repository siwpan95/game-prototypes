# -*- coding: utf-8 -*-
"""碎片驱动的被动能力系统。"""
from .fragments import FragmentSystem

class AbilitySystem:
    """能力增强系统"""
    def __init__(self, fragments: FragmentSystem):
        self.fragments = fragments
        self.danger_immune_timer = 0.0
        self._immune_cooldown: float = 0.0  # 全收集免疫冷却（防止永久免疫）

    def update(self, dt: float):
        """每帧更新能力状态"""
        if self.danger_immune_timer > 0:
            self.danger_immune_timer -= dt
        if self._immune_cooldown > 0:
            self._immune_cooldown -= dt
        # 检查全收集免疫
        self._check_passives()

    def _check_passives(self):
        """检查被动能力状态（每帧调用，实际检查在getter中）"""
        pass

    def get_depth_multiplier(self) -> float:
        """视野增强：5个同色碎片 → +15%"""
        for deco_type in range(2, 12):
            if self.fragments.get_count(deco_type) >= 5:
                return 1.15
        return 1.0

    def get_drain_multiplier(self) -> float:
        """耗能降低：5个同色碎片 → -20%"""
        for deco_type in range(2, 12):
            if self.fragments.get_count(deco_type) >= 5:
                return 0.8
        return 1.0

    def get_speed_multiplier(self) -> float:
        """移速增加：5个同色碎片 → +15%"""
        for deco_type in range(2, 12):
            if self.fragments.get_count(deco_type) >= 5:
                return 1.15
        return 1.0

    def is_danger_immune(self) -> bool:
        """10种各1 → 危险免疫5秒（含冷却60秒防止永久触发）"""
        # 仍在免疫期内
        if self.danger_immune_timer > 0:
            return True
        # 冷却中，不可再次触发
        if self._immune_cooldown > 0:
            return False
        # 全收集且冷却结束 → 激活免疫
        if self.fragments.is_all_types_collected():
            self.danger_immune_timer = 5.0
            self._immune_cooldown = 65.0  # 5秒免疫+60秒冷却
            return True
        return False

    def has_vision_bonus(self) -> bool:
        """是否有视野增强"""
        return self.get_depth_multiplier() > 1.0

    def has_drain_reduction(self) -> bool:
        """是否有耗能降低"""
        return self.get_drain_multiplier() < 1.0

    def has_speed_bonus(self) -> bool:
        """是否有移速增加"""
        return self.get_speed_multiplier() > 1.0
