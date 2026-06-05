"""Audio Components for KARD ECS — 音频相关 ECS 组件。

遵循游戏音频工程师规范：
- AudioEventComponent：游戏逻辑通过此组件排队音频事件，由 AudioSystem 消费
- MusicStateComponent：同步音乐控制器状态
- AudioListenerComponent：音频监听器（玩家位置）
- SpatialAudioComponent：3D 空间音频源
"""

from dataclasses import dataclass, field
from typing import Optional


# ── 音频事件类型 ───────────────────────────────────────────────────
class AudioEventType:
    """音频事件类型常量。"""
    # UI
    UI_CLICK = "ui_click"
    UI_HOVER = "ui_hover"
    UI_BUTTON_CLICK = "ui_button_click"
    UI_ERROR = "ui_error"
    UI_SUCCESS = "ui_success"
    UI_MENU_OPEN = "ui_menu_open"
    UI_MENU_CLOSE = "ui_menu_close"
    UI_SCROLL = "ui_scroll"
    UI_CANCEL = "ui_cancel"

    # 卡牌
    CARD_DRAW = "card_draw"
    CARD_PLAY = "card_play"
    CARD_SELECT = "card_select"
    CARD_DISCARD = "card_discard"
    CARD_UPGRADE = "card_upgrade"
    CARD_HOVER = "card_hover"
    CARD_SHUFFLE = "card_shuffle"
    CARD_REVEAL = "card_reveal"
    ETHEREAL_PASS = "ethereal_pass"

    # 战斗
    COMBAT_ATTACK = "combat_attack"
    COMBAT_ATTACK_MAGIC = "combat_attack_magic"
    COMBAT_DAMAGE_PLAYER = "combat_damage_player"
    COMBAT_DAMAGE_ENEMY = "combat_damage_enemy"
    COMBAT_HEAL = "combat_heal"
    COMBAT_SHIELD = "combat_shield"
    COMBAT_DEATH = "combat_death"
    COMBAT_CRITICAL = "combat_critical"
    COMBAT_DODGE = "combat_dodge"
    COMBAT_PLAYER_HURT = "combat_player_hurt"
    COMBAT_SHIELD_GAIN = "combat_shield_gain"
    COMBAT_POISON = "combat_poison"

    # 敌人
    ENEMY_INTENT_ATTACK = "enemy_intent_attack"
    ENEMY_TURN_START = "enemy_turn_start"

    # 随从
    MINION_SUMMON = "minion_summon"
    MINION_ATTACK = "minion_attack"
    MINION_DEATH = "minion_death"

    # 游戏阶段
    GAME_START = "game_start"
    GAME_OVER = "game_over"
    ROOM_CLEAR = "room_clear"
    REWARD_SHOW = "reward_show"
    LEVEL_UP = "level_up"
    ACHIEVEMENT_UNLOCK = "achievement_unlock"
    BOSS_APPEAR = "boss_appear"

    # 事件/商人/篝火
    EVENT_ENTER = "event_enter"
    MERCHANT_ENTER = "merchant_enter"
    MERCHANT_BUY = "merchant_buy"
    CAMPFIRE_ENTER = "campfire_enter"
    CAMPFIRE_UPGRADE = "campfire_upgrade"
    CAMPFIRE_REST = "campfire_rest"

    # 玩家状态
    PLAYER_HP_LOW = "player_hp_low"
    PLAYER_GOLD_CHANGE = "player_gold_change"
    PLAYER_ENERGY_CHANGE = "player_energy_change"


@dataclass
class AudioEventComponent:
    """音频事件组件 —— 游戏逻辑向此组件追加事件，由 AudioSystem 消费。

    音频工程师规范：
    - 游戏逻辑不直接调用 pygame.mixer
    - 而是通过此组件排队事件
    - AudioSystem 在每帧末尾统一处理
    """
    events: list[tuple[str, float, float]] = field(default_factory=list)
    # 每个事件: (event_name, volume_override, pitch_override)
    # volume_override: 1.0 = 使用定义中的音量
    # pitch_override:  1.0 = 使用定义中的音高

    def add(self, event_name: str, volume: float = 1.0, pitch: float = 1.0) -> None:
        """追加一个音频事件到队列。"""
        self.events.append((event_name, volume, pitch))

    def clear(self) -> None:
        """清空事件队列（AudioSystem 消费后调用）。"""
        self.events.clear()


@dataclass
class MusicStateComponent:
    """音乐状态组件 —— 与 MusicController 同步。"""
    combat_intensity: float = 0.0
    player_health: float = 1.0
    game_phase: str = "MENU"
    current_track: str = "menu"
    target_track: str = "menu"
    is_transitioning: bool = False


@dataclass
class AudioListenerComponent:
    """音频监听器组件 —— 代表玩家听音位置。"""
    x: float = 640.0
    y: float = 360.0


@dataclass
class SpatialAudioComponent:
    """3D 空间音频组件 —— 声源位置，用于衰减和遮挡计算。"""
    x: float = 0.0
    y: float = 0.0
    min_distance: float = 1.0
    max_distance: float = 50.0

    def calculate_volume(self, listener_x: float, listener_y: float) -> float:
        """根据与监听器的距离计算音量衰减（对数衰减）。"""
        dx = self.x - listener_x
        dy = self.y - listener_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance <= self.min_distance:
            return 1.0
        if distance >= self.max_distance:
            return 0.0

        # 对数衰减（音频工程师规范）
        ratio = (distance - self.min_distance) / max(0.01, self.max_distance - self.min_distance)
        # 使用平滑曲线：近距离衰减慢，远距离衰减快
        attenuation = 1.0 - (ratio * ratio)
        return max(0.0, min(1.0, attenuation))
