# -*- coding: utf-8 -*-
"""
SimCore — 引擎无关的模拟内核（M1 抽取）

持有全部模拟状态与逻辑，零 tkinter / pystray / GUI 依赖。
由宿主（GameController 或未来 Godot 桥接层）按固定 dt 调用 update(dt) 推进。

设计约束（见 migration-plan.md M1 + §2）：
  - 本文件的方法主体从 src.app.controllers 的各 Mixin 逐字迁移。
  - 唯一输出通道改写：原 `self.audio.sfx_*(...)`（即时播放）改为
    `self.audio_events.append(("sfx_*", ()))`，由宿主每帧消费并真实播放。
    这样模拟逻辑与音频输出解耦，可在无音频硬件的 headless 环境下确定性运行。
  - _add_log 与现版逐字一致（时间戳前缀格式不变），保证黄金测试可比对。
"""
import os
import sys
import json
import random

from src.sim_core.models.character import (
    Character, Race, CharClass, Party, init_race_class_config,
)
from src.sim_core.models.dungeon import Dungeon, RoomContent
from src.sim_core.services.data_service import DataService
from src.sim_core.services.item_service import ItemService
from src.sim_core.services.combat_service import CombatService
from src.sim_core.services.quest_service import QuestService
from src.sim_core.services.difficulty_service import DifficultyService
from src.sim_core.services.rest_service import RestService
from src.sim_core.services.recipe_service import RecipeService
from src.sim_core.services.event_service import EventService
from src.sim_core.services.town_service import TownService
from src.sim_core.services.world_service import WorldService
from src.sim_core.services.dungeon_service import DungeonService
from src.sim_core.services.potion_service import PotionService
from src.sim_core.services.castle_service import CastleService
from src.sim_core.services.achievement_service import AchievementService
from src.sim_core.services.artifact_service import ArtifactService
from src.sim_core.services.audio_service import AudioService
from src.sim_core.services.hall_of_fame import HallOfFame
from src.sim_core.config.settings import (
    LOOT_INTERVAL, REGION_CHANGE_INTERVAL, ENEMY_RESPAWN_DELAY, MAX_LOG_ENTRIES,
)
from src.config import settings as _settings


class SimCore:
    """模拟内核：状态 + 逻辑。宿主驱动 update(dt)。"""

    def __init__(self, audio=None, save_path=None, load_existing=True, theme=None):
        # ── 服务构造（镜像原 GameController.__init__）──
        self.data_service = DataService()
        # 主题包（P0：异界 DLC）。显式复位单例池主题，避免跨实例泄漏。
        self.theme_name = theme
        self.data_service.set_theme(theme)
        init_race_class_config()  # 零 I/O：仅硬编码回退
        self.item_service = ItemService(data_service=self.data_service)
        self.difficulty_service = DifficultyService()
        self.combat_service = CombatService(self.data_service, self.difficulty_service)
        self.quest_service = QuestService(self.data_service)
        self.rest_service = RestService(data_service=self.data_service)
        self.recipe_service = RecipeService()
        self.event_service = EventService()
        self.town_service = TownService()

        # ── 模拟状态（镜像原 GameController.__init__ 的非 UI 字段）──
        self.character = None
        self.party = None
        self.world = None
        self.current_region = None
        self.current_dungeon = None
        self.current_dungeon_idx = 0
        self.game_time = 0.0
        self.world_seed = 0
        self.paused = False
        self.log_messages = []
        self.max_logs = MAX_LOG_ENTRIES

        # 材料背包（配方合成用）
        self._material_inventory = {}

        self._loot_timer = 0.0
        self._enemy_respawn_timer = 0.0
        self._region_change_timer = 0.0
        self._landmark_discover_timer = 0.0
        self._history_display_timer = 0.0
        self._combat_time = 0.0          # 攻击周期计时
        self._enemy_attack_timer = 0.0   # 怪物攻击间隔计时
        self._combat_start_time = 0.0    # 当前战斗开始时的 game_time（用于 DDA）
        self._game_over = False
        self._death_countdown = 0.0
        self._farm_report_timer = 0.0

        self.world_history_lines = []
        self.show_world_panel = False
        self._discovered_landmarks = []

        # 音频：默认构造 AudioService（headless 下自动禁用实时播放）
        self.audio = audio if audio is not None else AudioService()
        # 事件队列：替代原 self.audio.sfx_*(...) 直接调用（由宿主消费）
        self.audio_events = []

        # 存档路径
        self.save_path = save_path

        # 名人堂：存档同目录独立文件（不影响 save.json schema）
        try:
            hof_path = os.path.join(
                os.path.dirname(os.path.abspath(self._get_save_path())),
                "hall_of_fame.json",
            )
        except Exception:
            hof_path = None
        self.hall_of_fame = HallOfFame(hof_path)

        # 初始化游戏（读档或新建；镜像原 _init_game）
        if load_existing:
            self._init_game()
        else:
            self._init_new_game()

    # ────────────────────────────────────────────────────
    #  主循环（由宿主按固定 dt 驱动）
    # ────────────────────────────────────────────────────

    def update(self, dt):
        """推进一帧模拟。等价于原 GameController._update_game。"""
        if not self.party or not self.current_region:
            return
        if self.paused:
            return

        char = self.character
        self.game_time += dt

        # 更新 DDA 玩家等级（供 UI 渲染查询）
        self.difficulty_service.update_player_level(char.level)

        # 硬核肉鸽：主角阵亡 → 倒计时自动重开
        if self.character.hp <= 0:
            if not self._game_over:
                self._game_over = True
                self._death_countdown = 5.0
                self._add_log(f"☠ {self.character.name} 已阵亡！")
                self._add_log(f"战绩 — Lv.{self.character.level} 击杀:{self.character.kills} "
                              f"死亡:{self.character.deaths} 金币:{self.character.gold}")
                # DDA 反馈回路：阵亡视为高威胁战斗 → 提升回血抑制，
                # 避免 Lv.1 新角色对高回复词缀敌人陷入死亡螺旋。
                try:
                    enemy = self.combat_service.current_enemy or {}
                    combat_duration = max(0, self.game_time - self._combat_start_time)
                    total_damage = self.combat_service.get_total_fight_damage()
                    self.difficulty_service.on_combat_end(
                        combat_duration, False, total_damage,
                        enemy.get("max_hp", 1), enemy.get("regen", 0),
                    )
                except Exception:
                    pass
                # 名人堂结算（跨重开累积 + 破纪录播报，失败不影响重开）
                try:
                    run = {
                        "name": self.character.name,
                        "race": getattr(self.character.race, "race_id", ""),
                        "char_class": getattr(self.character.char_class, "class_id", ""),
                        "level": self.character.level,
                        "kills": self.character.kills,
                        "gold": self.character.gold,
                        "survival_seconds": self.game_time,
                    }
                    for msg in self.hall_of_fame.submit(run):
                        self._add_log(msg)
                except Exception:
                    pass
                self._add_log(f"[系统] {int(self._death_countdown)}秒后自动重开...")
                self.audio_events.append(("sfx_system_fallen", ()))
            # 倒计时
            self._death_countdown -= dt
            remaining = int(self._death_countdown) + 1
            if remaining <= 0:
                self._restart_game()
            return

        # 药水时效
        potion_expired = self.potion_service.tick(dt)
        for msg in potion_expired:
            self._add_log(msg)

        # 农场产出
        farm_coins = self.castle_service.tick_farm(dt)
        if farm_coins > 0:
            self.character.gold += farm_coins
        self._farm_report_timer += dt
        if self._farm_report_timer >= 60.0:
            self._farm_report_timer = 0.0
            if self.castle_service.get_farm_count() > 0:
                self._add_log(f"🏰 农场产出中...({self.castle_service.get_farm_count()}个农场)")

        # 城堡维护
        maintenance_msgs = self.castle_service.tick_maintenance(dt, self.character)
        for msg in maintenance_msgs:
            self._add_log(msg)
            if "自动续期" in msg:
                self.audio_events.append(("sfx_system_gold", ()))
            elif "失去守护" in msg:
                self.audio_events.append(("sfx_system_fallen", ()))

        # 任务系统
        quest_events = self.quest_service.tick(dt, char)
        for event in quest_events:
            self._add_log(event)
            if "完成" in event:
                self.audio_events.append(("sfx_system_quest", ()))

        # 自然回血（已阵亡则跳过）
        if not self.combat_service.in_combat and self.character.hp > 0 and not self._game_over:
            regen = max(1, int(self.character.max_hp * 0.02))
            if int(self.game_time) != int(self.game_time - dt):
                self.character.heal(regen)

        # 战斗 vs 探索
        if self.combat_service.in_combat:
            self._update_combat(dt)
        else:
            self._handle_exploration(dt)

        # ★ 随机事件（旅商/传送门/流浪剑客等）
        self._tick_events(dt)

        # ★ 城镇被动交互（商店刷新/自动购买）
        town_msgs = self.town_service.tick(dt, self.character, self.item_service)
        for msg in town_msgs:
            self._add_log(msg)

        # 地牢房间推进
        self._region_change_timer += dt
        if self._region_change_timer >= REGION_CHANGE_INTERVAL:
            self._region_change_timer = 0.0
            if not self.combat_service.in_combat:
                self._advance_dungeon_room()

        # 地标发现
        self._landmark_discover_timer += dt
        if self._landmark_discover_timer >= 30.0:
            self._landmark_discover_timer = 0.0
            self._try_discover_landmark()

        # 世界历史展示
        self._history_display_timer += dt
        if self._history_display_timer >= 60.0:
            self._history_display_timer = 0.0
            if self.world_history_lines:
                event = random.choice(self.world_history_lines)
                self._add_log(f"[历史] {event}")

        # DDA 长期评估（每 120 秒自动检查一次玩家表现）
        dda_logs = self.difficulty_service.tick(dt)
        for msg in dda_logs:
            self._add_log(msg)

    def _tick_events(self, dt):
        """随机事件触发（旅商/传送门/流浪剑客等）"""
        if self.combat_service.in_combat:
            return  # 战斗中不触发事件

        if not self.event_service.should_trigger(dt):
            return

        # 构建上下文
        char = self.character
        regions = self.world_service.get_all_regions() if self.world_service else []
        prefixes = ["火焰", "冰霜", "闪电", "暗影", "圣光", "剧毒"]
        context = {
            "char_name": char.name if char else "冒险者",
            "current_region": self.current_region.get("name", "未知区域") if self.current_region else "未知区域",
            "random_item": f"一把神秘的武器",
            "random_region": random.choice(regions).get("name", "远方") if regions else "远方",
            "random_element": random.choice(prefixes),
            "gold_cost": random.randint(50, 200),
        }

        event = self.event_service.roll_event(context)
        if event:
            msgs = self.event_service.process_event(event, char, self.item_service)
            for msg in msgs:
                self._add_log(msg)

    # ────────────────────────────────────────────────────
    #  战斗
    # ────────────────────────────────────────────────────

    def _update_combat(self, dt):
        """更新战斗 — 组队版 + 状态机"""
        self._combat_time += dt
        self._enemy_attack_timer += dt
        enemy = self.combat_service.current_enemy

        # 检查敌人是否还活着
        if not enemy or not enemy.get("alive", True):
            self._handle_enemy_defeated(enemy)
            return

        # ★ 僵局检测：记录敌人 HP 变化
        current_hp = enemy.get("hp", 0)
        prev_hp = enemy.get("_fed_hp_snapshot", current_hp)
        enemy["_fed_hp_snapshot"] = current_hp
        enemy["_fed_stuck_time"] = enemy.get("_fed_stuck_time", 0)
        if current_hp >= prev_hp and current_hp >= enemy.get("max_hp", 1) * 0.95:
            # 敌人血量几乎满且没有减少 → 僵局计时
            enemy["_fed_stuck_time"] += dt
        else:
            enemy["_fed_stuck_time"] = 0.0

        stalemate_timeout = self.difficulty_service.STALEMATE_TIMEOUT
        if enemy["_fed_stuck_time"] >= stalemate_timeout:
            enemy_regen = enemy.get("regen", 0)
            self._add_log(f"[反馈] 战斗僵局！敌人回血速度过快，系统已记录并将在下一场战斗中削弱回血效果。")
            # 强制结束僵局战斗（视为逃逸）
            self.combat_service.in_combat = False
            self.combat_service.current_enemy = None
            total_damage = self.combat_service.get_total_fight_damage()
            combat_duration = max(0, self.game_time - self._combat_start_time)
            # report_stalemate 内部记录高威胁 + on_combat_end(False) 叠加触发双倍抑制
            self.difficulty_service.report_stalemate(enemy_regen)
            self.difficulty_service.on_combat_end(
                combat_duration, False, total_damage,
                enemy.get("max_hp", 1), enemy.get("regen", 0),
            )
            # 移除敌人
            dungeon = self.current_dungeon
            if dungeon and dungeon.current_room:
                room = dungeon.current_room
                room.enemies = [e for e in room.enemies if e is not enemy]
                if not room.has_enemies():
                    room.cleared = True
                    self._add_log(f"[房间] 房间已清空!")
            return

        # ★ 回合状态机：处理词缀效果 + 种族技能
        env_tag = ""
        dungeon = self.current_dungeon
        if dungeon and dungeon.current_room:
            env_tag = dungeon.current_room.environment

        # 回合计数：以 1.5s 攻击周期为一回合，从第 1 回合起递增
        # （旧实现误用 _combat_start_time 导致回合数整场恒定，环境叙事与龙息触发异常）
        combat_elapsed = max(0.0, self.game_time - self._combat_start_time)
        round_num = max(1, int(combat_elapsed / 1.5) + 1)
        status_msgs = self.combat_service.tick_status_effects(
            enemy, self.character, env_tag, round_num=round_num, dt=dt,
        )
        for msg in status_msgs:
            self._add_log(msg)
        if not enemy.get("alive", True):
            self._handle_enemy_defeated(enemy)
            return

        # 队伍攻击（约每1.5秒一次）
        if self._combat_time >= 1.5:
            self._combat_time = 0.0
            msgs = self.combat_service.party_attack_cycle(self.party, enemy)
            for msg in msgs:
                self._add_log(msg)
                if "暴击" in msg:
                    self.audio_events.append(("sfx_combat_critical", ()))
                else:
                    self.audio_events.append(("sfx_combat_attack", ()))
            if not enemy.get("alive", True):
                self._handle_enemy_defeated(enemy)
                return

        # 敌人反击 — 公式驱动：
        # T_attack = 3.0 / (1.0 + E_level*0.04 + DDA_mod*2.0)
        interval = self.difficulty_service.get_monster_attack_interval(
            enemy.get("level", 1)
        )
        if self._enemy_attack_timer >= interval:
            self._enemy_attack_timer = 0.0
            msgs = self.combat_service.party_defend_cycle(self.party, enemy, dt)
            for msg in msgs:
                self._add_log(msg)
                if "躲开" in msg:
                    self.audio_events.append(("sfx_combat_dodge", ()))
                elif "伤害" in msg:
                    self.audio_events.append(("sfx_combat_hurt", ()))
                elif "阵亡" in msg:
                    self.audio_events.append(("sfx_system_fallen", ()))

    def _handle_enemy_defeated(self, enemy):
        """处理敌人被击败：按DPS分配经验/金币 + 战利品/药水/成就（含难度调整）"""
        char = self.character

        # ★ 亡语检查（种族技能：亡灵系死亡时造成伤害）
        death_msgs = self.combat_service.on_enemy_death_rattle(enemy, char)
        for msg in death_msgs:
            self._add_log(msg)

        # 任务：击杀敌人（传递 party 以便任务奖励分发给全队）
        for event in self.quest_service.on_kill(enemy, char, self.party):
            self._add_log(event)

        # 敌人模板中的 exp_reward/gold_reward 已由 DDA 服务在生成时缩放完毕
        # 此处直接使用，不再重复应用 DDA 奖励系数
        exp_gained = max(1, enemy.get("exp_reward", 10))
        gold_gained = max(1, enemy.get("gold_reward", 5))

        char.kills += 1
        old_level = char.level
        char.gain_exp(exp_gained)
        char.gold += gold_gained

        self._add_log(f"[击杀] {enemy.get('name', '?')}! +{exp_gained}EXP +{gold_gained}G")
        self.audio_events.append(("sfx_combat_enemy_death", ()))
        if char.level > old_level:
            self._add_log(f"[升级] {char.name} 升到了 Lv.{char.level}")
            self.audio_events.append(("sfx_system_levelup", ()))

        # 战利品掉落（受 DDA 影响）
        loot_chance = 0.5 * self.difficulty_service.get_loot_drop_rate_multiplier()
        if random.random() < loot_chance:
            loot = self.item_service.generate_loot(char.level)
            if loot:
                self._add_log(f"[战利品] 获得: {loot.get_display_name()}")
                self.audio_events.append(("sfx_explore_loot", ()))
                if char.try_auto_equip(loot):
                    self._add_log(f"[装备] {char.name} 已装备: {loot.get_display_name()}")
                    self.audio_events.append(("sfx_explore_equip", ()))

        # 标签驱动材料掉落
        enemy_tags = enemy.get("tags", [])
        enemy_rarity = enemy.get("rarity", "普通")
        if enemy_tags and hasattr(self, '_material_inventory'):
            materials = self.item_service.roll_materials(enemy_tags, enemy_rarity, enemy.get("level", 1))
            for mat_name, mat_value in materials:
                self._material_inventory[mat_name] = self._material_inventory.get(mat_name, 0) + 1
                self._add_log(f"[材料] 从{enemy['name']}获得: {mat_name} (背包: {self._material_inventory[mat_name]}个)")

        # 药水掉落（受 DDA 影响）
        potion_chance = 0.05 * self.difficulty_service.get_loot_drop_rate_multiplier()
        if random.random() < potion_chance:
            pt = self.potion_service.random_potion_type()
            msg = self.potion_service.pickup_potion(pt)
            self._add_log(msg)
            self.audio_events.append(("sfx_explore_potion", ()))

        # 成就检查
        self._check_achievements()

        # ★ 休息：先计算战斗短休，再处理房间清空
        self.rest_service.on_combat_end()
        did_rest = False
        if self.rest_service.should_short_rest_after_combat:
            for msg in self.rest_service.short_rest(self.party):
                self._add_log(msg)
            did_rest = True

        # 检查房间是否清空
        dungeon = self.current_dungeon
        if dungeon and dungeon.current_room:
            room = dungeon.current_room
            room.enemies = [e for e in room.enemies if e is not enemy]
            if not room.has_enemies():
                room.cleared = True
                cleared = dungeon.cleared_rooms
                total = dungeon.total_rooms
                self._add_log(f"[房间] 房间已清空!({cleared}/{total})")
                self.audio_events.append(("sfx_explore_room_clear", ()))
                # 房间清空 → 短休（避免重复：如果战斗短休已触发则跳过）
                if self.rest_service.should_short_rest_on_room_clear() and not did_rest:
                    for msg in self.rest_service.short_rest(self.party):
                        self._add_log(msg)
                self._region_change_timer = REGION_CHANGE_INTERVAL - 2.0

        self.combat_service.in_combat = False
        self.combat_service.current_enemy = None

        # ★ DDA：通知战斗结束，追踪表现（含 DPS 数据用于反馈回路）
        combat_duration = max(0.01, self.game_time - self._combat_start_time)
        total_damage = self.combat_service.get_total_fight_damage()
        enemy_regen = enemy.get("regen", 0) if enemy else 0
        enemy_max_hp = enemy.get("max_hp", 1) if enemy else 1
        self.difficulty_service.on_combat_end(
            combat_duration, True, total_damage, enemy_max_hp, enemy_regen,
        )

    # ────────────────────────────────────────────────────
    #  探索
    # ────────────────────────────────────────────────────

    def _handle_exploration(self, dt):
        self._enemy_respawn_timer += dt
        if self._enemy_respawn_timer >= ENEMY_RESPAWN_DELAY:
            self._enemy_respawn_timer = 0.0
            self._start_combat_from_room()
        self._loot_timer += dt
        if self._loot_timer >= LOOT_INTERVAL:
            self._loot_timer = 0.0
            self._random_loot()

    def _advance_dungeon_room(self):
        dungeon = self.current_dungeon
        if not dungeon:
            return
        if dungeon.current_room and dungeon.current_room.cleared:
            new_room = self.dungeon_service.advance_room(dungeon)
            if new_room is None:
                self._add_log(f"[地牢] {dungeon.name} 已清空！")
                self._on_dungeon_cleared()
            else:
                self._add_log(
                    f"[探索] {dungeon.name} — 进入第{new_room.room_index + 1}间房 "
                    f"[{dungeon.cleared_rooms}/{dungeon.total_rooms}]"
                )
                if new_room.content == RoomContent.CHEST:
                    self._add_log("[探索] 房间里有宝箱...")
                elif new_room.content == RoomContent.ELITE:
                    self._add_log("[探索] ⚡ 精英房！怪物成群出现！")
                    self.audio_events.append(("sfx_explore_elite", ()))

    def _on_dungeon_cleared(self):
        dungeon = self.current_dungeon
        self.audio_events.append(("sfx_explore_dungeon_cleared", ()))
        gold_bonus = dungeon.danger_level * 50
        for member in self.party.members:
            member.gold += gold_bonus
        self._add_log(f"[奖励] 地牢清空，队伍获得 {gold_bonus} 金币")
        self.audio_events.append(("sfx_system_gold", ()))
        artifact = self.artifact_service.try_get_artifact("dungeon_clear")
        if artifact:
            self._add_log(
                f"🏶 获得神器：{artifact.name} — {artifact.get_effect_desc()}"
            )
            self.audio_events.append(("sfx_system_artifact", ()))
        # 地牢清空 → 长休（如战术配置启用）
        if self.rest_service.should_long_rest_on_dungeon_clear():
            for msg in self.rest_service.long_rest(self.party):
                self._add_log(msg)
            # ★ 长休时自动合成（配方系统）
            if hasattr(self, '_material_inventory') and self._material_inventory:
                craft_results = self.recipe_service.auto_craft_all(
                    self._material_inventory,
                    self.item_service,
                    self.character,
                )
                for msg in craft_results:
                    self._add_log(msg)
        self._auto_next_dungeon()

    def _auto_next_dungeon(self):
        region_id = self.current_region["region_id"]
        if self.dungeon_service.check_region_cleared(region_id):
            self._on_region_cleared()
            return
        next_d = self.dungeon_service.get_first_uncleared_dungeon(region_id)
        if next_d:
            self.current_dungeon = next_d
            dungeons = self.dungeon_service.get_region_dungeons(region_id)
            for i, d in enumerate(dungeons):
                if d.dungeon_id == next_d.dungeon_id:
                    self.current_dungeon_idx = i
                    break
            self._add_log(
                f"[地牢] 进入: {next_d.name} [{next_d.total_rooms}间房]"
            )

    def _on_region_cleared(self):
        region_id = self.current_region["region_id"]
        gold_ref = [self.character.gold]
        msg = self.castle_service.try_maintain_castle(self.current_region, gold_ref)
        self.character.gold = gold_ref[0]
        self._add_log(msg)
        if "维护" in msg or "激活" in msg:
            self.audio_events.append(("sfx_system_castle", ()))
        self.castle_service.setup_farm(
            region_id, self.current_region.get("danger_level", 1)
        )
        if not self.castle_service.is_maintained(region_id):
            self._add_log("[入侵] 未守护区域的地牢即将被怪物重新侵占...")
        self._move_to_neighbor_region()

    def _start_combat_from_room(self):
        dungeon = self.current_dungeon
        if not dungeon or not dungeon.current_room:
            return
        room = dungeon.current_room
        if room.content == RoomContent.CHEST and not room.chest_opened:
            room.chest_opened = True
            self._add_log("[宝箱] 打开了宝箱！")
            self.audio_events.append(("sfx_explore_chest", ()))
            for _ in range(2):
                self._random_loot()
            room.cleared = True
            return
        if room.content == RoomContent.POTION_RACK and not room.chest_opened:
            room.chest_opened = True
            pt = self.potion_service.random_potion_type()
            msg = self.potion_service.pickup_potion(pt)
            self._add_log(f"[药水] 发现药水架 — {msg}")
            self.audio_events.append(("sfx_explore_potion", ()))
            room.cleared = True
            return
        if room.enemies and room.has_enemies():
            enemy = next(e for e in room.enemies if e.get("alive", True))
            # ★ DDA：战斗开始时根据队伍强度实时缩放敌人属性
            self.difficulty_service.scale_enemy_in_place(enemy, self.party)
            # ★ 新战斗开始 → 重置 DPS 追踪器
            self.combat_service.reset_damage_tracker()
            self.combat_service.current_enemy = enemy
            self.combat_service.in_combat = True
            self._combat_time = 0.0
            self._enemy_attack_timer = 0.0   # 重置怪物攻击计时
            self._combat_start_time = self.game_time  # ★ 记录战斗开始时间（DDA用）
            self._add_log(f"[战斗] 遭遇: {enemy['name']}")
            self.audio_events.append(("sfx_combat_attack", ()))
        else:
            room.cleared = True

    def _random_loot(self):
        # 探索掉落受 DDA 影响
        loot_chance = 0.2 * self.difficulty_service.get_loot_drop_rate_multiplier()
        if random.random() < loot_chance and self.character:
            loot = self.item_service.generate_loot(self.character.level)
            if loot:
                self._add_log(f"[战利品] 发现: {loot.get_display_name()}")
                if self.character.try_auto_equip(loot):
                    self._add_log(f"[装备] {self.character.name} 已装备: {loot.get_display_name()}")

    def _move_to_neighbor_region(self):
        regions = self.world_service.get_all_regions()
        neighbors = self.current_region.get("neighbors", [])
        candidate_ids = neighbors if neighbors else [r["region_id"] for r in regions]
        if not candidate_ids:
            return
        new_id = random.choice(candidate_ids)
        new_region = self.world_service.get_region_by_id(new_id)
        if not new_region or new_region == self.current_region:
            return
        old_name = self.current_region["name"]
        self.current_region = new_region
        self._add_log(
            f"[旅行] {old_name} → {new_region['name']} (危险:{new_region['danger_level']})"
        )
        self.audio_events.append(("sfx_explore_travel", ()))
        self._check_reinfestation(old_name)
        self.dungeon_service.generate_dungeons_for_region(new_region, self.party)
        dungeons = self.dungeon_service.get_region_dungeons(new_region["region_id"])
        if dungeons:
            self.current_dungeon = dungeons[0]
            self.current_dungeon_idx = 0
            self._add_log(
                f"[地牢] 进入: {self.current_dungeon.name}"
                f" [{self.current_dungeon.total_rooms}间房]"
            )
        desc = self.world_service.get_region_description(new_region["region_id"])
        for line in desc.split("\n")[1:3]:
            self._add_log(f"        {line}")

    def _check_reinfestation(self, region_name: str):
        for rid, _dungeons in list(self.dungeon_service.dungeons.items()):
            region = self.world_service.get_region_by_id(rid)
            if not region:
                continue
            infested = self.dungeon_service.check_infest(rid, self.party)
            if infested:
                self._add_log(
                    f"[入侵] {region['name']}的{infested.name}被怪物重新侵占!"
                    f" 须要折返清理..."
                )
                self.audio_events.append(("sfx_explore_infestation", ()))

    def _try_discover_landmark(self):
        if not self.current_region:
            return
        landmarks = [
            lm for lm in self.world_service.get_landmarks()
            if lm["region_id"] == self.current_region["region_id"]
            and not lm["discovered"]
        ]
        if landmarks and random.random() < 0.2:
            lm = random.choice(landmarks)
            self.world_service.discover_landmark(lm["landmark_id"])
            self._add_log(f"[地标] 发现: {lm['name']}!")
            self._add_log(f"        {lm['description']}")
            self.audio_events.append(("sfx_explore_landmark", ()))

    # ────────────────────────────────────────────────────
    #  初始化 / 重开
    # ────────────────────────────────────────────────────

    def _init_game(self):
        """初始化游戏：读档或新建世界（镜像原 GameInitMixin._init_game）"""
        # ── 加载敌人词缀池（前缀/标签系统）──
        self._load_affix_pool()

        # ── 主题包（异界 DLC）──
        if self.theme_name:
            meta = self.data_service.get_theme_meta()
            display = (meta or {}).get("name", self.theme_name)
            self._add_log(f"[系统] 主题已加载: {display}")

        # 尝试读取存档
        if not self._load_game():
            self._init_new_game()

        # 始终初始化这些服务（存档也需要的运行时服务）
        self.castle_service = CastleService(self.dungeon_service)
        self.achievement_service = AchievementService(self.data_service)
        self.artifact_service = ArtifactService(self.data_service)

        # 音频服务已在 __init__ 中构造（self.audio），此处不再重复创建

        # 设置初始区域并生成地牢
        regions = self.world_service.get_all_regions()
        if regions:
            self.current_region = regions[0]
            self.dungeon_service.generate_dungeons_for_region(self.current_region, self.party)
            self.current_dungeon = self.dungeon_service.get_current_dungeon(
                self.current_region["region_id"], 0
            )
            self.current_dungeon_idx = 0
            self._add_log(f"[旅行] 出生点: {self.current_region['name']}")
            if self.current_dungeon:
                self._add_log(
                    f"[地牢] 进入: {self.current_dungeon.name} "
                    f"[{self.current_dungeon.total_rooms}间房]"
                )

        self._add_log("[系统] 冒险开始！")
        self._add_log(self.world_service.describe_history())

    def _init_new_game(self, race=None, char_class=None, name=None, seed=None):
        """新建世界 + 角色。

        两种调用语境（关键：默认无参开局必须与原逻辑逐字一致，golden 依赖）：
          - 默认开局（SimCore() 构造 → _init_game 调用，全部为 None）：
            仅建 hero/party/world/dungeon/potion；区域 / 运行时服务 / 计时器
            由 _init_game 补全（不在此重置），保证 SimCore() 无参行为不变。
          - 角色创建对话框（用户主动触发，传入 race/char_class/name/seed）：
            做完整重开——重置计时器 / 日志 / 结局态，重建运行时服务并设定出生区域。
        """
        # 是否为"自定义完整重开"（对话框路径）
        custom = not (race is None and char_class is None and name is None and seed is None)

        # DDA 动态难度服务（自动根据表现调整，无需玩家选择）
        self.difficulty_service = DifficultyService()
        self.combat_service.difficulty_service = self.difficulty_service
        self._add_log("[系统] 动态难度已就绪，将根据你的表现自动调整")
        # 重新注入词缀池（因为 DDA 是新实例）
        self._load_affix_pool()

        # 角色参数：未提供则回退默认随机（与迁移前一致）
        races = list(Race)
        classes = list(CharClass)
        if race is None:
            race = random.choice(races)
        if char_class is None:
            char_class = random.choice(classes)
        name_pool = [
            "艾德里安", "赛巴斯蒂安", "奥利维亚", "亚瑟兰",
            "卡斯帕", "克劳斯", "赛林特", "凯尔斯",
        ]
        if name is None:
            name = random.choice(name_pool)

        # 种子：自定义时固定全局 RNG + 世界种子；默认时沿用调用方已设的全局种子（golden 等价）
        if seed is not None:
            random.seed(seed)
            world_seed = seed % 999999 or 1
        else:
            world_seed = random.randint(1, 999999)
        self.world_seed = world_seed

        hero = Character.create(
            name=name, race=race, char_class=char_class, seed=world_seed,
        )
        self.character = hero
        self.party = Party(hero)

        # 生成新世界
        self.world_service = WorldService(seed=world_seed)
        self.world = self.world_service
        self.world_history_lines = self.world_service.history_events

        # 初始化地牢服务（注入 DDA 难度服务，闭环出生即缩放）
        self.dungeon_service = DungeonService(
            self.data_service, self.world_service, self.difficulty_service,
        )
        self.potion_service = PotionService(self.data_service)

        # ── 自定义完整重开：补全计时器 / 日志 / 运行时服务 / 出生区域 ──
        if custom:
            self._game_over = False
            self._death_countdown = 0.0
            self.game_time = 0.0
            self._combat_time = 0.0
            self._enemy_attack_timer = 0.0
            self._combat_start_time = 0.0
            self._loot_timer = 0.0
            self._enemy_respawn_timer = 0.0
            self._region_change_timer = 0.0
            self._landmark_discover_timer = 0.0
            self._history_display_timer = 0.0
            self._farm_report_timer = 0.0
            self.log_messages.clear()

            self.castle_service = CastleService(self.dungeon_service)
            self.achievement_service = AchievementService(self.data_service)
            self.artifact_service = ArtifactService(self.data_service)
            # audio 保持不变（复用现有实例）

            regions = self.world_service.get_all_regions()
            if regions:
                self.current_region = regions[0]
                self.dungeon_service.generate_dungeons_for_region(
                    self.current_region, self.party
                )
                self.current_dungeon = self.dungeon_service.get_current_dungeon(
                    self.current_region["region_id"], 0
                )
                self.current_dungeon_idx = 0
                self._add_log(f"[旅行] 出生点: {self.current_region['name']}")
                if self.current_dungeon:
                    self._add_log(
                        f"[地牢] 进入: {self.current_dungeon.name} "
                        f"[{self.current_dungeon.total_rooms}间房]"
                    )

            self._add_log("[系统] 新的冒险开始了！")
            self._add_log(self.world_service.describe_history())

    def _load_affix_pool(self):
        """加载敌人词缀池（从物品模板的前缀配置中复用）"""
        try:
            item_templates = self.data_service.get_item_templates()
            prefixes = item_templates.get("prefixes", [])
            if prefixes and self.difficulty_service:
                self.difficulty_service.set_affix_pool(prefixes)
                self._add_log(f"[系统] 敌人词缀池已加载 ({len(prefixes)}个词缀)")
        except Exception:
            pass  # 降级：没有词缀池不影响核心游戏

    def _restart_game(self):
        """阵亡后自动重开，不读档，全新世界 + 全新角色"""
        self._game_over = False
        self._death_countdown = 0.0

        # ── 重置所有计时器 ──
        self.game_time = 0.0
        self._combat_time = 0.0
        self._enemy_attack_timer = 0.0
        self._combat_start_time = 0.0
        self._loot_timer = 0.0
        self._enemy_respawn_timer = 0.0
        self._region_change_timer = 0.0
        self._landmark_discover_timer = 0.0
        self._history_display_timer = 0.0
        self._farm_report_timer = 0.0

        # ── 清空日志 ──
        self.log_messages.clear()

        # ── 全新 DDA（继承上世的回血抑制反馈，避免死亡螺旋跨世复发）──
        old_dda = self.difficulty_service
        self.difficulty_service = DifficultyService()
        self.difficulty_service.load_dict(old_dda.to_dict())
        self.combat_service.difficulty_service = self.difficulty_service
        self._load_affix_pool()  # 重新注入词缀池
        self._add_log("[系统] 动态难度已就绪（继承上世反馈）")

        # ── 随机角色 + 全新世界 ──
        races = list(Race)
        classes = list(CharClass)
        race = random.choice(races)
        char_class = random.choice(classes)
        name = random.choice([
            "艾德里安", "赛巴斯蒂安", "奥利维亚", "亚瑟兰",
            "卡斯帕", "克劳斯", "赛林特", "凯尔斯",
        ])
        world_seed = random.randint(1, 999999)
        self.world_seed = world_seed

        hero = Character.create(
            name=name, race=race, char_class=char_class, seed=world_seed,
        )
        self.character = hero
        self.party = Party(hero)

        self.world_service = WorldService(seed=world_seed)
        self.world = self.world_service
        self.world_history_lines = self.world_service.history_events

        # ── 重新初始化运行时服务 ──
        self.dungeon_service = DungeonService(
            self.data_service, self.world_service, self.difficulty_service,
        )
        self.potion_service = PotionService(self.data_service)
        self.castle_service = CastleService(self.dungeon_service)
        self.achievement_service = AchievementService(self.data_service)
        self.artifact_service = ArtifactService(self.data_service)
        # audio 保持不变（复用现有实例）

        # ── 设置初始区域 ──
        regions = self.world_service.get_all_regions()
        if regions:
            self.current_region = regions[0]
            self.dungeon_service.generate_dungeons_for_region(
                self.current_region, self.party
            )
            self.current_dungeon = self.dungeon_service.get_current_dungeon(
                self.current_region["region_id"], 0
            )
            self.current_dungeon_idx = 0
            self._add_log(f"[旅行] 出生点: {self.current_region['name']}")
            if self.current_dungeon:
                self._add_log(
                    f"[地牢] 进入: {self.current_dungeon.name} "
                    f"[{self.current_dungeon.total_rooms}间房]"
                )

        self._add_log("[系统] 新的冒险开始了！")
        self._add_log(self.world_service.describe_history())

    # ────────────────────────────────────────────────────
    #  日志 & 成就
    # ────────────────────────────────────────────────────

    def _add_log(self, msg: str):
        t = int(self.game_time)
        hh, mm, ss = t // 3600, (t % 3600) // 60, t % 60
        ts = f"{hh:02d}:{mm:02d}:{ss:02d}"
        self.log_messages.append(f"[{ts}] {msg}")
        if len(self.log_messages) > self.max_logs:
            self.log_messages = self.log_messages[-self.max_logs:]

    def _check_achievements(self):
        char = self.character
        total_kills = sum(m.kills for m in self.party.members) if self.party else char.kills
        max_level = max((m.level for m in self.party.members), default=char.level) if self.party else char.level
        total_deaths = sum(m.deaths for m in self.party.members) if self.party else char.deaths
        total_quests = sum(m.quests_completed for m in self.party.members) if self.party else char.quests_completed
        checks = [
            ("ACH_KILL_10",    total_kills, None), ("ACH_KILL_100",   total_kills, None),
            ("ACH_KILL_1000",  total_kills, None), ("ACH_KILL_10000", total_kills, None),
            ("ACH_LV10",       max_level, None), ("ACH_LV25",       max_level, None),
            ("ACH_DEATH_5",    total_deaths, None), ("ACH_QUEST_10",   total_quests, None),
            ("ACH_CASTLE_5",   self.castle_service.get_secured_count(), None),
            ("ACH_CASTLE_10",  self.castle_service.get_secured_count(), None),
            ("ACH_ARTIFACT_5", len(self.artifact_service.get_owned_list()), None),
        ]
        for ach_id, progress, _ in checks:
            ach = self.achievement_service.achievements.get(ach_id)
            if not ach or ach.completed:
                continue
            old_progress = ach.progress
            ach.progress = min(progress, ach.target)
            if ach.progress >= ach.target and old_progress < ach.target:
                ach.completed = True
                self.achievement_service._pending_rewards.append({
                    "name": ach.name, "reward_type": ach.reward_type,
                    "reward_value": ach.reward_value,
                })
        rewards = self.achievement_service.get_pending_rewards()
        for reward in rewards:
            self._add_log(f"🏆 成就解锁：{reward['name']}!")
            self.audio_events.append(("sfx_system_achievement", ()))
            self._apply_achievement_reward(reward)

    def _apply_achievement_reward(self, reward: dict):
        rtype = reward["reward_type"]; rval = reward["reward_value"]
        if rtype == "gold":
            for member in self.party.members:
                member.gold += int(rval)
        elif rtype == "xp":
            for member in self.party.get_alive():
                member.gain_exp(int(rval))
        elif rtype == "hp_bonus":
            for member in self.party.members:
                member.max_hp = int(member.max_hp * (1 + rval))
                member.hp = min(member.hp, member.max_hp)

    # ────────────────────────────────────────────────────
    #  存读档（镜像原 GameIOMixin）
    # ────────────────────────────────────────────────────

    def _get_save_dir(self):
        """统一存档目录：始终返回项目根目录下的 data 文件夹"""
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(_settings.BASE_DIR)
        return os.path.join(base, "data")

    def _get_save_path(self):
        """获取存档完整路径（优先使用构造时传入的 save_path）"""
        if self.save_path:
            return self.save_path
        return os.path.join(self._get_save_dir(), "save.json")

    def save_game(self):
        """保存游戏"""
        if not self.character:
            return
        try:
            save_dir = self._get_save_dir()
            os.makedirs(save_dir, exist_ok=True)
            save_path = self._get_save_path()

            # 保存队伍
            party_data = []
            for m in self.party.members:
                party_data.append(m.to_dict())

            data = {
                "character": self.character.to_dict(),
                "party": party_data,
                "game_time": self.game_time,
                "world_seed": self.world_seed,
                "quest_service": self.quest_service.to_dict(),
                "potion_service": self.potion_service.to_dict(),
                "castle_service": self.castle_service.to_dict(),
                "achievement_service": self.achievement_service.to_dict(),
                "artifact_service": self.artifact_service.to_dict(),
                "difficulty_service": self.difficulty_service.to_dict(),  # ★ DDA 状态
                "rest_service": self.rest_service.to_dict(),  # ★ 休息系统状态
                "material_inventory": getattr(self, '_material_inventory', {}),  # ★ 材料背包
                # 地牢进度
                "current_region_id": self.current_region["region_id"] if self.current_region else None,
                "current_dungeon_idx": self.current_dungeon_idx,
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 校验写入完整性
            written_size = os.path.getsize(save_path)
            if written_size < 200:
                self._add_log(f"[系统] 存档异常: 文件仅{written_size}字节, 可能不完整!")
            else:
                self._add_log(f"[系统] 游戏已保存 ({written_size}B) -> {save_path}")
            self.audio_events.append(("sfx_ui_save", ()))
        except Exception as e:
            self._add_log(f"[系统] 保存失败: {e}")

    def _backup_corrupt_save(self, save_path: str, reason: str) -> bool:
        """损坏存档自动备份并引导新建游戏（stay 式不可信存档容错）"""
        import time
        backup = f"{save_path}.corrupt-{int(time.time())}"
        try:
            if os.path.exists(save_path):
                os.replace(save_path, backup)
            self._add_log(
                f"[读档] 存档损坏（{reason}），已备份为 {os.path.basename(backup)}，将创建新游戏"
            )
        except Exception:
            self._add_log(f"[读档] 存档损坏（{reason}），备份失败，将创建新游戏")
        return False

    def _load_game(self):
        """读取存档 — 详细错误日志 + 损坏存档自动备份（stay 式容错）"""
        save_path = self._get_save_path()
        try:
            if not os.path.exists(save_path):
                self._add_log(f"[系统] 未找到存档: {save_path}，将创建新游戏")
                return False

            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # ── 验证关键字段 ──
            if "character" not in data:
                self._add_log("[读档] 存档损坏: 缺少 character 字段")
                return False

            char_data = data["character"]
            if "name" not in char_data or "race" not in char_data or "char_class" not in char_data:
                self._add_log("[读档] 存档损坏: character 字段缺少 name/race/char_class")
                return False

            # ── 恢复角色 ──
            self.character = Character.from_dict(char_data)
            self.game_time = data.get("game_time", 0)
            self.world_seed = data.get("world_seed", 0)

            # ── 恢复队伍 ──
            self.party = Party(self.character)
            party_data = data.get("party", [])
            for i, member_data in enumerate(party_data):
                if i == 0:
                    continue
                companion = Character.from_dict(member_data)
                self.party.add_member(companion)

            # ── 恢复世界 ──
            from src.sim_core.services.world_service import WorldService
            from src.sim_core.services.dungeon_service import DungeonService
            from src.sim_core.services.potion_service import PotionService
            from src.sim_core.services.castle_service import CastleService
            from src.sim_core.services.achievement_service import AchievementService
            from src.sim_core.services.artifact_service import ArtifactService

            self.world_service = WorldService(seed=self.world_seed)
            self.world = self.world_service
            self.world_history_lines = self.world_service.history_events

            # 初始化地牢服务（先恢复 DDA 状态，再注入地牢服务以实现出生即缩放）
            self.dungeon_service = DungeonService(
                self.data_service, self.world_service, self.difficulty_service,
            )
            self.potion_service = PotionService(self.data_service)
            self.castle_service = CastleService(self.dungeon_service)
            self.achievement_service = AchievementService(self.data_service)
            self.artifact_service = ArtifactService(self.data_service)

            # ── 恢复区域与地牢 ──
            regions = self.world_service.get_all_regions()
            saved_region_id = data.get("current_region_id")
            if regions:
                if saved_region_id:
                    region = self.world_service.get_region_by_id(saved_region_id)
                    self.current_region = region if region else regions[0]
                else:
                    self.current_region = regions[0]

                self.dungeon_service.generate_dungeons_for_region(self.current_region, self.party)
                d_idx = data.get("current_dungeon_idx", 0)
                self.current_dungeon_idx = d_idx
                self.current_dungeon = self.dungeon_service.get_current_dungeon(
                    self.current_region["region_id"], d_idx
                )

            # ── 恢复服务状态 ──
            # ★ DDA 必须先恢复（DungeonService 需要它来做出生缩放）
            if "difficulty_service" in data:
                self.difficulty_service.load_dict(data["difficulty_service"])
                self.combat_service.difficulty_service = self.difficulty_service
            if "quest_service" in data:
                self.quest_service.from_dict(
                    data["quest_service"], self.data_service.get_quest_templates()
                )
            if "potion_service" in data:
                self.potion_service.from_dict(data["potion_service"])
            if "castle_service" in data:
                self.castle_service.from_dict(data["castle_service"])
            if "achievement_service" in data:
                self.achievement_service.from_dict(data["achievement_service"])
            if "artifact_service" in data:
                self.artifact_service.from_dict(data["artifact_service"])
            if "rest_service" in data:
                self.rest_service.from_dict(data["rest_service"])

            # 恢复材料背包
            self._material_inventory = data.get("material_inventory", {})

            # 读档后检查角色是否已阵亡（硬核肉鸽）
            if self.character.hp <= 0:
                self._game_over = True
                self._add_log("☠ 读档发现角色已阵亡。游戏结束。")

            self._add_log(f"[系统] 存档已读取: {self.character.name} Lv.{self.character.level}"
                          f" 金币:{self.character.gold}")
            return True

        except FileNotFoundError:
            self._add_log("[系统] 未找到存档文件，将创建新游戏")
            return False
        except json.JSONDecodeError as e:
            return self._backup_corrupt_save(save_path, f"JSON解析失败: {e}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # 写入 crash.log 便于排查
            try:
                with open(os.path.join(self._get_save_dir(), "crash.log"), "w", encoding="utf-8") as f:
                    f.write(f"[LOAD ERROR] {e}\n\n{tb}\n")
            except Exception:
                pass
            return self._backup_corrupt_save(save_path, f"读档异常: {e}")
