"""SFX Bank for KARD — 音效资源库。

定义所有游戏音效的：
- 文件路径（映射到 faatt.py 程序化合成生成的 WAV 文件）
- 默认音量/音调
- 随机化（音高、音量）范围
- 优先级
- 语音限制（防止同类音效过多）

遵循音频工程师规范：
- 所有音效为随机化容器（pitch/volume variation）
- 测试最大同时播放数
- 配置语音抢占模式

生成命令: python faatt.py --batch --output assets/audio
"""

import os
import random


# ── 音效定义协议 ───────────────────────────────────────
class SFXDef:
    """单个音效定义。"""

    def __init__(
        self,
        name: str,
        file_paths: list[str],  # 支持多文件随机
        volume: float = 1.0,
        pitch_range: tuple[float, float] = (0.95, 1.05),
        volume_range: tuple[float, float] = (0.9, 1.1),
        priority: int = 2,  # 0=最高
        max_voices: int = 4,  # 最大同时播放数
        steal_mode: str = "STEAL_FARTHEST",  # "NEVER_STEAL" | "STEAL_QUIETEST" | "STEAL_FARTHEST" | "STEAL_OLDEST"
        is_3d: bool = False,
        min_distance: float = 1.0,
        max_distance: float = 50.0,
        attack: float = 0.01,  # 淡入时间（秒）
        release: float = 0.05,  # 淡出时间（秒）
    ) -> None:
        self.name: str = name
        self.file_paths: list[str] = file_paths
        self.volume: float = volume
        self.pitch_range: tuple[float, float] = pitch_range
        self.volume_range: tuple[float, float] = volume_range
        self.priority: int = priority
        self.max_voices: int = max_voices
        self.steal_mode: str = steal_mode
        self.is_3d: bool = is_3d
        self.min_distance: float = min_distance
        self.max_distance: float = max_distance
        self.attack: float = attack
        self.release: float = release

    def get_random_file(self) -> str:
        """随机选择一个音效文件。"""
        return random.choice(self.file_paths) if self.file_paths else ""

    def get_random_pitch(self) -> float:
        """返回随机化音高。"""
        return random.uniform(self.pitch_range[0], self.pitch_range[1])

    def get_random_volume(self) -> float:
        """返回随机化音量。"""
        return self.volume * random.uniform(self.volume_range[0], self.volume_range[1])


# ── 辅助函数 ─────────────────────────────────────────────
def _f(sfx_root: str, category: str, filename: str) -> list[str]:
    """构建单个 WAV 文件路径列表（单文件）"""
    return [os.path.join(sfx_root, "sfx", category, filename)]


def _fm(sfx_root: str, category: str, filenames: list[str]) -> list[str]:
    """构建多个 WAV 文件路径列表（多文件随机）"""
    return [os.path.join(sfx_root, "sfx", category, f) for f in filenames]


# ── 音效库 ───────────────────────────────────────────────
class SFXBank:
    """游戏音效库 —— 所有音效的注册表。

    使用方式：
    bank = SFXBank()
    sfx_def = bank.get("ui_click")
    file = sfx_def.get_random_file()
    """

    def __init__(self, sfx_root: str) -> None:
        self.sfx_root: str = sfx_root
        self.sfx_defs: dict[str, SFXDef] = {}
        self._init()

    def _init(self) -> None:
        """初始化所有音效定义。

        文件路径映射到 faatt.py 程序化合成引擎生成的 WAV 文件。
        生成命令: python faatt.py --batch --output assets/audio
        """

        # ── UI 音效（优先级 0：永不抢占）─────────────
        self.register(SFXDef(
            name="ui_click",
            file_paths=_f(self.sfx_root, "ui", "button_click.wav"),
            volume=0.6,
            pitch_range=(0.98, 1.02),
            priority=0,
            max_voices=2,
            steal_mode="NEVER_STEAL",
            attack=0.005,
            release=0.02,
        ))

        self.register(SFXDef(
            name="ui_hover",
            file_paths=_f(self.sfx_root, "ui", "button_hover.wav"),
            volume=0.3,
            pitch_range=(0.95, 1.05),
            priority=0,
            max_voices=1,
            steal_mode="STEAL_OLDEST",
            attack=0.005,
            release=0.02,
        ))

        self.register(SFXDef(
            name="ui_button_click",
            file_paths=_f(self.sfx_root, "ui", "confirm.wav"),
            volume=0.7,
            pitch_range=(0.97, 1.03),
            priority=0,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ui_error",
            file_paths=_f(self.sfx_root, "ui", "error.wav"),
            volume=0.5,
            pitch_range=(0.95, 1.0),
            priority=0,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ui_success",
            file_paths=_f(self.sfx_root, "ui", "notification.wav"),
            volume=0.6,
            pitch_range=(0.98, 1.02),
            priority=0,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ui_menu_open",
            file_paths=_f(self.sfx_root, "ui", "menu_open.wav"),
            volume=0.5,
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ui_menu_close",
            file_paths=_f(self.sfx_root, "ui", "menu_close.wav"),
            volume=0.45,
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ui_scroll",
            file_paths=_f(self.sfx_root, "ui", "scroll.wav"),
            volume=0.25,
            priority=0,
            max_voices=1,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="ui_cancel",
            file_paths=_f(self.sfx_root, "ui", "cancel.wav"),
            volume=0.4,
            priority=0,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        # ── 卡牌音效（优先级 1）─────────────────────
        self.register(SFXDef(
            name="card_draw",
            file_paths=_f(self.sfx_root, "card", "card_draw.wav"),
            volume=0.5,
            pitch_range=(0.95, 1.05),
            priority=1,
            max_voices=3,
            steal_mode="STEAL_QUIETEST",
        ))

        self.register(SFXDef(
            name="card_play",
            file_paths=_f(self.sfx_root, "card", "card_play.wav"),
            volume=0.7,
            pitch_range=(0.97, 1.03),
            priority=1,
            max_voices=4,
            steal_mode="STEAL_FARTHEST",
        ))

        self.register(SFXDef(
            name="card_select",
            file_paths=_f(self.sfx_root, "card", "card_select.wav"),
            volume=0.4,
            pitch_range=(0.98, 1.02),
            priority=1,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="card_discard",
            file_paths=_f(self.sfx_root, "card", "card_exhaust.wav"),
            volume=0.4,
            pitch_range=(0.95, 1.05),
            priority=1,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="card_upgrade",
            file_paths=_f(self.sfx_root, "card", "card_upgrade.wav"),
            volume=0.8,
            pitch_range=(0.98, 1.02),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="card_hover",
            file_paths=_f(self.sfx_root, "card", "card_hover.wav"),
            volume=0.28,
            pitch_range=(0.95, 1.08),
            priority=1,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="card_shuffle",
            file_paths=_f(self.sfx_root, "card", "shuffle.wav"),
            volume=0.35,
            pitch_range=(0.95, 1.05),
            priority=1,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="card_reveal",
            file_paths=_f(self.sfx_root, "card", "card_reveal.wav"),
            volume=0.5,
            pitch_range=(0.95, 1.05),
            priority=1,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="ethereal_pass",
            file_paths=_f(self.sfx_root, "card", "ethereal_pass.wav"),
            volume=0.4,
            pitch_range=(0.96, 1.04),
            priority=1,
            max_voices=3,
            steal_mode="STEAL_QUIETEST",
        ))

        # ── 战斗音效（优先级 2）─────────────────────
        self.register(SFXDef(
            name="combat_attack",
            file_paths=_f(self.sfx_root, "combat", "attack_melee.wav"),
            volume=0.8,
            pitch_range=(0.93, 1.07),
            priority=2,
            max_voices=8,
            steal_mode="STEAL_FARTHEST",
            is_3d=True,
            min_distance=2.0,
            max_distance=30.0,
        ))

        self.register(SFXDef(
            name="combat_attack_magic",
            file_paths=_f(self.sfx_root, "combat", "attack_magic.wav"),
            volume=0.65,
            pitch_range=(0.94, 1.06),
            priority=2,
            max_voices=6,
            steal_mode="STEAL_FARTHEST",
            is_3d=True,
        ))

        self.register(SFXDef(
            name="combat_damage_player",
            file_paths=_f(self.sfx_root, "combat", "damage_taken.wav"),
            volume=0.9,
            pitch_range=(0.92, 1.04),
            priority=1,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="combat_damage_enemy",
            file_paths=_f(self.sfx_root, "combat", "weak_hit.wav"),
            volume=0.5,
            pitch_range=(0.90, 1.10),
            priority=2,
            max_voices=6,
            steal_mode="STEAL_FARTHEST",
            is_3d=True,
        ))

        self.register(SFXDef(
            name="combat_heal",
            file_paths=_f(self.sfx_root, "combat", "heal.wav"),
            volume=0.6,
            pitch_range=(0.97, 1.03),
            priority=1,
            max_voices=3,
            steal_mode="STEAL_QUIETEST",
        ))

        self.register(SFXDef(
            name="combat_shield",
            file_paths=_f(self.sfx_root, "combat", "block_hit.wav"),
            volume=0.55,
            pitch_range=(0.95, 1.07),
            priority=2,
            max_voices=3,
            steal_mode="STEAL_QUIETEST",
        ))

        self.register(SFXDef(
            name="combat_death",
            file_paths=_f(self.sfx_root, "combat", "enemy_death.wav"),
            volume=0.8,
            pitch_range=(0.94, 1.04),
            priority=1,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="combat_critical",
            file_paths=_f(self.sfx_root, "combat", "critical_hit.wav"),
            volume=0.85,
            pitch_range=(0.92, 1.06),
            priority=1,
            max_voices=3,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="combat_dodge",
            file_paths=_f(self.sfx_root, "combat", "dodge.wav"),
            volume=0.35,
            pitch_range=(0.95, 1.10),
            priority=2,
            max_voices=4,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="combat_player_hurt",
            file_paths=_f(self.sfx_root, "combat", "player_hurt.wav"),
            volume=0.55,
            pitch_range=(0.94, 1.04),
            priority=1,
            max_voices=2,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="combat_shield_gain",
            file_paths=_f(self.sfx_root, "combat", "shield_gain.wav"),
            volume=0.5,
            pitch_range=(0.97, 1.03),
            priority=2,
            max_voices=3,
            steal_mode="STEAL_QUIETEST",
        ))

        self.register(SFXDef(
            name="combat_poison",
            file_paths=_f(self.sfx_root, "combat", "poison_tick.wav"),
            volume=0.35,
            pitch_range=(0.95, 1.08),
            priority=2,
            max_voices=5,
            steal_mode="STEAL_OLDEST",
        ))

        # ── 敌人音效（优先级 2）───────────────────────
        self.register(SFXDef(
            name="enemy_intent_attack",
            file_paths=_f(self.sfx_root, "system", "elite_alert.wav"),
            volume=0.5,
            pitch_range=(0.98, 1.02),
            priority=2,
            max_voices=3,
            steal_mode="STEAL_FARTHEST",
        ))

        self.register(SFXDef(
            name="enemy_turn_start",
            file_paths=_f(self.sfx_root, "system", "notification.wav"),
            volume=0.45,
            pitch_range=(0.98, 1.02),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        # ── 随从/召唤物音效（优先级 2）──────────────────
        self.register(SFXDef(
            name="minion_summon",
            file_paths=_f(self.sfx_root, "system", "item_pickup.wav"),
            volume=0.6,
            pitch_range=(0.95, 1.08),
            priority=2,
            max_voices=4,
            steal_mode="STEAL_FARTHEST",
        ))

        self.register(SFXDef(
            name="minion_attack",
            file_paths=_f(self.sfx_root, "combat", "attack_melee.wav"),
            volume=0.5,
            pitch_range=(1.0, 1.15),
            priority=2,
            max_voices=6,
            steal_mode="STEAL_FARTHEST",
            is_3d=True,
        ))

        self.register(SFXDef(
            name="minion_death",
            file_paths=_f(self.sfx_root, "combat", "damage_taken.wav"),
            volume=0.4,
            pitch_range=(1.05, 1.20),
            priority=2,
            max_voices=4,
            steal_mode="STEAL_OLDEST",
        ))

        # ── 游戏阶段音效（优先级 0-1）────────────────
        self.register(SFXDef(
            name="game_start",
            file_paths=_f(self.sfx_root, "system", "victory_fanfare.wav"),
            volume=0.75,
            pitch_range=(0.99, 1.01),
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="game_over",
            file_paths=_f(self.sfx_root, "system", "game_over.wav"),
            volume=0.85,
            pitch_range=(0.98, 1.02),
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="room_clear",
            file_paths=_f(self.sfx_root, "system", "achievement.wav"),
            volume=0.7,
            pitch_range=(0.98, 1.03),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="reward_show",
            file_paths=_f(self.sfx_root, "system", "gold_pickup.wav"),
            volume=0.6,
            pitch_range=(0.97, 1.06),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="level_up",
            file_paths=_f(self.sfx_root, "system", "level_up.wav"),
            volume=0.6,
            pitch_range=(0.98, 1.04),
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="achievement_unlock",
            file_paths=_f(self.sfx_root, "system", "achievement.wav"),
            volume=0.55,
            pitch_range=(0.98, 1.03),
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="boss_appear",
            file_paths=_f(self.sfx_root, "system", "boss_appear.wav"),
            volume=0.65,
            pitch_range=(0.95, 1.01),
            priority=0,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        # ── 事件/商人/篝火音效（优先级 1）────────────────
        self.register(SFXDef(
            name="event_enter",
            file_paths=_f(self.sfx_root, "system", "transition.wav"),
            volume=0.35,
            pitch_range=(0.98, 1.02),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="merchant_enter",
            file_paths=_f(self.sfx_root, "ui", "scroll.wav"),
            volume=0.25,
            pitch_range=(0.95, 1.05),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="merchant_buy",
            file_paths=_f(self.sfx_root, "ui", "confirm.wav"),
            volume=0.55,
            pitch_range=(0.97, 1.03),
            priority=1,
            max_voices=2,
            steal_mode="STEAL_QUIETEST",
        ))

        self.register(SFXDef(
            name="campfire_enter",
            file_paths=_f(self.sfx_root, "ui", "menu_open.wav"),
            volume=0.4,
            pitch_range=(0.95, 1.02),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="campfire_upgrade",
            file_paths=_f(self.sfx_root, "card", "card_upgrade.wav"),
            volume=0.6,
            pitch_range=(0.97, 1.04),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        self.register(SFXDef(
            name="campfire_rest",
            file_paths=_f(self.sfx_root, "system", "potion_use.wav"),
            volume=0.48,
            pitch_range=(0.97, 1.04),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
        ))

        # ── 玩家状态音效（优先级 1）───────────────────
        self.register(SFXDef(
            name="player_hp_low",
            file_paths=_f(self.sfx_root, "ui", "error.wav"),
            volume=0.4,
            pitch_range=(0.90, 0.97),
            priority=1,
            max_voices=1,
            steal_mode="NEVER_STEAL",
            attack=0.1,
            release=0.2,
        ))

        self.register(SFXDef(
            name="player_gold_change",
            file_paths=_f(self.sfx_root, "system", "gold_pickup.wav"),
            volume=0.4,
            pitch_range=(0.95, 1.12),
            priority=2,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

        self.register(SFXDef(
            name="player_energy_change",
            file_paths=_f(self.sfx_root, "ui", "button_hover.wav"),
            volume=0.28,
            pitch_range=(1.0, 1.20),
            priority=2,
            max_voices=2,
            steal_mode="STEAL_OLDEST",
        ))

    def register(self, sfx_def: SFXDef) -> None:
        """注册一个音效定义。"""
        self.sfx_defs[sfx_def.name] = sfx_def

    def get(self, name: str) -> SFXDef | None:
        """获取音效定义。"""
        return self.sfx_defs.get(name)

    def get_all_names(self) -> list[str]:
        """返回所有已注册音效的名称。"""
        return list(self.sfx_defs.keys())

    def validate_files(self) -> dict[str, list[str]]:
        """验证所有音效文件是否存在，返回缺失文件列表。"""
        missing: dict[str, list[str]] = {}
        for name, sfx_def in self.sfx_defs.items():
            missing_files = [fp for fp in sfx_def.file_paths if not os.path.isfile(fp)]
            if missing_files:
                missing[name] = missing_files
        return missing
