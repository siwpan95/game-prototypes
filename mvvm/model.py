"""
MVVM — Model 层
GameModel 持有 ECS World，提供游戏操作接口，并收集日志。
整合：词缀 / 装备 / 状态效果 / 随机事件 / Boss波
"""

import random
from typing import Callable, Dict, List, Optional

from ecs.components import (
    AttackComponent,
    BackpackComponent,
    EquipmentComponent,
    ExpComponent,
    HPComponent,
    MonsterComponent,
    MonsterTag,
    NameComponent,
    PlayerTag,
    RespawnComponent,
    StatusEffectComponent,
)
from ecs.entities import create_all_monsters, create_boss, create_player
from ecs.equipment import roll_equipment_drop
from ecs.random_events import trigger_random_event
from ecs.systems import (
    calc_attack_power,
    combat_system,
    respawn_system,
    rest_system,
    reset_player,
    status_effect_system,
)
from ecs.world import World


class GameModel:
    """
    游戏模型：封装 ECS world 和所有游戏操作。
    """

    def __init__(self, notify_fn: Optional[Callable[[str], None]] = None) -> None:
        self.world: World = World()
        self.player_eid: int = create_player(self.world)
        self.monster_eids: List[int] = create_all_monsters(self.world)
        self.boss_eid: Optional[int] = None
        self.log_lines: List[str] = []
        self._notify_fn: Optional[Callable[[str], None]] = notify_fn
        self._kill_count: int = 0           # 击杀计数（事件触发）
        self._event_threshold: int = 4       # 每 N 次击杀触发事件
        self._boss_wave_active: bool = False

    # ── 日志 ──────────────────────────────────────────────

    def _log(self, text: str) -> None:
        self.log_lines.append(text)
        if self._notify_fn:
            self._notify_fn("log")

    def get_log_text(self) -> str:
        return "\n".join(self.log_lines[-500:])

    # ── 查询接口 ─────────────────────────────────────────

    def get_player_state(self) -> Dict[str, object]:
        from ecs.systems import _effective_atk, _effective_crit, _effective_dodge
        hp_c = self.world.get_component(self.player_eid, HPComponent)
        exp_c = self.world.get_component(self.player_eid, ExpComponent)
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        if hp_c is None or exp_c is None:
            return {}
        atk = _effective_atk(self.world, self.player_eid)
        crit = _effective_crit(self.world, self.player_eid)
        dodge = _effective_dodge(self.world, self.player_eid)
        return {
            "level": exp_c.level,
            "atk": int(atk),
            "hp": hp_c.hp,
            "max_hp": hp_c.max_hp,
            "exp": exp_c.exp,
            "exp_threshold": exp_c.threshold(),
            "exp_pool": exp_c.exp_pool,
            "crit_chance": crit,
            "dodge_chance": dodge,
            "rest_cost": exp_c.rest_cost,
            "equipment": [eq for eq in (eq_c.equipped if eq_c else [])],
        }

    def get_monster_states(self) -> List[Dict[str, object]]:
        result: List[Dict[str, object]] = []
        all_eids = self.monster_eids + ([self.boss_eid] if self.boss_eid else [])
        for eid in all_eids:
            hp_c = self.world.get_component(eid, HPComponent)
            mon_c = self.world.get_component(eid, MonsterComponent)
            resp_c = self.world.get_component(eid, RespawnComponent)
            name_c = self.world.get_component(eid, NameComponent)
            if hp_c is None:
                continue
            result.append({
                "eid": eid,
                "name": name_c.name if name_c else "?",
                "hp": hp_c.hp,
                "max_hp": hp_c.max_hp,
                "alive": hp_c.alive,
                "exp_reward": mon_c.exp_reward if mon_c else 0,
                "respawn_timer": resp_c.respawn_timer if resp_c else 0,
                "is_boss": eid == self.boss_eid,
            })
        return result

    def is_player_dead(self) -> bool:
        hp_c = self.world.get_component(self.player_eid, HPComponent)
        return hp_c is not None and hp_c.hp <= 0

    def all_monsters_dead(self) -> bool:
        """检查所有普通怪物是否都死了（BOSS波触发条件）"""
        for eid in self.monster_eids:
            hp_c = self.world.get_component(eid, HPComponent)
            if hp_c and hp_c.alive:
                return False
        return True

    # ── 游戏操作 ─────────────────────────────────────────

    def attack_monster(self, idx: int) -> None:
        """攻击第 idx 只怪物（或 Boss）"""
        all_ids = self.monster_eids + ([self.boss_eid] if self.boss_eid else [])
        if idx < 0 or idx >= len(all_ids):
            return
        target_eid = all_ids[idx]
        was_alive = self._is_alive(target_eid)

        # 用 on_kill 回调处理装备掉落
        def on_kill(eid: int, mon_name: str) -> None:
            # 装备掉落
            eq = roll_equipment_drop()
            if eq:
                eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
                bp_c = self.world.get_component(self.player_eid, BackpackComponent)
                if eq_c and eq_c.equip(eq):
                    self._log(f"🎁 掉落：{eq['icon']}{eq['name']} — {eq['desc']}（已装备）")
                elif bp_c and bp_c.add(eq):
                    self._log(f"🎁 掉落：{eq['icon']}{eq['name']} — {eq['desc']}（→背包）")
                elif bp_c:
                    self._log(f"🎁 掉落：{eq['icon']}{eq['name']}，但装备栏和背包都已满")
                else:
                    self._log(f"🎁 掉落：{eq['icon']}{eq['name']}，但背包已满")
            # 击杀计数 → 随机事件
            self._kill_count += 1
            if self._kill_count >= self._event_threshold:
                self._kill_count = 0
                trigger_random_event(self.world, self.player_eid, self._log)

        combat_system(self.world, 0.0, self.player_eid, target_eid,
                      self._log, on_kill=on_kill)

        if self.is_player_dead():
            self._log("🔄 重新开始...")
            self._reset_game()
            return

        # Boss 被击杀后刷新所有怪物
        if self.boss_eid and target_eid == self.boss_eid:
            if not self._is_alive(target_eid):
                self._log("👑 Boss 被击杀！新一轮怪物刷新……")
                self._start_new_wave()

        # Boss波触发条件
        if self.all_monsters_dead() and self.boss_eid is None:
            self._spawn_boss()

        if self._notify_fn:
            self._notify_fn("player_state")
            self._notify_fn("monster_states")

    def rest(self) -> None:
        ok = rest_system(self.world, self.player_eid, self._log)
        if ok and self._notify_fn:
            self._notify_fn("player_state")

    def tick(self, dt: float = 1.0) -> None:
        """每秒调用一次：复活 + 状态效果"""
        respawn_system(self.world, dt, log_fn=self._log)
        status_effect_system(self.world, dt, self.player_eid, log_fn=self._log)
        if self._notify_fn:
            self._notify_fn("monster_states")
            self._notify_fn("player_state")

    # ── Boss 波 ──────────────────────────────────────────

    def _spawn_boss(self) -> None:
        exp_c = self.world.get_component(self.player_eid, ExpComponent)
        lv = exp_c.level if exp_c else 1
        self.boss_eid = create_boss(self.world, lv)
        self._boss_wave_active = True
        lb = self.world.get_component(self.boss_eid, NameComponent)
        name = lb.name if lb else "Boss"
        self._log(f"\n ═══ 👑 {name} 出现了！ ═══\n")
        if self._notify_fn:
            self._notify_fn("monster_states")

    def _start_new_wave(self) -> None:
        """Boss 被击杀后刷新新一波怪物"""
        # 移除旧怪物实体
        for eid in self.monster_eids[:]:
            self.world.destroy_entity(eid)
        self.monster_eids.clear()
        if self.boss_eid:
            self.world.destroy_entity(self.boss_eid)
            self.boss_eid = None
        self._boss_wave_active = False
        # 新一波（基于玩家等级）
        exp_c = self.world.get_component(self.player_eid, ExpComponent)
        lv = exp_c.level if exp_c else 1
        self.monster_eids = create_all_monsters(self.world, player_level=lv)
        if self._notify_fn:
            self._notify_fn("monster_states")

    # ── 内部辅助 ─────────────────────────────────────────

    def _is_alive(self, eid: int) -> bool:
        hp_c = self.world.get_component(eid, HPComponent)
        return hp_c is not None and hp_c.alive

    def buy_equipment(self, equip: dict) -> bool:
        """商人购买装备：花费经验池，优先装备栏，满了走背包"""
        price = equip.get("price", 10)
        exp_c = self.world.get_component(self.player_eid, ExpComponent)
        if exp_c is None or exp_c.exp_pool < price:
            return False
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        bp_c = self.world.get_component(self.player_eid, BackpackComponent)
        placed = False
        if eq_c and eq_c.equip(equip):
            placed = True
        elif bp_c and bp_c.add(equip):
            placed = True
        if not placed:
            return False
        exp_c.exp_pool -= price
        self._log(f"🛒 购买了 {equip['icon']}{equip['name']} — 花费 {price} 经验池")
        if self._notify_fn:
            self._notify_fn("player_state")
        return True

    def unequip_item(self, idx: int) -> bool:
        """卸下装备"""
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        if eq_c is None:
            return False
        eq = eq_c.unequip(idx)
        if eq:
            self._log(f"🗑 卸下了 {eq['icon']}{eq['name']}")
            if self._notify_fn:
                self._notify_fn("player_state")
            return True
        return False

    def get_equipped(self) -> list:
        """获取已装备列表"""
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        return eq_c.equipped if eq_c else []

    def get_backpack(self) -> list:
        """获取背包物品列表"""
        bp_c = self.world.get_component(self.player_eid, BackpackComponent)
        return bp_c.items if bp_c else []

    def move_equip_to_backpack(self, equip_idx: int) -> bool:
        """从装备栏卸下第 equip_idx 件 → 放入背包"""
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        bp_c = self.world.get_component(self.player_eid, BackpackComponent)
        if eq_c is None or bp_c is None:
            return False
        if equip_idx < 0 or equip_idx >= len(eq_c.equipped):
            return False
        item = eq_c.unequip(equip_idx)
        if item:
            if bp_c.add(item):
                self._log(f"🗑 {item['icon']}{item['name']} 卸下→背包")
                if self._notify_fn:
                    self._notify_fn("player_state")
                return True
            else:
                # 背包满了，装回去
                eq_c.equip(item)
                self._log(f"背包已满，无法卸下 {item['icon']}{item['name']}")
                return False
        return False

    def equip_from_backpack(self, bp_idx: int) -> bool:
        """从背包第 bp_idx 件物品装备到身上"""
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        bp_c = self.world.get_component(self.player_eid, BackpackComponent)
        if eq_c is None or bp_c is None:
            return False
        if bp_idx < 0 or bp_idx >= len(bp_c.items):
            return False
        if len(eq_c.equipped) >= eq_c.max_slots:
            return False
        item = bp_c.take(bp_idx)
        if item:
            eq_c.equip(item)
            self._log(f"⬆ {item['icon']}{item['name']} 装备上了")
            if self._notify_fn:
                self._notify_fn("player_state")
            return True
        return False

    def swap_equip_from_backpack(self, equip_idx: int, bp_idx: int) -> bool:
        """用背包第 bp_idx 件物品替换装备栏第 equip_idx 件（旧装备进背包）"""
        eq_c = self.world.get_component(self.player_eid, EquipmentComponent)
        bp_c = self.world.get_component(self.player_eid, BackpackComponent)
        if eq_c is None or bp_c is None:
            return False
        if equip_idx < 0 or equip_idx >= len(eq_c.equipped):
            return False
        if bp_idx < 0 or bp_idx >= len(bp_c.items):
            return False
        new_item = bp_c.take(bp_idx)
        old_item = eq_c.swap(equip_idx, new_item)
        if new_item and old_item:
            bp_c.add(old_item)
            self._log(f"🔄 {old_item['icon']}{old_item['name']}→背包  "
                      f"{new_item['icon']}{new_item['name']}←装备")
            if self._notify_fn:
                self._notify_fn("player_state")
            return True
        return False

    def _reset_game(self) -> None:
        reset_player(self.world, self.player_eid)
        for eid in self._monster_dead_list():
            hp_c = self.world.get_component(eid, HPComponent)
            resp_c = self.world.get_component(eid, RespawnComponent)
            if hp_c:
                hp_c.hp = hp_c.max_hp
                hp_c.alive = True
            if resp_c:
                resp_c.respawn_timer = 0
        if self.boss_eid:
            self.world.destroy_entity(self.boss_eid)
            self.boss_eid = None
            self._boss_wave_active = False
        if self._notify_fn:
            self._notify_fn("player_state")
            self._notify_fn("monster_states")

    def _monster_dead_list(self) -> List[int]:
        return self.monster_eids + ([self.boss_eid] if self.boss_eid else [])
