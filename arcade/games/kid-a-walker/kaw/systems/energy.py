# -*- coding: utf-8 -*-
"""玩家能量系统。"""
from dataclasses import dataclass

from ..config import ACID_DRAIN_RATE, ENERGY_MAX, SPAWN_GRACE_PERIOD

@dataclass
class EnergySystem:
    """玩家能量管理"""
    energy: float = ENERGY_MAX
    max_energy: float = ENERGY_MAX
    drain_move: float = 1.0       # 点/秒，移动时消耗
    drain_red: float = 3.0        # 点/秒，红色区消耗
    recover_glow: float = 0.5     # 点/秒，发光柱附近恢复
    shield_timer: float = 0.0     # 护盾剩余时间（秒）
    grace_timer: float = SPAWN_GRACE_PERIOD  # 出生保护期倒计时
    is_dead: bool = False

    def update(self, dt: float, is_moving: bool,
               near_glow: bool, near_red: bool, near_acid: bool,
               drain_mult: float = 1.0, shielded: bool = False):
        """每帧更新能量值
        dt: 帧间隔（秒）
        is_moving: 玩家是否在移动
        near_glow: 是否在发光柱(2)附近（5x5 邻域）
        near_red: 是否在红色警示区(3)附近（5x5 邻域）
        near_acid: 是否在酸液池(5)附近（5x5 邻域）
        drain_mult: AbilitySystem 提供的消耗倍率
        shielded: 是否处于危险免疫状态（AbilitySystem全收集免疫）
        """
        # 护盾倒计时
        if self.shield_timer > 0:
            self.shield_timer -= dt

        # 出生保护期倒计时
        if self.grace_timer > 0:
            self.grace_timer -= dt
            # 保护期内仅发光柱恢复生效，不消耗能量
            if near_glow and self.energy < self.max_energy:
                self.energy += self.recover_glow * dt
                self.energy = min(self.max_energy, self.energy)
            return

        if shielded:
            return  # 危险免疫期完全不消耗

        # 护盾减半消耗（能量核心护盾，独立于AbilitySystem免疫）
        shield_mult = 0.5 if self.shield_timer > 0 else 1.0

        # 消耗计算
        # 红色警示区邻域消耗（不论移动与否）
        if near_red:
            self.energy -= self.drain_red * dt * drain_mult * shield_mult
            if is_moving:
                self.energy -= self.drain_move * dt * drain_mult * shield_mult
        elif is_moving:
            self.energy -= self.drain_move * dt * drain_mult * shield_mult

        # 酸液池邻域接触
        if near_acid:
            self.energy -= ACID_DRAIN_RATE * dt * shield_mult

        # 发光柱恢复
        if near_glow and self.energy < self.max_energy:
            self.energy += self.recover_glow * dt

        # 夹紧
        self.energy = max(0.0, min(self.max_energy, self.energy))
        if self.energy <= 0:
            self.is_dead = True

    def recover(self, amount: float):
        """恢复指定量能量"""
        self.energy = min(self.max_energy, self.energy + amount)

    def activate_shield(self, duration: float):
        """激活护盾指定秒数"""
        self.shield_timer = duration

    def is_shielded(self) -> bool:
        """是否处于护盾状态"""
        return self.shield_timer > 0

    def get_ratio(self) -> float:
        """获取能量比例 0.0~1.0"""
        return self.energy / self.max_energy if self.max_energy > 0 else 0.0

    def reset(self):
        """重置能量系统"""
        self.energy = self.max_energy
        self.shield_timer = 0.0
        self.grace_timer = SPAWN_GRACE_PERIOD
        self.is_dead = False
