# -*- coding: utf-8 -*-
"""
休息服务 — D&D 风格双休制（短休 / 长休）

配置链路（三级降级）：
  1. Excel「休息配置」Sheet  → 策划直接编辑，即时生效
  2. rest_config.json        → Excel 不可用时的兜底文件
  3. DEFAULT_REST_CONFIG     → 硬编码最终回退（以下所有链路都失败时）

战术预设：
  ┌──────────┬──────────────────────────────┐
  │ 短休     │ 每 N 次战斗 / 每房间清空      │
  │          │ 回复 30% HP + 30% MP          │
  ├──────────┼──────────────────────────────┤
  │ 长休     │ 每地牢清空                     │
  │          │ 回满 HP + MP + 重置技能冷却    │
  └──────────┴──────────────────────────────┘

全自动：无需手动按钮，按战术预设固定执行。
"""
from __future__ import annotations
from typing import List, TYPE_CHECKING

from ..utils.logging_config import get_logger

if TYPE_CHECKING:
    from ..models.character import Party

logger = get_logger(__name__)

# ── 硬编码最终回退 ──────────────────────────────────────────
FALLBACK_REST_CONFIG: dict = {
    "short_rest": {
        "combat_interval": 3,
        "on_room_clear": True,
        "hp_restore_pct": 0.30,
        "mp_restore_pct": 0.30,
    },
    "long_rest": {
        "on_dungeon_clear": True,
        "hp_restore_pct": 1.0,
        "mp_restore_pct": 1.0,
        "reset_cooldowns": True,
    },
}


class RestService:
    """双休制休息服务 — 全自动触发，无需按钮"""

    def __init__(self, data_service=None):
        self._config = FALLBACK_REST_CONFIG.copy()
        self._combat_counter: int = 0
        self._data_service = data_service  # 保存引用，延迟加载
        self._config_loaded = False

    # ── 配置加载（三级降级：JSON → 硬编码回退）───────

    def _ensure_config(self):
        """按需加载休息配置（零预加载，首次使用时触发）"""
        if self._config_loaded:
            return
        self._config_loaded = True
        if self._data_service is not None:
            self._try_load_from_data(self._data_service)

    def _try_load_from_data(self, data_service) -> None:
        """通过 DataService 统一入口加载休息配置。"""
        try:
            cfg = data_service.get_rest_config()
            if cfg:
                self._merge_config(cfg)
        except Exception:
            pass

    def _merge_config(self, cfg: dict) -> None:
        """合并外部配置到当前值（局部分段覆盖，不丢失默认键）"""
        for section in ("short_rest", "long_rest"):
            if section in cfg:
                self._config[section].update(cfg[section])

    # ── 计数器管理 ──────────────────────────────────────

    def on_combat_end(self) -> None:
        """每场战斗结束时调用，累加计数器"""
        self._combat_counter += 1

    @property
    def combat_interval(self) -> int:
        self._ensure_config()
        return self._config["short_rest"]["combat_interval"]

    @property
    def should_short_rest_after_combat(self) -> bool:
        """是否达到短休触发条件（每 N 次战斗）"""
        return self._combat_counter >= self.combat_interval

    # ── 短休 ──────────────────────────────────────────

    def short_rest(self, party: Party) -> List[str]:
        """
        执行短休：全队存活成员回复 HP%/MP%。
        返回日志消息列表。
        """
        self._ensure_config()
        cfg = self._config["short_rest"]
        hp_pct = cfg["hp_restore_pct"]
        mp_pct = cfg["mp_restore_pct"]

        messages: List[str] = []
        self._combat_counter = 0

        for member in party.get_alive():
            hp_before = member.hp
            mp_before = member.mp
            member.heal(int(member.max_hp * hp_pct))
            member.mp = min(member.max_mp, member.mp + int(member.max_mp * mp_pct))

            hp_gained = member.hp - hp_before
            mp_gained = member.mp - mp_before

            tag = f"{member.char_class.category_name}·{member.name}"
            parts = []
            if hp_gained > 0:
                parts.append(f"+{hp_gained}HP")
            if mp_gained > 0:
                parts.append(f"+{mp_gained}MP")
            if parts:
                messages.append(f"[短休] {tag} {' '.join(parts)}")

        return messages

    def should_short_rest_on_room_clear(self) -> bool:
        """房间清空时是否触发短休"""
        self._ensure_config()
        return self._config["short_rest"]["on_room_clear"]

    # ── 长休 ──────────────────────────────────────────

    def long_rest(self, party: Party) -> List[str]:
        """
        执行长休：全队回满 HP + MP，重置所有技能冷却。
        返回日志消息列表。
        """
        self._ensure_config()
        cfg = self._config["long_rest"]
        hp_pct = cfg["hp_restore_pct"]
        mp_pct = cfg["mp_restore_pct"]
        reset_cd = cfg["reset_cooldowns"]

        messages: List[str] = []
        recovered = 0
        cd_reset = 0

        for member in party.members:
            old_hp = member.hp
            old_mp = member.mp

            member.heal(int(member.max_hp * hp_pct))
            member.mp = int(member.max_mp * mp_pct)

            if member.hp > old_hp or member.mp > old_mp:
                recovered += 1

            if reset_cd:
                for skill in member.skills:
                    if skill.current_cooldown > 0:
                        skill.current_cooldown = 0.0
                        cd_reset += 1

        if recovered > 0:
            messages.append(f"[长休] 全队休整完毕！{recovered}人恢复状态")
        if cd_reset > 0:
            messages.append(f"[长休] {cd_reset}个技能冷却已重置")

        return messages

    def should_long_rest_on_dungeon_clear(self) -> bool:
        """地牢清空时是否触发长休"""
        self._ensure_config()
        return self._config["long_rest"]["on_dungeon_clear"]

    # ── 配置查询 ──────────────────────────────────────

    def get_config(self) -> dict:
        """获取当前生效的休息配置（用于 UI 显示 / 调试）"""
        self._ensure_config()
        return self._config

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化（仅保存计数器运行时状态）"""
        return {
            "combat_counter": self._combat_counter,
        }

    def from_dict(self, data: dict) -> None:
        """反序列化"""
        self._combat_counter = data.get("combat_counter", 0)
