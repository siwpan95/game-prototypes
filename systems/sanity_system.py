"""
理智系统 — 理智值钳制 + 恢复 + 游戏状态判定
============================================
- 每帧钳制理智值在 [0, max_value] 范围内
- 理智归零 → 触发 GAME_OVER 事件
- 监听卡牌收集事件，特定卡牌可恢复理智
"""
from core.ecs import System
from components.sanity import Sanity


class SanitySystem(System):
    # 理智恢复表：收集特定卡牌时恢复的理智值
    SANITY_RECOVERY = {
        "lavender_01": 15,      # 薰衣草 — 宁神安眠
        "full_moon_01": 10,     # 满月 — 月光抚慰
        "owl_01": 8,            # 猫头鹰 — 智慧之光
    }

    def __init__(self, event_bus=None):
        self.bus = event_bus
        self._game_over_emitted = False
        if self.bus:
            self.bus.subscribe("CARD_COLLECTED", self._on_card_collected)

    def _on_card_collected(self, data):
        """收集特定卡牌时恢复理智。"""
        card_id = data.get("card_id", "")
        recovery = self.SANITY_RECOVERY.get(card_id, 0)
        if recovery > 0 and self.bus:
            self.bus.emit("SANITY_RECOVER", {"amount": recovery, "card_id": card_id})

    def update(self, world, dt):
        player = world.entities.get("player")
        if not player:
            return
        s = player.get(Sanity)
        if not s:
            return

        # 钳制理智值
        s.value = max(0, min(s.value, s.max_value))

        # 理智归零 → 游戏结束
        if s.value == 0 and not self._game_over_emitted:
            self._game_over_emitted = True
            if self.bus:
                self.bus.emit("GAME_OVER", {"reason": "sanity_zero"})
