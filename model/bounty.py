"""赏金首管理器（纯业务逻辑，零UI依赖）

生命周期：locked（未接） → active（悬赏榜已接取） → defeated（已击杀待领）
→ claimed（赏金已入账）。

- 接取/领赏只能在城镇悬赏榜操作（VM 层约束）
- 走到赏金首坐标即触发明雷战斗（接取与否都能打）
- 接取状态下击杀即时入账；未接取则击杀后可回悬赏榜补领
"""
from typing import Optional


class BountyStatus:
    LOCKED = "locked"
    ACTIVE = "active"
    DEFEATED = "defeated"
    CLAIMED = "claimed"


class BountyManager:
    """赏金首状态机 — 静态方法"""

    @staticmethod
    def status(data: "GameData", bounty_id: int) -> str:
        if bounty_id in data.bounty_claimed:
            return BountyStatus.CLAIMED
        if bounty_id in data.bounty_defeated:
            return BountyStatus.DEFEATED
        if bounty_id in data.bounty_accepted:
            return BountyStatus.ACTIVE
        return BountyStatus.LOCKED

    @staticmethod
    def accept(data: "GameData", bounty_id: int) -> bool:
        """悬赏榜接取；已领取/已接取的返回 False"""
        status = BountyManager.status(data, bounty_id)
        if status != BountyStatus.LOCKED:
            return False
        data.bounty_accepted.add(bounty_id)
        return True

    @staticmethod
    def check_encounter(data: "GameData") -> Optional["BountyData"]:
        """玩家脚下是否有可挑战的赏金首（未领取 + 同地图 + 坐标命中）"""
        if data.config is None:
            return None
        for bounty in data.config.bounties.values():
            if bounty.map_id != data.current_map_id:
                continue
            if bounty.id in data.bounty_claimed:
                continue
            if (data.player_x, data.player_y) == (bounty.x, bounty.y):
                return bounty
        return None

    @staticmethod
    def on_defeated(data: "GameData", bounty_id: int) -> int:
        """击杀赏金首：标记 defeated；若已接取则立即结算，返回入账金额"""
        if bounty_id in data.bounty_claimed:
            return 0
        data.bounty_defeated.add(bounty_id)
        if bounty_id in data.bounty_accepted:
            return BountyManager._payout(data, bounty_id)
        return 0

    @staticmethod
    def claim(data: "GameData", bounty_id: int) -> int:
        """悬赏榜领赏：仅 defeated 状态可领，返回入账金额"""
        if BountyManager.status(data, bounty_id) != BountyStatus.DEFEATED:
            return 0
        return BountyManager._payout(data, bounty_id)

    @staticmethod
    def _payout(data: "GameData", bounty_id: int) -> int:
        """实际入账：悬赏金 + 敌人基础金币，标记 claimed"""
        if data.config is None:
            return 0
        bounty = data.config.bounties.get(bounty_id)
        if bounty is None:
            return 0
        data.gold += bounty.reward
        data.bounty_claimed.add(bounty_id)
        data.bounty_defeated.discard(bounty_id)
        data.bounty_accepted.discard(bounty_id)
        data.add_log(f"悬赏结算: {bounty.name}，获得 {bounty.reward} 金币！")
        return bounty.reward

    @staticmethod
    def status_label(status: str) -> str:
        return {
            BountyStatus.LOCKED: "可接取",
            BountyStatus.ACTIVE: "进行中",
            BountyStatus.DEFEATED: "待领赏",
            BountyStatus.CLAIMED: "已领取",
        }.get(status, status)
