"""game.py — 地牢冒险者 (Dungeon Delver)

把 <procgen 源仓> 的 procgen 生成能力，与 <alloy 源仓> 的游戏引擎，
融合成一个*可以真正游玩*的回合制 Roguelike（两者均已内联进本仓）。

引擎整合点（alloy）：
  - world.map_data.MapData        地形字符网格
  - world.item.Item               loot / 武器 / 护甲 / 药水
  - world.game_state.PlayerState  玩家状态
  - systems.simple_combat         SimpleCombat / MobTemplate / MobLibrary（战斗）
  - systems.inventory.Inventory   背包
  - ai.decision.GenericStateMachine  怪物 AI 状态机
  - core.ecs.World/Entity/Component  ECS 实体模型

世界生成（procgen）：
  - generate_dungeon / generate_cave   地牢几何
  - NameGenerator                      怪物名 / 区域名
  - LootTable                          宝箱掉落风味
"""
from __future__ import annotations

import os
import random
import sys

# 让本仓内的 alloy / procgen 包可被 import（自包含，零跨项目耦合）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alloy.core.ecs import World
from alloy.world.game_state import PlayerState
from alloy.systems.simple_combat import SimpleCombat
from alloy.systems.inventory import Inventory, InventoryItem
from fov import compute_fov
from pathfinding import compute_dijkstra, UNREACHABLE, clear_los
import savegame as savegame_mod

# 新增强化模块（成长 / 词缀 / AI Director）
import progression as prog_mod
from progression import (
    PERK_MAP,   # 2026-09-23 修复：779/808 行用到 PERK_MAP 但原导入清单里没有它（选 perk 时 NameError）
    Progression, grant_xp, apply_perk, roll_perk_choices, compute_perk_mods,
)
import affixes as affix_mod
import director as director_mod
from director import Director

# 注意：Position/Health/MobBrain 统一从 entities 导入，
# 避免与 alloy.core.ecs 中的同名类产生「类身份不一致」导致 get() 失效。
from entities import Position, Health, MobBrain, build_catalog, BOSS_ART
from world_gen import generate_floor, WALL, STAIRS
from monster_ai import decide as monster_decide, decide_boss, decide_dijkstra

WALL_ = WALL
STAIRS_ = STAIRS


class Game:
    def __init__(self, seed: int = 20260717, floors: int = 5,
                 autobuild: bool = True):
        self.seed = seed
        self.total_floors = max(1, floors)
        # 让战斗运气也由种子决定（SimpleCombat 使用全局 random）
        random.seed(self.seed)
        self.floor_index = 1

        self.world = World()
        self.catalog = build_catalog()

        self.player = self.world.create_entity("player")
        self.player.add(Position(0, 0))
        self.ps = PlayerState(hp=100, max_hp=100)

        self.inv = Inventory(capacity=24)
        self.gold = 0
        self.equipped_weapon: str | None = None
        self.equipped_armor: str | None = None

        self.logs: list[str] = []
        self.status = "playing"            # playing | battle | won | lost | quit
        self.combat: SimpleCombat | None = None
        self.battle_state = None
        self.battle_mob = None

        self.monsters: list = []
        self.monster_at: dict = {}

        # ── 视野 / 战争迷雾 ──
        self.fov_radius = 9
        self.visible: set = set()          # 当前可见格
        self.explored: set = set()         # 曾经见过（记忆）的格

        # ── 玩家状态异常（中毒 / 灼烧）──
        self.status_effects: list = []

        # ── 成长系统（经验 / 等级 / 升级三选一 perk）──
        self.progression = Progression()
        self.perk_mods: dict = {}          # perk 属性加成累加器
        self.mods: dict = {}               # perk + 装备词缀合并后的有效加成
        self.pending_levels: list = []     # 待处理的升级（队列）
        self.is_auto = False               # 无头演示模式
        self.color = True                  # 终端颜色

        # ── AI Director 动态难度（橡皮筋式调节）──
        self.director = Director()

        # ── 词缀掉落用的独立 RNG（与战斗/生成解耦，保证可复现）──
        self.rng = random.Random((seed * 7919 + 12345) & 0xFFFFFFFF)

        # ── 群聚警觉：本层有怪贴脸则全层警觉（感知半径 +）──
        self.alerted = False
        self.boss_art_shown = False

        self._recompute_mods()

        if autobuild:
            self._build_floor(1)
            self.logs.append(f"你踏入了 {self.floor['region']} 地牢第 1 层……")

    # ──────────────────────────────────────────────────
    #  楼层构建
    # ──────────────────────────────────────────────────
    def _build_floor(self, fi: int) -> None:
        self.boss_art_shown = False
        self.alerted = False
        for m in getattr(self, "monsters", []):
            try:
                self.world.remove_entity(m.eid or m.id)
            except Exception:
                pass
        self.floor_index = fi
        self.floor = generate_floor(self.world, self.seed, fi, self.total_floors,
                                    director=self.director)
        sx, sy = self.floor["start"]
        self.px, self.py = sx, sy
        self.player.get(Position).x = sx
        self.player.get(Position).y = sy
        self.monsters = self.floor["monsters"]
        self.status_effects = []           # 换层清除状态异常
        self._reindex()
        self._update_fov()
        tag = "（BOSS 层！）" if self.floor["is_boss"] else ""
        kind = self.floor.get("gen_kind", "")
        kind_label = {"room": "房间", "cave": "洞穴", "bsp": "地窖"}.get(kind, "")
        extra = f"[{kind_label}] " if kind_label else ""
        self.logs.append(
            f"—— 第 {fi} 层：{extra}{self.floor['region']}"
            f"（{self.floor.get('biome', '')}）地牢{tag}"
        )
        # 沉浸感：生物群系氛围描述 + procgen 生成的战利品传闻
        self.log(f"  {self.floor.get('biome_desc', '')}")
        lf = self.floor.get("loot_flavor") or []
        if lf:
            self.log(f"  📜 传闻此层埋藏：{', '.join(lf)}")

    def _reindex(self) -> None:
        self.monster_at = {}
        for m in self.monsters:
            if m.get(MobBrain).alive:
                p = m.get(Position)
                self.monster_at[(p.x, p.y)] = m

    # ──────────────────────────────────────────────────
    #  视野 / 战争迷雾（递归阴影投射）
    # ──────────────────────────────────────────────────
    def _update_fov(self) -> None:
        """以玩家为中心计算可见格，并合并进已探索记忆。"""
        t = self.floor["terrain"]
        blocked = lambda x, y: not self._walkable(x, y)
        self.visible = compute_fov(self.px, self.py, self.fov_radius,
                                   blocked, t.width, t.height)
        self.explored |= self.visible

    # ──────────────────────────────────────────────────
    #  玩家状态异常（中毒 / 灼烧）
    # ──────────────────────────────────────────────────
    def _add_status(self, kind: str, turns: int, power: int) -> None:
        """叠加状态异常（同类刷新为更强/更久）。"""
        for eff in self.status_effects:
            if eff["kind"] == kind:
                eff["turns"] = max(eff["turns"], turns)
                eff["power"] = max(eff["power"], power)
                return
        self.status_effects.append({"kind": kind, "turns": turns, "power": power})

    def _tick_status(self) -> None:
        """每回合结算玩家状态异常；致死则置 lost。"""
        if not self.status_effects:
            return
        still = []
        for eff in self.status_effects:
            kind, turns, power = eff["kind"], eff["turns"], eff["power"]
            if kind in ("poison", "burn"):
                real = self.ps.adjust_hp(-power)
                label = "灼烧" if kind == "burn" else "中毒"
                self.log(f"☠️ {label}发作，损失 {abs(real)} 点生命")
            eff["turns"] -= 1
            if eff["turns"] > 0:
                still.append(eff)
        self.status_effects = still
        if self.ps.hp <= 0 and self.status in ("playing", "battle"):
            self.status = "lost"
            self.log(self._death_line())

    # ──────────────────────────────────────────────────
    #  属性 / 查询
    # ──────────────────────────────────────────────────
    def weapon_damage(self) -> int:
        base = 2  # 徒手
        if self.equipped_weapon and self.equipped_weapon in self.catalog:
            base = self.catalog[self.equipped_weapon].get_stat("attack")
        return base + int(self.mods.get("attack", 0))

    def armor_val(self) -> int:
        base = 0
        if self.equipped_armor and self.equipped_armor in self.catalog:
            base = self.catalog[self.equipped_armor].get_stat("defense")
        return base + int(self.mods.get("defense", 0))

    # ── 派生战斗属性（来自 perk + 装备词缀）──
    def crit_chance(self) -> float:
        return float(self.mods.get("crit", 0.0))

    def lifesteal(self) -> float:
        return float(self.mods.get("lifesteal", 0.0))

    def special_mult(self) -> float:
        return 1.0 + float(self.mods.get("special", 0.0))

    def damage_reduction(self) -> int:
        return int(self.mods.get("dr", 0))

    def regen_per_turn(self) -> int:
        return int(self.mods.get("regen", 0))

    def weapon_onhit(self) -> str | None:
        """当前武器是否有「命中附加状态」词缀（burn / poison）。"""
        if not self.equipped_weapon:
            return None
        ii = self.inv.get(self.equipped_weapon)
        if not ii:
            return None
        for af in ii.metadata.get("affixes", []):
            if af.get("special") in ("burn", "poison"):
                return af["special"]
        return None

    def thorns(self) -> int:
        """当前护甲的荆棘反弹值。"""
        if not self.equipped_armor:
            return 0
        ii = self.inv.get(self.equipped_armor)
        if not ii:
            return 0
        for af in ii.metadata.get("affixes", []):
            if af.get("special") == "thorns":
                return int(af.get("value", 0))
        return 0

    def _is_wall(self, x: int, y: int) -> bool:
        return not self._walkable(x, y)

    def _los(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        return clear_los(x0, y0, x1, y1, self._is_wall)

    def _recompute_mods(self) -> None:
        """合并 perk 加成与已装备物品的词缀，得到有效 mods，并刷新视野半径。"""
        m = dict(self.perk_mods)
        for slot, iid in (("weapon", self.equipped_weapon),
                          ("armor", self.equipped_armor)):
            if iid and iid in self.catalog:
                ii = self.inv.get(iid)
                affixes_ = ii.metadata.get("affixes", []) if ii else []
                for af in affixes_:
                    if af.get("stat"):
                        m[af["stat"]] = m.get(af["stat"], 0) + af["value"]
        self.mods = m
        self.fov_radius = 9 + int(m.get("fov", 0))

    def _eq_name(self, kind: str) -> str:
        iid = self.equipped_weapon if kind == "weapon" else self.equipped_armor
        return self.catalog[iid].name if iid else "无"

    def _in_bounds(self, x: int, y: int) -> bool:
        return self.floor["terrain"].in_bounds(x, y)

    def _walkable(self, x: int, y: int) -> bool:
        return self._in_bounds(x, y) and self.floor["terrain"].get(x, y) != WALL_

    def _item_at(self, x: int, y: int):
        for it in self.floor["items"]:
            if it["pos"] == (x, y):
                return it
        return None

    def log(self, msg: str) -> None:  # type: ignore[override]
        self.logs.append(msg)
        if len(self.logs) > 200:
            self.logs = self.logs[-150:]

    # 阵亡结语（随机轮换，避免重复枯燥）
    _DEATH_LINES = [
        "你的视野陷入黑暗，地牢又吞没了一名冒险者……",
        "最后一口气消散在潮湿的空气中，传说到此为止。",
        "你跪倒在地，鲜血染红了脚下的石砖……",
        "地牢的回响里，再少了一道活人的脚步声。",
    ]

    def _death_line(self) -> str:
        return random.choice(self._DEATH_LINES)

    # ──────────────────────────────────────────────────
    #  移动 / 拾取 / 地图交互
    # ──────────────────────────────────────────────────
    def move(self, dx: int, dy: int) -> None:
        if self.status != "playing":
            return
        nx, ny = self.px + dx, self.py + dy
        if not self._walkable(nx, ny):
            self.log("前方是墙壁。")
            return
        mob = self.monster_at.get((nx, ny))
        if mob is not None:
            self.enter_battle(mob)
            return
        self.px, self.py = nx, ny
        self.player.get(Position).x = nx
        self.player.get(Position).y = ny
        it = self._item_at(nx, ny)
        if it is not None:
            self._take_item(it)
        # 陷阱 / 灾害地块：踩中扣血并解除（经典 roguelike 危险元素）
        trap_types = self.floor.get("trap_types", {})
        if (nx, ny) in self.floor.get("traps", set()):
            self.floor["traps"].discard((nx, ny))
            ttype = trap_types.get((nx, ny), "spike")
            dmg = max(0, (5 + self.floor_index * 2) - self.damage_reduction())
            real = self.ps.adjust_hp(-dmg)
            if ttype == "lava":
                self._add_status("burn", 3, 2)
                self.log(f"🌋 你踩进熔岩！受到 {abs(real)} 点伤害并灼烧")
            else:
                self.log(f"⚠️ 你触发了尖刺陷阱！受到 {abs(real)} 点伤害")
            if self.ps.hp <= 0:
                self.status = "lost"
                self.director.on_death()
                self.log("你倒在了陷阱之中……")
                return
        self.director.on_step()
        self._tick_regen()
        self._tick_status()
        if self.status != "playing":
            return
        self.monster_turn()
        self._update_fov()

    def _tick_regen(self) -> None:
        """每回合结算玩家再生（来自「再生」perk / 护甲词缀）。"""
        r = self.regen_per_turn()
        if r > 0 and self.ps.hp < self.ps.max_hp:
            self.ps.adjust_hp(r)

    def _take_item(self, it: dict) -> None:
        self.floor["items"].remove(it)
        item = it["item"]
        ii = InventoryItem(
            item_id=it["iid"], name=item.name, item_type=item.item_type,
            description=item.description, usable=item.usable,
            max_stack=99 if item.item_type == "consumable" else 1,
            metadata=it.get("metadata", {}),
        )
        ok, _msg = self.inv.add(ii)
        if ok:
            self.log(f"拾取了 {item.name}")
        else:
            self.floor["items"].append(it)   # 背包满则放回
            self.log("背包已满，无法拾取。")

    def pickup(self) -> None:
        it = self._item_at(self.px, self.py)
        if it is None:
            self.log("脚下没有可拾取的物品。")
            return
        self._take_item(it)

    def descend(self) -> None:
        if self.floor["terrain"].get(self.px, self.py) != STAIRS_:
            self.log("这里没有楼梯。")
            return
        if self.floor_index >= self.total_floors:
            self.log("🏆 你踏过巨龙的骸骨，地牢的诅咒就此解除——"
                     "你的名字将被刻入地牢的传说。")
            self.status = "won"
            self.log("你征服了整座地牢，传说就此诞生！")
            return
        self.director.on_floor_cleared()
        self._build_floor(self.floor_index + 1)

    # ──────────────────────────────────────────────────
    #  战斗（bump-to-battle：撞向怪物进入战斗）
    # ──────────────────────────────────────────────────
    def enter_battle(self, mob) -> None:
        mb = mob.get(MobBrain)
        self.combat = SimpleCombat()
        self.battle_mob = mob
        self.battle_state = self.combat.start(
            mb.template, self.ps.hp,
            armor=self.armor_val() + self.damage_reduction()
        )
        self.status = "battle"
        if mb.template.mob_type == "boss" and not self.boss_art_shown:
            for line in BOSS_ART.get(mb.template.mob_id, []):
                self.log("  " + line)
            self.boss_art_shown = True
            self.log("  传说巨龙睁开通红的双眼，洞窟因它的吐息而震颤……"
                     "这是终焉，也是传奇的起点。")
        self.log(f"⚔️ 遭遇 {mb.name}！(HP {mb.template.hp})")

    def battle_command(self, ch: str) -> None:
        if self.status != "battle" or self.battle_state is None:
            return
        bs = self.battle_state
        c = ch.strip().lower()
        before_hp = bs.player_hp

        if c in ("u", "p", "喝药"):
            # 战中喝药：回复生命，但消耗回合（怪物照常反击）
            if self._has_potion():
                self.use_best_potion()
                bs.player_hp = self.ps.hp
                self._battle_mob_counter(bs)
                self.log("你饮下药水，但露出了破绽……")
            else:
                self.log("你没有可用的药水。")
        elif c in ("4", "z", "s", "special", "特技"):
            # 特技：强力一击，必定触发武器命中效果
            wd = max(1, int(self.weapon_damage() * self.special_mult()))
            msg = self.combat.attack(bs, weapon_damage=wd)
            self._apply_weapon_onhit(self.battle_mob)
            self._tick_mob_status(self.battle_mob, bs)
            self._post_attack(bs)
            self.log(msg.splitlines()[0] if msg else "")
        elif c in ("1", "a", "attack"):
            crit = random.random() < self.crit_chance()
            wd = self.weapon_damage() * (2 if crit else 1)
            msg = self.combat.attack(bs, weapon_damage=wd)
            if crit:
                self.log("💥 暴击！")
            self._apply_weapon_onhit(self.battle_mob)
            self._tick_mob_status(self.battle_mob, bs)
            self._post_attack(bs)
            self.log(msg.splitlines()[0] if msg else "")
        elif c in ("2", "d", "defend"):
            msg = self.combat.defend(bs)
            self._post_attack(bs)
            self.log(msg.splitlines()[0] if msg else "")
        elif c in ("3", "f", "flee"):
            msg = self.combat.flee(bs)
            self.log(msg.splitlines()[0] if msg else "")
        else:
            return

        # 同步玩家血量 + 记录承伤（供 AI Director 调节难度）
        dmg_taken = before_hp - bs.player_hp
        if dmg_taken > 0:
            self.director.on_damage(dmg_taken)
        self.ps.hp = bs.player_hp

        if bs.last_action == "fled":
            self.log(f"你逃离了 {self.battle_mob.get(MobBrain).name}！")
            self._end_battle()
            return
        if bs.player_hp <= 0:
            self.status = "lost"
            self.director.on_death()
            self.log(self._death_line())
            return
        if bs.mob_hp <= 0:
            self._win_battle()
        else:
            self._tick_status()
            if self.status == "lost":
                return

    # ── 战斗辅助结算 ──
    def _post_attack(self, bs) -> None:
        """攻击后结算：吸血 + 荆棘反弹。"""
        if self.lifesteal() > 0 and bs.mob_hp > 0:
            heal = max(0, int(self.weapon_damage() * self.lifesteal()))
            if heal:
                self.ps.adjust_hp(heal)
                bs.player_hp = self.ps.hp
        if self.thorns() > 0 and bs.mob_hp > 0 and bs.last_action in ("attack", "defend"):
            bs.mob_hp -= self.thorns()
            self.log(f"🌵 荆棘反弹 {self.thorns()} 点伤害！")

    def _apply_weapon_onhit(self, mob) -> None:
        onh = self.weapon_onhit()
        if onh and mob.get(MobBrain).alive:
            self._add_mob_status(mob, onh, 3, 2)

    def _add_mob_status(self, mob, kind: str, turns: int, power: int) -> None:
        mb = mob.get(MobBrain)
        for eff in mb.status_effects:
            if eff["kind"] == kind:
                eff["turns"] = max(eff["turns"], turns)
                eff["power"] = max(eff["power"], power)
                return
        mb.status_effects.append({"kind": kind, "turns": turns, "power": power})

    def _tick_mob_status(self, mob, bs) -> None:
        """结算怪物身上的状态异常（中毒/灼烧），直接作用于战斗血量。"""
        mb = mob.get(MobBrain)
        if not mb.status_effects:
            return
        still = []
        for eff in mb.status_effects:
            kind, turns, power = eff["kind"], eff["turns"], eff["power"]
            if kind in ("poison", "burn"):
                real = min(power, bs.mob_hp) if bs.mob_hp > 0 else 0
                bs.mob_hp -= power
                label = "灼烧" if kind == "burn" else "中毒"
                self.log(f"{mb.name} {label}发作，损失 {real} 点生命")
            eff["turns"] -= 1
            if eff["turns"] > 0:
                still.append(eff)
        mb.status_effects = still

    def _battle_mob_counter(self, bs) -> None:
        """战斗中喝药后的怪物反击（复用战斗参数）。"""
        dmg = max(1, bs.mob.damage + random.randint(-1, 1))
        dmg = max(0, dmg - bs.armor)
        bs.player_hp -= dmg
        self.log(f"{bs.mob.name} 造成 {dmg} 点伤害！")

    def _win_battle(self) -> None:
        bs = self.battle_state
        mob = self.battle_mob
        name = mob.get(MobBrain).name

        # 经验与升级（zooz 半随机层：升级后三选一）
        xp = max(1, int(self.combat.get_xp_reward(bs)
                        * (1 + 0.15 * (self.floor_index - 1))))
        levels = grant_xp(self, xp)
        self.pending_levels.extend(levels)
        self.director.on_kill()
        if levels:
            self.log(f"获得 {xp} 经验，升到 {self.progression.level} 级！(待选 perk)")
        else:
            self.log(f"获得 {xp} 经验")

        # 战利品（武器/护甲按层深与幸运掷稀有度 + 词缀）
        luck = int(self.mods.get("rarity", 0)) + self.director.rarity_luck()
        for iid, count in self.combat.generate_drops(bs):
            if iid == "gold":
                self.gold += count
                self.log(f"获得 {count} 金币")
            elif iid in self.catalog:
                item = self.catalog[iid]
                meta = {"rarity": "common", "affixes": []}
                if item.item_type in ("weapon", "armor"):
                    meta = affix_mod.make_loot(
                        self.rng, iid, item.item_type,
                        self.floor_index, luck)
                self.inv.add(InventoryItem(
                    item_id=iid, name=item.name, item_type=item.item_type,
                    description=item.description, usable=item.usable,
                    max_stack=99 if item.item_type == "consumable" else 1,
                    metadata=meta,
                ))
                extra = affix_mod.describe_affixes(meta["affixes"])
                self.log(f"获得 {item.name}{extra} x{count}")
            else:
                self.inv.add(InventoryItem(item_id=iid, name=iid, item_type="material"))
                self.log(f"获得 {iid} x{count}")
        mob.get(MobBrain).alive = False
        self.log(f"💀 你终结了 {name} 的生命。")
        try:
            self.world.remove_entity(mob.eid or mob.id)
        except Exception:
            pass
        if mob in self.monsters:
            self.monsters.remove(mob)
        self._reindex()
        self.log(f"你击败了 {name}！")
        self._end_battle()

    def _end_battle(self) -> None:
        self.status = "playing"
        self.battle_mob = None
        self.battle_state = None
        self.combat = None

    # ──────────────────────────────────────────────────
    #  怪物回合（状态机驱动）
    # ──────────────────────────────────────────────────
    def monster_turn(self) -> None:
        t = self.floor["terrain"]
        W, H = t.width, t.height
        walkable = lambda x, y: self._walkable(x, y)
        # 每回合从玩家位置洪水填充一次 Dijkstra 距离场，全怪共用
        dist_map = compute_dijkstra(self.px, self.py, walkable, W, H)
        occupied = set(self.monster_at.keys())

        # 群聚警觉：本层有怪贴脸则全层警觉（感知半径 +2，群聚追击）
        self.alerted = any(
            (abs(m.get(Position).x - self.px) + abs(m.get(Position).y - self.py)) == 1
            for m in self.monsters if m.get(MobBrain).alive
        )
        sight = self.director.sight_radius() + (2 if self.alerted else 0)
        dmg_mult = self.director.monster_dmg_mult()

        for m in list(self.monsters):
            mb = m.get(MobBrain)
            if not mb.alive:
                continue
            p = m.get(Position)
            h = m.get(Health)
            hp_ratio = h.value / max(1, h.max)
            armor = self.armor_val() + self.damage_reduction()

            # 再生型怪物每回合自我恢复（高血量肉盾）
            if mb.ability == "regen":
                h.value = min(h.max, h.value + 2)

            # —— 远程攻击：射程内且视线无遮挡则发射（不移动）——
            if mb.attack_range > 1:
                cheb = max(abs(p.x - self.px), abs(p.y - self.py))
                if 1 < cheb <= mb.attack_range and self._los(p.x, p.y, self.px, self.py):
                    dmg = max(0, int(mb.template.damage * dmg_mult) - armor)
                    if dmg > 0:
                        self.ps.adjust_hp(-dmg)
                        self.director.on_damage(dmg)
                    label = "箭矢" if mb.ranged_kind == "arrow" else "法术"
                    self.log(f"{mb.name} 射出{label}，造成 {dmg} 点伤害！")
                    if mb.onhit == "burn":
                        self._add_status("burn", 3, 2)
                    elif mb.onhit == "poison":
                        self._add_status("poison", 3, 2)
                    if self.ps.hp <= 0:
                        self.status = "lost"
                        self.director.on_death()
                        self.log(self._death_line())
                        return
                    continue

            # —— Boss 狂暴阶段标记 ——
            if mb.template.mob_type == "boss" and hp_ratio < 0.5:
                mb.enraged = True

            if mb.bt is not None and mb.blackboard is not None:
                php_ratio = self.ps.hp / max(1, self.ps.max_hp)
                act = decide_boss(mb.bt, mb.blackboard, p.x, p.y,
                                  self.px, self.py, hp_ratio, php_ratio,
                                  dist_map, W, H, occupied, sight=sight)
            else:
                wounded = hp_ratio < 0.34
                act = decide_dijkstra(mb.fsm, p.x, p.y, dist_map, W, H,
                                     occupied - {(p.x, p.y)},
                                     (self.px, self.py), wounded, sight=sight)

            if act[0] == "attack" or (
                act[0] == "move" and (p.x + act[1], p.y + act[2]) == (self.px, self.py)
            ):
                mult = 1.5 if mb.enraged else 1.0
                dmg = max(0, int(mb.template.damage * dmg_mult * mult) - armor)
                if dmg > 0:
                    self.ps.adjust_hp(-dmg)
                    self.director.on_damage(dmg)
                self.log(f"{mb.name} 攻击你，造成 {dmg} 点伤害！"
                         + (" 🔥狂暴!" if mb.enraged else ""))
                # 特殊能力结算
                if mb.ability == "poison":
                    self._add_status("poison", 3, 2)
                elif mb.ability == "drain":
                    h.value = min(h.max, h.value + dmg)
                if self.ps.hp <= 0:
                    self.status = "lost"
                    self.director.on_death()
                    self.log(self._death_line())
                    return
            elif act[0] == "move":
                nx, ny = p.x + act[1], p.y + act[2]
                if (self._walkable(nx, ny) and (nx, ny) not in self.monster_at
                        and (nx, ny) != (self.px, self.py)):
                    p.x, p.y = nx, ny
                    self._reindex()
                    occupied = set(self.monster_at.keys())

    # ──────────────────────────────────────────────────
    #  背包 / 装备 / 药水
    # ──────────────────────────────────────────────────
    def _equip(self, iid: str) -> None:
        if iid not in self.catalog:
            return
        kind = self.catalog[iid].item_type
        if kind == "weapon":
            self.equipped_weapon = iid
        elif kind == "armor":
            self.equipped_armor = iid
        self.log(f"装备了 {self.catalog[iid].name}")

    def _equip_best(self) -> None:
        cur_atk = (self.catalog[self.equipped_weapon].get_stat("attack")
                   if self.equipped_weapon else 2)
        best, bestv = None, cur_atk
        for it in self.inv.list_all():
            if it.item_type == "weapon" and it.item_id in self.catalog:
                a = self.catalog[it.item_id].get_stat("attack")
                if a > bestv:
                    bestv, best = a, it.item_id
        if best and best != self.equipped_weapon:
            self._equip(best)

        cur_def = (self.catalog[self.equipped_armor].get_stat("defense")
                   if self.equipped_armor else 0)
        best, bestv = None, cur_def
        for it in self.inv.list_all():
            if it.item_type == "armor" and it.item_id in self.catalog:
                d = self.catalog[it.item_id].get_stat("defense")
                if d > bestv:
                    bestv, best = d, it.item_id
        if best and best != self.equipped_armor:
            self._equip(best)

    def _has_potion(self) -> bool:
        return any(it.item_type == "consumable" for it in self.inv.list_all())

    def use_best_potion(self) -> bool:
        for it in self.inv.list_all():
            if it.item_type == "consumable" and it.item_id in self.catalog:
                item = self.catalog[it.item_id]
                hp = item.get_effect("hp")
                self.ps.adjust_hp(hp)
                self.inv.remove(it.item_id, quantity=1)
                self.log(f"使用 {item.name}，恢复 {hp} 点生命")
                return True
        return False

    def save(self, path: str | None = None) -> None:
        """存档到磁盘（默认 savegame.json）。"""
        if self.status not in ("playing", "battle"):
            self.log("当前状态无法存盘。")
            return
        p = savegame_mod.save_game(self, path)
        self.log(f"已存盘：{p}")

    def show_inventory(self) -> None:
        items = self.inv.list_all()
        if not items:
            self.log("背包是空的。")
            return
        self.log("—— 背包 ——")
        for i, it in enumerate(items, 1):
            tag = "◆" if it.item_id in (self.equipped_weapon, self.equipped_armor) else " "
            rarity = it.metadata.get("rarity", "common")
            color = affix_mod.rarity_color(rarity) if self.color else ""
            reset = "\033[0m" if self.color else ""
            extra = affix_mod.describe_affixes(it.metadata.get("affixes", []))
            self.log(f"{i}. [{tag}] {color}{it.name}{reset}{extra} "
                     f"x{it.quantity} ({it.item_type})")

    # ──────────────────────────────────────────────────
    #  成长：升级三选一（zooz 半随机层设计）
    # ──────────────────────────────────────────────────
    def _do_level_up(self) -> None:
        """交互式升级：弹出 3 个随机 perk 选项，玩家选 1。"""
        level = self.pending_levels.pop(0)
        choices = roll_perk_choices(self.rng, 3)
        self.log(f"⬆️ 升级！你达到 {level} 级，选择一项强化：")
        for i, p in enumerate(choices, 1):
            self.log(f"  {i}. {p['name']} — {p['desc']}")
        ans = input("选择 (1-3): ").strip()
        idx = 0
        try:
            idx = int(ans) - 1
        except ValueError:
            idx = 0
        pick = choices[idx]["id"] if 0 <= idx < len(choices) else choices[0]["id"]
        apply_perk(self, pick)
        self.log(f"你选择了【{PERK_MAP[pick]['name']}】")
        if self.pending_levels:
            self._do_level_up()

    def _auto_level_up(self) -> None:
        """无头模式：按简易启发自动选 perk（残血优先强健，否则堆攻防）。"""
        while self.pending_levels:
            self.pending_levels.pop(0)
            choices = roll_perk_choices(self.rng, 3)
            hp_ratio = self.ps.hp / max(1, self.ps.max_hp)
            pick = choices[0]["id"]
            if hp_ratio < 0.5 and any(p["id"] == "vigor" for p in choices):
                pick = "vigor"
            elif any(p["id"] == "strength" for p in choices):
                pick = "strength"
            elif any(p["id"] == "toughness" for p in choices):
                pick = "toughness"
            apply_perk(self, pick)

    def show_character(self) -> None:
        p = self.progression
        self.log("—— 角色面板 ——")
        self.log(f"等级 {p.level}  (经验 {p.xp}/{p.xp_next})")
        self.log(f"生命 {self.ps.hp}/{self.ps.max_hp}   攻击 {self.weapon_damage()}"
                 f"   防御 {self.armor_val()}   暴击 {int(self.crit_chance() * 100)}%")
        if self.mods.get("lifesteal") or self.mods.get("special") \
                or self.damage_reduction() or self.regen_per_turn():
            self.log(f"吸血 {int(self.lifesteal() * 100)}%   特技x{self.special_mult():.2f}"
                     f"   减伤 {self.damage_reduction()}   再生 {self.regen_per_turn()}/回合")
        perks = [PERK_MAP[i]["name"] for i in p.perks]
        self.log("已选强化：" + ("、".join(perks) if perks else "无"))
        d = self.director
        self.log(f"AI Director：击杀 {d.kills}  死亡 {d.deaths}"
                 f"  挣扎 {d.struggle:.1f}  压制 {d.challenge:.1f}")

    def equip_menu(self) -> None:
        eq = [it for it in self.inv.list_all() if it.item_type in ("weapon", "armor")]
        if not eq:
            self.log("没有可装备的武器/护甲。")
            return
        self.log("—— 可装备 ——")
        for i, it in enumerate(eq, 1):
            self.log(f"{i}. {it.name} ({it.item_type})")
        ans = input("装备哪个? (序号 / 回车取消): ").strip()
        if not ans:
            return
        try:
            idx = int(ans) - 1
        except ValueError:
            self.log("无效序号。")
            return
        if 0 <= idx < len(eq):
            self._equip(eq[idx].item_id)

    def use_menu(self) -> None:
        pots = [it for it in self.inv.list_all() if it.item_type == "consumable"]
        if not pots:
            self.log("没有可用的药水。")
            return
        self.log("—— 药水 ——")
        for i, it in enumerate(pots, 1):
            self.log(f"{i}. {it.name}")
        ans = input("喝哪个? (序号 / 回车取消): ").strip()
        if not ans:
            return
        try:
            idx = int(ans) - 1
        except ValueError:
            self.log("无效序号。")
            return
        if 0 <= idx < len(pots):
            it = pots[idx]
            self.ps.adjust_hp(self.catalog[it.item_id].get_effect("hp"))
            self.inv.remove(it.item_id, quantity=1)
            self.log(f"使用 {it.name}，恢复生命")

    # ──────────────────────────────────────────────────
    #  镇子安全屋：休息 / 购买（打通 procgen generate_town 玩法）
    # ──────────────────────────────────────────────────
    def rest_at_inn(self) -> None:
        if self.status != "playing":
            return
        st = self.floor.get("structures", {})
        if (self.px, self.py) != st.get("inn"):
            self.log("你不在旅馆旁，无法休息。")
            return
        healed = self.ps.max_hp - self.ps.hp
        if healed <= 0:
            self.log("你已精力充沛。")
            return
        self.ps.adjust_hp(healed)
        self.log(f"你在旅馆饱餐休整，恢复 {healed} 点生命。")

    def shop_buy(self) -> None:
        if self.status != "playing":
            return
        st = self.floor.get("structures", {})
        if (self.px, self.py) != st.get("shop"):
            self.log("你不在商店旁，无法购买。")
            return
        offerings = [
            ("minor_potion", 10, "治疗药水"),
            ("major_potion", 25, "强效药水"),
            ("iron_sword", 40, "铁剑"),
            ("chain", 35, "锁子甲"),
        ]
        for iid, price, label in offerings:
            if self.gold < price:
                continue
            if iid in ("minor_potion", "major_potion") and \
               any(it.item_id == iid for it in self.inv.list_all()):
                continue
            self.gold -= price
            item = self.catalog[iid]
            self.inv.add(InventoryItem(
                item_id=iid, name=item.name, item_type=item.item_type,
                description=item.description, usable=item.usable,
                max_stack=99 if item.item_type == "consumable" else 1,
            ))
            self.log(f"你花费 {price} 金币购买了 {label}。")
            return
        self.log("金币不足，或已购齐基础装备。")

    # ──────────────────────────────────────────────────
    #  指令分发
    # ──────────────────────────────────────────────────
    def handle(self, cmd: str) -> None:
        if self.status != "playing":
            return
        # 有升级待处理时，优先进入三选一（不消耗移动）
        if self.pending_levels:
            self._do_level_up()
            return
        c = cmd.strip().lower()
        if c in ("w", "k", "up", "上"):
            self.move(0, -1)
        elif c in ("s", "j", "down", "下"):
            self.move(0, 1)
        elif c in ("a", "h", "left", "左"):
            self.move(-1, 0)
        elif c in ("d", "l", "right", "右"):
            self.move(1, 0)
        elif c == "g":
            self.pickup()
        elif c == "e":
            self.equip_menu()
        elif c == "u":
            self.use_menu()
        elif c == "c":
            self.show_character()
        elif c == "i":
            self.show_inventory()
        elif c == "r":
            self.rest_at_inn()
        elif c == "b":
            self.shop_buy()
        elif c in (">", "downstairs", "下层"):
            self.descend()
        elif c in ("s", "save", "存盘"):
            self.save()
        elif c in ("?", "help"):
            for line in self.help_text().splitlines():
                self.log(line)
        elif c in ("q", "quit", "exit"):
            self.status = "quit"
        else:
            self.log("未知命令，输入 ? 查看帮助")

    def help_text(self) -> str:
        return (
            "【操作帮助】\n"
            "  移动：W/A/S/D（也支持 H/J/K/L 或 上/下/左/右）\n"
            "  G 拾取    E 装备    U 喝药水    I 背包    C 角色面板\n"
            "  R 旅馆休息(回血)  B 商店购买(花金币)   > 在楼梯处下层\n"
            "  S 存盘    ? 帮助    Q 退出\n"
            "  撞向怪物即进入战斗：1 攻击 / 2 防御 / 3 逃跑 / 4 特技(强击)\n"
            "  战斗中也可按 U 喝药；升级时三选一强化自身\n"
            "  视野有限（战争迷雾），^ 尖刺 / ~ 熔岩，集镇(H=旅馆 ¥=商店)可休整补给；\n"
            "  目标：击败最终 Boss（巨龙），活着通关。"
        )

    # ──────────────────────────────────────────────────
    #  渲染
    # ──────────────────────────────────────────────────
    def render(self) -> str:
        t = self.floor["terrain"]
        mat = self.monster_at
        iat = {it["pos"]: it for it in self.floor["items"]}
        structs = self.floor.get("structures", {})
        struct_pos = {pos: ("H" if k == "inn" else "¥")
                      for k, pos in structs.items()}
        traps = self.floor.get("traps", set())
        trap_types = self.floor.get("trap_types", {})

        def col(ch, c):
            return f"{c}{ch}\033[0m" if self.color else ch

        rows = ["╔" + "═" * t.width + "╗"]
        for r in range(t.height):
            line = []
            for c in range(t.width):
                if (c, r) == (self.px, self.py):
                    ch = col("@", "\033[1;33m")
                elif (c, r) in self.visible:
                    if (c, r) in mat:
                        ch = mat[(c, r)].get(MobBrain).template.icon
                    elif (c, r) in iat:
                        rarity = iat[(c, r)].get("metadata", {}).get("rarity", "common")
                        ch = col("$", affix_mod.rarity_color(rarity))
                    elif (c, r) in struct_pos:
                        ch = struct_pos[(c, r)]
                    elif (c, r) in traps:
                        ch = "~" if trap_types.get((c, r), "spike") == "lava" else "^"
                    else:
                        ch = t.get(c, r)
                elif (c, r) in self.explored:
                    # 记忆：显示地形与记得的陷阱，但不显示怪物/物品
                    if (c, r) in traps:
                        ch = "~" if trap_types.get((c, r), "spike") == "lava" else "^"
                    else:
                        ch = t.get(c, r)
                else:
                    ch = " "          # 战争迷雾：未探索
                line.append(ch)
            rows.append("║" + "".join(line) + "║")
        rows.append("╚" + "═" * t.width + "╝")
        board = "\n".join(rows)

        biome = self.floor.get("biome", "")
        explored_pct = int(100 * len(self.explored) / max(1, t.width * t.height))
        hud = (f"第 {self.floor_index}/{self.total_floors} 层 · {self.floor['region']}"
               f"（{biome}）地牢   "
               f"HP {self.ps.hp}/{self.ps.max_hp}   金币 {self.gold}   "
               f"武器 {self._eq_label('weapon')}   护甲 {self._eq_label('armor')}   "
               f"背包 {len(self.inv.list_all())}   探索 {explored_pct}%")

        if self.status_effects:
            effs = " ".join(
                f"{'中毒' if e['kind']=='poison' else '灼烧'}{e['turns']}"
                for e in self.status_effects)
            hud += f"   [异常: {effs}]"

        if self.status == "battle" and self.battle_mob is not None:
            mb = self.battle_mob.get(MobBrain)
            bs = self.battle_state
            hud += (f"\n⚔ 对战 {mb.name}  HP {bs.mob_hp}/{bs.mob_max_hp}"
                    f"   你 {bs.player_hp}/{self.ps.max_hp}")
            ctrl = "战斗：1 攻击 · 2 防御 · 3 逃跑 · 4 特技 · U 喝药"
        else:
            ctrl = ("移动 W/A/S/D · 拾取 G · 装备 E · 喝药 U · 背包 I · 面板 C · 下层 > · 存盘 S · 帮助 ? · 退出 Q")

        logblock = "\n".join("» " + m for m in self.logs[-5:])
        return f"{board}\n{hud}\n{ctrl}\n{logblock}\n{self._render_minimap()}"

    def _eq_label(self, kind: str) -> str:
        """返回带稀有度配色的已装备物品名（HUD 用）。"""
        iid = self.equipped_weapon if kind == "weapon" else self.equipped_armor
        if not iid:
            return "无"
        name = self.catalog[iid].name
        if self.color:
            ii = self.inv.get(iid)
            rarity = ii.metadata.get("rarity", "common") if ii else "common"
            return f"{affix_mod.rarity_color(rarity)}{name}\033[0m"
        return name

    def _render_minimap(self) -> str:
        """紧凑小地图：以 2x2 降采样展示已探索区域。"""
        t = self.floor["terrain"]
        step = 2
        item_pos = {it["pos"] for it in self.floor["items"]}
        lines = ["—— 小地图 ——"]
        for r in range(0, t.height, step):
            row = []
            for c in range(0, t.width, step):
                if (c, r) == (self.px, self.py):
                    row.append("@")
                elif (c, r) in self.visible and (c, r) in self.monster_at:
                    row.append("m")
                elif (c, r) in self.visible and (c, r) in item_pos:
                    row.append("$")
                elif (c, r) in self.explored:
                    row.append("#" if t.get(c, r) == WALL_ else ".")
                else:
                    row.append(" ")
            lines.append("".join(row))
        return "\n".join(lines)

    # ──────────────────────────────────────────────────
    #  运行：交互模式
    # ──────────────────────────────────────────────────
    def run_interactive(self) -> None:
        print(self.help_text())
        print()
        while self.status in ("playing", "battle"):
            print(self.render())
            print()
            if self.status == "battle":
                cmd = input("战斗> ").strip()
                self.battle_command(cmd)
            else:
                cmd = input("> ").strip()
                self.handle(cmd)
            if self.status == "quit":
                break
        print()
        if self.status == "won":
            print("🏆 通关！你成为了地牢的传奇冒险者。")
        elif self.status == "lost":
            print("💀 你死在了地牢深处。冒险者，下次好运。")
        else:
            print("已退出。")

    # ──────────────────────────────────────────────────
    #  BFS 寻路（怪物格视为可通行）
    # ──────────────────────────────────────────────────
    def _bfs_step(self, tx: int, ty: int):
        """返回从玩家当前位置朝 (tx,ty) 的下一步方向；无路返回 None。"""
        from collections import deque

        start = (self.px, self.py)
        if start == (tx, ty):
            return None
        q: deque = deque([start])
        prev = {start: None}
        while q:
            cx, cy = q.popleft()
            if (cx, cy) == (tx, ty):
                break
            for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + ddx, cy + ddy
                if (nx, ny) in prev:
                    continue
                if not self._walkable(nx, ny):
                    continue
                prev[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
        if (tx, ty) not in prev:
            return None
        node = (tx, ty)
        while prev[node] != start:
            node = prev[node]
        return (node[0] - self.px, node[1] - self.py)

    # ──────────────────────────────────────────────────
    #  运行：无头自动演示（用于自检 / CI）
    # ──────────────────────────────────────────────────
    def run_auto(self, max_steps: int = 4000):
        self.logs.append(f"自动演示开始：种子 {self.seed}，共 {self.total_floors} 层")
        steps = 0
        skip_items: set[tuple[int, int]] = set()   # 背包满而捡不起的物品，避免原地死循环
        while self.status in ("playing", "battle") and steps < max_steps:
            steps += 1
            # 待处理升级：无头模式自动选 perk
            if self.pending_levels:
                self._auto_level_up()
            if self.status == "battle":
                if self.ps.hp < self.ps.max_hp * 0.35 and self._has_potion():
                    self.use_best_potion()
                # 血量充裕且面对 Boss/硬怪时偶尔用特技（强击）
                use_special = (
                    self.ps.hp > self.ps.max_hp * 0.6
                    and self.battle_mob is not None
                    and self.battle_mob.get(MobBrain).template.hp >= 30
                )
                self.battle_command("4" if use_special else "1")
                continue

            # 地图模式：先回血、再装备、再拾取
            if self.ps.hp < self.ps.max_hp * 0.4 and self._has_potion():
                self.use_best_potion()
                continue
            self._equip_best()
            here_it = self._item_at(self.px, self.py)
            if here_it is not None and here_it["pos"] not in skip_items:
                self.pickup()
                if self._item_at(self.px, self.py) is here_it:
                    skip_items.add(here_it["pos"])   # 拾取失败（背包满）→ 拉黑
                else:
                    continue

            W = self.floor["terrain"].width
            H = self.floor["terrain"].height
            traps = self.floor.get("traps", set())
            walk = lambda x, y: self._walkable(x, y)   # noqa: E731
            sx, sy = self.floor["stairs"]

            # 目标选择：装备/药水直接决定生还率，先把本层可达战利品顺路收干净再下楼。
            # 第一次距离场量「玩家→各物品」找最近目标，第二次用于导航。
            target = (sx, sy)
            loot = [it for it in self.floor["items"] if it["pos"] not in skip_items]
            if loot:
                from_me = compute_dijkstra(self.px, self.py, walk, W, H)
                nearest, nd = None, UNREACHABLE
                for it in loot:
                    ix, iy = it["pos"]
                    d = from_me[iy][ix]
                    if d < nd:
                        nd, nearest = d, (ix, iy)
                if nearest is not None and nd < UNREACHABLE:
                    target = nearest
            if target == (self.px, self.py):
                target = (sx, sy)

            if target == (sx, sy) and \
                    self.floor["terrain"].get(self.px, self.py) == STAIRS_:
                self.descend()
                continue

            dist = compute_dijkstra(target[0], target[1], walk, W, H)
            here = dist[self.py][self.px]
            dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

            def pick(allow_trap: bool, allow_mob: bool):
                """在四邻中挑一个严格下坡的格子；按容忍度分档。"""
                bstep, bd = None, here
                for dx, dy in dirs:
                    nx, ny = self.px + dx, self.py + dy
                    if not self._walkable(nx, ny):
                        continue
                    if not allow_mob and (nx, ny) in self.monster_at:
                        continue
                    if not allow_trap and (nx, ny) in traps:
                        continue
                    d = dist[ny][nx]
                    if d < bd:
                        bd, bstep = d, (dx, dy)
                return bstep

            # 三档退让：① 既不踩陷阱也不撞怪 ② 允许踩陷阱 ③ 允许撞怪（进入战斗）
            best_step = pick(False, False) or pick(True, False) or pick(True, True)
            # ④ 距离场彻底无下坡（被围死/孤岛）→ 回退到把怪视作可通行的 BFS
            if best_step is None:
                best_step = self._bfs_step(*target)
            if best_step is None and target != (sx, sy):
                best_step = self._bfs_step(sx, sy)   # 物品够不着就直奔楼梯
            if best_step is None:
                break
            self.move(best_step[0], best_step[1])
        self.logs.append(
            f"自动演示结束：状态={self.status}，步数={steps}，"
            f"到达第{self.floor_index}层，金币{self.gold}，"
            f"背包{len(self.inv.list_all())}"
        )
        return self.status
