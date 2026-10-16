"""游戏主 ViewModel — 连接 Model 和 View 的桥梁（完整版）"""
import os
import tkinter as tk
import random
import time
from typing import Optional, Callable

from data import ConfigLoader, SaveManager
from model import (
    Character, Enemy, Item, Vehicle, NPC, Skill,
    GameState, GameData, Direction, QuestTrack, QuestManager,
    BattleEngine, MapManager, InfiniteTerrain, BountyManager, ModShop,
)


class GameViewModel:
    """游戏 ViewModel：持有 GameData、暴露 Observable 属性、处理命令"""

    def __init__(self, config_loader):
        self.config = config_loader
        self.data = GameData()
        self.data.config = config_loader

        # 存档目录：配置文件所在目录下的 saves/
        config_dir = os.path.dirname(os.path.abspath(config_loader.excel_path))
        self.save_manager = SaveManager(os.path.join(config_dir, "saves"))

        # ── Observable 属性（View 绑定这些） ──
        self.display_text = tk.StringVar(value="")
        self.player_name_text = tk.StringVar(value="")
        self.stats_text = tk.StringVar(value="")
        self.vehicle_text = tk.StringVar(value="战车: 无")
        self.log_text = tk.StringVar(value="")
        self.battle_text = tk.StringVar(value="")
        self.battle_visible = tk.BooleanVar(value=False)
        self.state_text = tk.StringVar(value="MENU")
        self.skill_visible = tk.BooleanVar(value=False)

        # ── 回调 ──
        self.on_display_update: Optional[Callable] = None
        self.on_battle_show: Optional[Callable] = None
        self.on_battle_hide: Optional[Callable] = None
        self.on_game_over: Optional[Callable] = None
        self.on_state_changed: Optional[Callable] = None
        self.on_skill_panel_changed: Optional[Callable] = None

        self._last_update = time.time()
        self._running = False

    # ═══════════════════════════════════════════════════
    # 初始化
    # ═══════════════════════════════════════════════════

    def init_new_game(self, class_id: int = 1):
        """初始化新游戏（class_id：1=猎人 2=机械师 3=战士）"""
        self.data = GameData()
        self.data.config = self.config
        self.data.player = Character("雷班纳", 100, 100, 15, 8, 12)
        self.data.player.class_id = class_id
        self.data.player.class_data = self.config.get_class_by_id(class_id)
        self.data.gold = 500
        self.data.player_x = 10
        self.data.player_y = 10
        self.data.inventory = []
        self.data.vehicles = []
        self.data.active_quests = []
        self.data.completed_quests = []
        self.data.quest_progress = []
        self.data.game_time = 0.0

        # 初始技能（只送解锁等级 ≤ 1 的）
        for skill_data in self.config.skills.values():
            if skill_data.unlock_level <= 1:
                self.data.player.learn_skill(Skill(skill_data))

        # 初始物品
        for item_data in self.config.get_starting_items():
            self.data.inventory.append(Item(item_data))

        # 初始战车
        if 1 in self.config.vehicles:
            v = Vehicle(self.config.vehicles[1], self.config)
            self.data.vehicles.append(v)
            self.data.current_vehicle = v
            self.data.player.vehicle = v

        # 地图
        MapManager.create_map(self.data, self.config.maps, self.config.npcs)

        self.data.add_log("欢迎来到重装机兵的世界！")

        # 初始任务
        for quest in self.config.quests.values():
            self.data.active_quests.append(quest)
            track = QuestTrack(quest)
            self.data.quest_progress.append(track)
            self.data.add_log(f"接到任务: {quest.name}")

        self.data.state = GameState.WORLD
        QuestManager.track_explore_map(self.data, self.data.current_map_id)
        self._notify_state()

    def start_game_loop(self, root: tk.Tk, interval_ms: int = 100):
        """启动游戏循环"""
        self._running = True
        self._last_update = time.time()
        self._tick(root, interval_ms)

    def _tick(self, root: tk.Tk, interval_ms: int):
        if not self._running:
            return
        now = time.time()
        delta = now - self._last_update
        self._last_update = now
        self.data.game_time += delta

        # 随机遇敌（使用地图遭遇率；迷彩条生效期屏蔽）
        if self.data.state == GameState.WORLD:
            if self.data.camouflage_steps <= 0:
                enc_rate = self._get_encounter_rate()
                if random.random() < enc_rate * 0.05:  # 每 tick 概率 = rate * 0.05
                    self._random_encounter()

        # 刷新显示
        self._refresh_all()
        root.after(interval_ms, lambda: self._tick(root, interval_ms))

    def _get_encounter_rate(self) -> float:
        """获取当前地图的遭遇率"""
        mid = self.data.current_map_id
        if mid in self.config.maps:
            return self.config.maps[mid].encounter_rate
        return 1.0  # 默认满遇敌

    # ═══════════════════════════════════════════════════
    # 显示刷新
    # ═══════════════════════════════════════════════════

    def _check_skill_unlocks(self):
        """按等级解锁技能（幂等：已学会的不会重复学/重复提示）

        职业限定技能只有对应职业可学（class_id 0=全职业）。
        """
        player = self.data.player
        if not player:
            return
        known_ids = [s.id for s in player.skills]
        for skill_data in self.config.skills.values():
            if skill_data.id in known_ids:
                continue
            if skill_data.unlock_level > player.level:
                continue
            if skill_data.class_id not in (0, player.class_id):
                continue
            player.learn_skill(Skill(skill_data))
            self.data.add_log(f"学会了新技能: {skill_data.name}！")

    def _refresh_all(self):
        """刷新所有 Observable 属性"""
        d = self.data

        # 技能解锁检查（升级后自动学会新技能）
        self._check_skill_unlocks()

        # 玩家信息
        self.player_name_text.set(f"{d.player.name} Lv.{d.player.level}" if d.player else "")
        if d.player:
            self.stats_text.set(
                f"HP: {d.player.hp}/{d.player.max_hp}\n"
                f"攻击: {d.player.attack}  防御: {d.player.defense}\n"
                f"速度: {d.player.speed}  金币: {d.gold}"
            )

        # 战车信息
        if d.current_vehicle:
            v = d.current_vehicle
            overweight = " [超重!]" if v.is_overweight() else ""
            self.vehicle_text.set(
                f"战车: {v.name}{overweight}\n"
                f"HP: {v.hp}/{v.max_hp}  装甲片: {v.armor_plates}/{v.max_plates}\n"
                f"燃料: {int(v.fuel)}/{int(v.max_fuel)}  载重: {v.total_weight()}t/{int(v.load_capacity())}t\n"
                f"底盘: {v.chassis.name}  引擎: {v.engine.name}\n"
                f"{v.weapon_summary()}"
            )
        else:
            self.vehicle_text.set("战车: 无")

        # 日志
        self.log_text.set("\n".join(d.get_recent_logs(5)))

        # 状态
        self.state_text.set(d.state.name)

        # 主显示文本
        self._render_display()

        # 战斗面板
        self.battle_visible.set(d.state == GameState.BATTLE)

        # 技能面板
        self.skill_visible.set(
            d.state == GameState.BATTLE and len(d.player.skills) > 0
        )

    def _render_display(self):
        """渲染主显示区域文本"""
        d = self.data
        renderers = {
            GameState.MENU: self._render_menu,
            GameState.WORLD: self._render_world,
            GameState.BATTLE: self._render_battle,
            GameState.INVENTORY: self._render_inventory,
            GameState.TOWN: self._render_town,
            GameState.SHOP: self._render_shop,
            GameState.DIALOG: self._render_dialog,
            GameState.BOUNTY: self._render_bounty_board,
            GameState.GARAGE: self._render_garage,
            GameState.ENGINE_SHOP: self._render_engine_shop,
        }
        renderer = renderers.get(d.state, lambda: "")
        self.display_text.set(renderer())

    # ── 各状态渲染 ──

    def _render_menu(self) -> str:
        return (
            "\n"
            "        ╔══════════════════════════════════════════════════════╗\n"
            "        ║                 重装机兵同人游戏                     ║\n"
            "        ║               Metal Max Fan Game                     ║\n"
            "        ╚══════════════════════════════════════════════════════╝\n"
            "\n\n"
            "        1. 开始新游戏\n"
            "        2. 继续游戏\n"
            "        3. 任务日志\n"
            "        4. 退出游戏\n"
            "\n\n        按对应数字键选择..."
        )

    def _render_world(self) -> str:
        d = self.data
        return MapManager.get_viewport(d, self.config.npcs)

    def _render_battle(self) -> str:
        enemy = self.data.current_enemy
        if not enemy:
            return "没有敌人！\n"
        desc = enemy.data.description.strip() if enemy.data.description else ""
        desc_line = f"        ║  {desc[:46]:^46}║\n" if desc else ""

        # 乘战车作战时显示战车状态
        vehicle_line = ""
        vehicle = self.data.player.vehicle
        on_foot = self.data.player.combat_on_foot
        if vehicle is not None and vehicle.is_alive() and not on_foot:
            vehicle_line = (
                f"        ║  战车: {vehicle.name} "
                f"HP: {vehicle.hp}/{vehicle.max_hp}"
                f"  燃料: {int(vehicle.fuel)}/{int(vehicle.max_fuel):<20}║\n"
            )
        mode = "步行" if on_foot else ("乘战车" if vehicle is not None else "步行")

        return (
            f"\n"
            f"        ╔══════════════════════════════════════════════════════╗\n"
            f"        ║                     战 斗                           ║\n"
            f"        ╠══════════════════════════════════════════════════════╣\n"
            f"        ║  形态: {mode:<44}║\n"
            f"        ║                                                      ║\n"
            f"        ║  {enemy.name:^20}                                    ║\n"
            f"        ║  HP: {enemy.hp:>3}/{enemy.max_hp:<3}                                      ║\n"
            f"{desc_line}"
            f"        ║                                                      ║\n"
            f"        ║              VS                                      ║\n"
            f"        ║                                                      ║\n"
            f"{vehicle_line}"
            f"        ║  {self.data.player.name:^20}                                    ║\n"
            f"        ║  HP: {self.data.player.hp:>3}/{self.data.player.max_hp:<3}                                      ║\n"
            f"        ║                                                      ║\n"
            f"        ╚══════════════════════════════════════════════════════╝\n"
        )

    def _render_inventory(self) -> str:
        d = self.data
        lines = ["=== 物品栏 ===\n"]
        if not d.inventory:
            lines.append("物品栏是空的。\n")
        else:
            for i, item in enumerate(d.inventory):
                usable = "✓" if item.usable_in_battle else " "
                kind = "装备" if getattr(item.data, "is_equipment", False) else "使用"
                lines.append(f"{i+1}. [{usable}] {item.name:15} - {item.description}\n")
                lines.append(f"    类型: {item.type}, 效果: {item.effect_value}（按 {i+1} {kind}）\n\n")
        # 已装备列表（序号续排在物品栏之后，按对应数字卸下）
        equipped = d.player.equipped_slots()
        if equipped:
            lines.append("── 已装备 ──\n")
            for j, (slot, item) in enumerate(equipped):
                num = len(d.inventory) + j + 1
                lines.append(f"{num}. [E] [{slot}] {item.name:15} - 效果: {item.effect_value}（按 {num} 卸下）\n")
        lines.append("\n按数字键使用/装备/卸下，按ESC返回游戏。")
        return "".join(lines)

    def _render_town(self) -> str:
        return (
            "=== 城镇 ===\n\n"
            "欢迎来到城镇！\n\n"
            "1. 商店\n"
            "2. 战车店（改造）\n"
            "3. 旅馆\n"
            "4. 修理店\n"
            "5. 悬赏榜\n"
            "6. 离开城镇\n\n"
            "请选择选项..."
        )

    def _render_garage(self) -> str:
        """战车改造店菜单"""
        d = self.data
        v = d.current_vehicle
        if v is None:
            return "=== 战车改造店 ===\n\n你没有战车。\n"
        lines = [
            "=== 战车改造店 ===\n\n",
            f"当前战车: {v.name}（底盘 {v.chassis.name} / 引擎 {v.engine.name}）\n",
            f"底盘防御: {v.chassis.defense + v.chassis_defense_bonus}"
            f"/{v.chassis.defense_max}   装甲片: {v.armor_plates}/{v.max_plates}\n\n",
            f"1. 开主炮孔 [{v.extra_main_slots}/{ModShop.MAIN_CAP}]"
            f"（{ModShop._cost_text(ModShop.hole_cost(v, '主炮'))}）\n",
            f"2. 开副炮孔 [{v.extra_sub_slots}/{ModShop.SUB_CAP}]"
            f"（{ModShop._cost_text(ModShop.hole_cost(v, '副炮'))}）\n",
            f"3. 开SE孔 [{v.extra_se_slots}/{ModShop.SE_CAP}]"
            f"（{ModShop._cost_text(ModShop.hole_cost(v, 'SE'))}）\n",
            f"4. 底盘防御强化 +{ModShop.DEF_STEP}"
            f"（{ModShop._cost_text(ModShop.defense_cost(v))}）\n",
            f"5. 装甲片扩容 +{ModShop.PLATE_STEP}"
            f"（{ModShop.plate_cost(v)}G）\n",
            "6. 更换引擎\n",
            "7. 离开\n\n",
            "按数字键选择改造项目...",
        ]
        return "".join(lines)

    def _render_engine_shop(self) -> str:
        """引擎更换列表"""
        d = self.data
        v = d.current_vehicle
        lines = ["=== 引擎更换 ===\n\n"]
        if v is not None:
            lines.append(f"当前引擎: {v.engine.name}（载重 {int(v.engine.load)}t）\n\n")
        engines = sorted((e for e in self.config.engines.values() if e.price > 0),
                         key=lambda e: e.id)
        for i, engine in enumerate(engines):
            lines.append(
                f"{i+1}. {engine.name}  载重 {int(engine.load)}t  "
                f"防御 {engine.defense}  - {engine.price}G\n"
            )
        lines.append("\n按数字键购买更换，按ESC返回改造店。")
        return "".join(lines)

    def _render_bounty_board(self) -> str:
        """悬赏榜：列表 + 状态 + 操作提示"""
        d = self.data
        lines = ["=== 悬赏榜 ===\n\n", "墙上的通缉令层层叠叠。\n\n"]
        for i, bounty_id in enumerate(sorted(self.config.bounties.keys())):
            bounty = self.config.bounties[bounty_id]
            status = BountyManager.status(d, bounty_id)
            label = BountyManager.status_label(status)
            lines.append(f"{i+1}. {bounty.name:<8} 悬赏 {bounty.reward:>7}G  [{label}]\n")
            lines.append(f"   {bounty.description}\n\n")
        lines.append("按数字键接取/领赏，按ESC返回城镇。")
        return "".join(lines)

    def _render_shop(self) -> str:
        shop = self.data.current_shop
        if shop:
            lines = [f"=== {shop.name} ===\n\n", "欢迎光临！想买点什么？\n\n"]
            for i, item_id in enumerate(shop.items[:9]):
                item_data = self.config.get_item_by_id(item_id)
                if item_data:
                    price = int(item_data.price * shop.price_multiplier)
                    lines.append(f"{i+1}. {item_data.name:15} - {price}金币\n")
                    lines.append(f"   {item_data.description}\n\n")
            lines.append("\n按数字键购买，按ESC离开。")
            return "".join(lines)
        else:
            lines = ["=== 商店 ===\n\n", "欢迎光临！想买点什么？\n\n"]
            for i in [1, 2, 3, 4]:
                item_data = self.config.get_item_by_id(i)
                if item_data:
                    lines.append(f"{i}. {item_data.name:15} - {item_data.price}金币\n")
                    lines.append(f"   {item_data.description}\n\n")
            lines.append("\n按数字键购买，按ESC离开。")
            return "".join(lines)

    def _render_dialog(self) -> str:
        npc = self.data.current_npc
        if not npc:
            return ""
        return f"=== {npc.name} ===\n\n{npc.dialog}\n\n\n按空格键继续..."

    def _render_quests(self) -> str:
        """渲染任务日志"""
        d = self.data
        lines = ["=== 任务日志 ===\n\n"]
        lines.append("── 进行中 ──\n")
        if d.quest_progress:
            for track in d.quest_progress:
                q = track.quest_data
                progress = ""
                if q.type == "kill":
                    progress = f" (击杀: {track.kill_count}/{q.target_count})"
                elif q.type == "collect":
                    progress = f" (收集: {track.collect_count}/{q.target_count})"
                elif q.type == "explore":
                    progress = f" (到访: {track.collect_count}/{q.target_count})"
                lines.append(f"  * {q.name}{progress}\n")
                lines.append(f"    {q.description}\n\n")
        else:
            lines.append("  暂无进行中的任务。\n\n")

        lines.append("── 已完成 ──\n")
        if d.completed_quests:
            for q in d.completed_quests:
                lines.append(f"  ✓ {q.name}\n")
        else:
            lines.append("  暂无已完成的任务。\n")

        lines.append("\n\n按任意键返回...")
        return "".join(lines)

    # ═══════════════════════════════════════════════════
    # 命令 — 移动 / 交互
    # ═══════════════════════════════════════════════════

    def command_move(self, direction: Direction):
        if self.data.state != GameState.WORLD:
            return

        # 超重拦截（载重由引擎决定）
        vehicle = self.data.current_vehicle
        if vehicle is not None and vehicle.is_alive() and vehicle.is_overweight():
            self.data.add_log(
                f"战车超重（{vehicle.total_weight()}t / 载重 {vehicle.load_capacity()}t），无法移动！"
            )
            return

        dx, dy = 0, 0
        if direction == Direction.UP:
            dy = -1
        elif direction == Direction.DOWN:
            dy = 1
        elif direction == Direction.LEFT:
            dx = -1
        elif direction == Direction.RIGHT:
            dx = 1

        old_x, old_y = self.data.player_x, self.data.player_y
        npc = MapManager.try_move(self.data, dx, dy, self.config.npcs)
        moved = (self.data.player_x, self.data.player_y) != (old_x, old_y)

        # 燃料消耗（成功移动且乘坐战车时）
        if moved and self.data.current_vehicle and self.data.current_vehicle.is_alive():
            if not self.data.current_vehicle.consume_fuel():
                self.data.add_log("战车燃料耗尽！")

        # 探索任务追踪（移动成功后）
        if moved:
            # 迷彩条：剩余隐身步数递减
            if self.data.camouflage_steps > 0:
                self.data.camouflage_steps -= 1
            QuestManager.track_explore_map(self.data, self.data.current_map_id)
            # 赏金首明雷遭遇（走到坐标即触发）
            bounty = BountyManager.check_encounter(self.data)
            if bounty is not None:
                self._start_bounty_battle(bounty)
                return

        if npc:
            self.command_start_dialog(npc)

    def command_interact(self):
        d = self.data
        if d.state == GameState.WORLD:
            entrance_id = MapManager.entrance_at(d)
            if entrance_id is not None:
                self._enter_map(entrance_id)
            elif MapManager.is_at_leave_point(d):
                self._leave_map()
            elif (MapManager.is_bounded(d) and d.config is not None
                  and d.config.maps[d.current_map_id].is_town):
                # 城镇内闲逛时，空格打开城镇菜单
                d.state = GameState.TOWN
                self._notify_state()
            else:
                d.add_log("这里什么都没有。")
        elif d.state == GameState.DIALOG:
            d.state = GameState.WORLD
            self._notify_state()

    def _enter_map(self, map_id: int):
        """从荒野进入有限地图（城镇/遗迹）"""
        d = self.data
        map_data = self.config.maps.get(map_id)
        if map_data is None:
            d.add_log("目标地图不存在。")
            return
        d.return_x, d.return_y = d.player_x, d.player_y
        d.current_map_id = map_id
        MapManager.generate_map(d, map_data, self.config.npcs)
        d.player_x, d.player_y = MapManager.entrance_cell(map_data)
        if map_data.is_town:
            d.state = GameState.TOWN
            d.add_log(f"进入了{map_data.name}。")
        else:
            d.state = GameState.WORLD
            d.add_log(f"来到了{map_data.name}。")
        QuestManager.track_explore_map(d, map_id)
        self._notify_state()

    def _leave_map(self):
        """从有限地图返回荒野"""
        d = self.data
        d.current_map_id = 1
        # 避免刚出镇就站在入口上、再次交互时立刻被弹回，优先向上偏移一格
        if InfiniteTerrain.is_passable(d.return_x, d.return_y - 1):
            d.player_x, d.player_y = d.return_x, d.return_y - 1
        else:
            d.player_x, d.player_y = d.return_x, d.return_y
        d.state = GameState.WORLD
        d.add_log("回到了荒野。")
        self._notify_state()

    def command_leave_town(self):
        """离开城镇（城镇菜单选项 4）"""
        d = self.data
        if d.state == GameState.TOWN:
            self._leave_map()

    def command_enter_shop(self):
        d = self.data
        # 根据地图ID查找商店
        shop = None
        for s in self.config.shops.values():
            if s.map_id == d.current_map_id:
                shop = s
                break
        d.current_shop = shop
        d.state = GameState.SHOP
        d.add_log(f"进入了{shop.name if shop else '商店'}。")
        self._notify_state()

    def command_start_dialog(self, npc_data):
        self.data.current_npc = npc_data
        self.data.state = GameState.DIALOG
        self.data.add_log(f"与{npc_data.name}交谈")
        self._notify_state()

    # ═══════════════════════════════════════════════════
    # 命令 — 战斗
    # ═══════════════════════════════════════════════════

    def command_attack(self):
        if self.data.state != GameState.BATTLE:
            return
        result = BattleEngine.player_attack(self.data)
        self._apply_battle_result(result)

    def command_defend(self):
        if self.data.state != GameState.BATTLE:
            return
        result = BattleEngine.player_defend(self.data)
        self._apply_battle_result(result)

    def command_use_skill(self, skill_index: int):
        """使用技能（战斗中）"""
        if self.data.state != GameState.BATTLE:
            return
        result = BattleEngine.player_use_skill(self.data, skill_index)
        self._apply_battle_result(result)

    def command_escape(self):
        if self.data.state != GameState.BATTLE:
            return
        result = BattleEngine.try_escape(self.data)
        if result.escaped:
            self.battle_text.set("成功逃跑了！")
            self._end_battle()
            self._notify_state()
            return
        self._apply_battle_result(result)

    # ═══════════════════════════════════════════════════
    # 命令 — 物品 / 购买 / 修理 / 休息
    # ═══════════════════════════════════════════════════

    def command_use_item(self, index: int):
        """使用/装备物品

        战斗中：走战斗道具逻辑（夺命三宝/特殊炮弹/回复）。
        非战斗：装备类执行装备，探索类执行探索效果，其余直接使用。
        """
        d = self.data
        if index < 0:
            return

        if d.state == GameState.BATTLE:
            result = BattleEngine.player_use_item(d, index)
            self._apply_battle_result(result)
            return

        if 0 <= index < len(d.inventory):
            item = d.inventory[index]

            if getattr(item.data, "is_equipment", False):
                old = d.player.equip(item)
                d.inventory.pop(index)
                if old is not None:
                    d.inventory.append(old)
                    d.add_log(f"卸下了{old.name}，装备了{item.name}！")
                else:
                    d.add_log(f"装备了{item.name}！")
                return

            scene = getattr(item.data, "use_scene", "人")
            if scene == "探索":
                self._use_explore_item(index)
                return

            self._consume_item(index)
            return

        # 卸下装备：序号 = len(inventory) + 已装备列表下标
        equipped = d.player.equipped_slots()
        eq_index = index - len(d.inventory)
        if 0 <= eq_index < len(equipped):
            slot, old = equipped[eq_index]
            d.player.unequip(slot)
            d.inventory.append(old)
            d.add_log(f"卸下了{old.name}。")
            return
        d.add_log("没有这个物品。")

    def _use_explore_item(self, index: int):
        """探索类道具（迷彩条/地图）"""
        d = self.data
        item = d.inventory[index]
        effect = getattr(item.data, "effect_type", "")
        if effect == "camouflage":
            d.camouflage_steps = item.effect_value
            d.add_log(f"使用了{item.name}，接下来 {item.effect_value} 次移动不会遇敌。")
            d.inventory.pop(index)
        elif effect == "map_hint":
            hint = self._nearest_hint()
            d.add_log(f"查看了{item.name}：{hint}")
        else:
            d.add_log(f"{item.name}现在不能使用。")

    def _nearest_hint(self) -> str:
        """地图道具：提示最近的城镇入口与赏金首"""
        d = self.data
        best_town, best_town_dist = None, None
        for (tx, ty), map_id in d.map_entrances.items():
            dist = abs(tx - d.player_x) + abs(ty - d.player_y)
            if best_town_dist is None or dist < best_town_dist:
                best_town = self.config.maps.get(map_id)
                best_town_dist = dist
        parts = []
        if best_town is not None:
            parts.append(f"最近的城镇是{best_town.name}（约 {best_town_dist} 步）")
        best_bounty, best_bounty_dist = None, None
        for bounty in self.config.bounties.values():
            if bounty.map_id != d.current_map_id or bounty.id in d.bounty_claimed:
                continue
            dist = abs(bounty.x - d.player_x) + abs(bounty.y - d.player_y)
            if best_bounty_dist is None or dist < best_bounty_dist:
                best_bounty, best_bounty_dist = bounty, dist
        if best_bounty is not None:
            parts.append(f"最近的赏金首是{best_bounty.name}（约 {best_bounty_dist} 步）")
        return "；".join(parts) if parts else "附近没有发现城镇或赏金首"

    def _consume_item(self, index: int):
        """消耗品使用逻辑"""
        d = self.data
        item = d.inventory[index]
        if item.type == "heal":
            d.player.heal(item.effect_value)
            d.add_log(f"使用了{item.name}，恢复了{item.effect_value}点HP！")
            d.inventory.pop(index)
        elif item.type == "fuel":
            if d.current_vehicle:
                d.current_vehicle.refuel(item.effect_value)
                d.add_log(f"使用了{item.name}，恢复了{item.effect_value}点燃料！")
                d.inventory.pop(index)
            else:
                d.add_log("没有战车可以使用燃料！")
        elif item.type == "buff":
            d.add_log(f"使用了{item.name}，感觉充满了力量！（buff 效果下阶段实装）")
            d.inventory.pop(index)
        else:
            d.add_log(f"{item.name}现在不能使用。")

    def _gain_item(self, item: Item):
        """获得物品的统一入口：入包 + 收集任务追踪（购买/掉落走这里）"""
        self.data.inventory.append(item)
        QuestManager.track_collect(self.data, item.id)

    def command_buy_item(self, item_num: int):
        d = self.data
        shop = d.current_shop
        if shop:
            # 使用 ShopData 配置
            if 0 <= item_num < len(shop.items):
                item_data = self.config.get_item_by_id(shop.items[item_num])
                if item_data:
                    price = int(item_data.price * shop.price_multiplier)
                    if d.gold >= price:
                        d.gold -= price
                        self._gain_item(Item(item_data))
                        d.add_log(f"购买了{item_data.name}！")
                    else:
                        d.add_log(f"金币不足！需要{price}金币。")
        else:
            # 兜底：硬编码商品
            item_ids = [1, 2, 3, 4]
            if 0 <= item_num < len(item_ids):
                item_data = self.config.get_item_by_id(item_ids[item_num])
                if item_data:
                    if d.gold >= item_data.price:
                        d.gold -= item_data.price
                        self._gain_item(Item(item_data))
                        d.add_log(f"购买了{item_data.name}！")
                    else:
                        d.add_log("金币不足！")

    def command_repair_vehicle(self):
        d = self.data
        v = d.current_vehicle
        if v is None:
            d.add_log("没有战车可以修理。")
            return
        if v.hp >= v.max_hp and v.missing_plates() == 0 and not v.broken:
            d.add_log("战车状态完好，无需修理。")
            return
        # 费用 = 基础修理费 + 装甲片补充费（每片 50G）
        plate_cost = v.missing_plates() * 50
        cost = v.repair_cost + plate_cost
        if d.gold >= cost:
            d.gold -= cost
            v.repair()
            d.add_log(f"战车修复完成，花费{cost}金币！")
        else:
            d.add_log(f"金币不足！需要{cost}金币。")

    def command_rest(self):
        d = self.data
        if not MapManager.is_at_town(d):
            d.add_log("只能在城镇里休息。")
            return
        d.player.heal(d.player.max_hp)
        if d.current_vehicle:
            d.current_vehicle.refuel(d.current_vehicle.max_fuel)
        d.add_log("在旅馆休息后，HP和燃料都恢复了！")

    def command_open_inventory(self):
        d = self.data
        if d.state in (GameState.WORLD, GameState.BATTLE):
            d.state = GameState.INVENTORY
            d.add_log("打开物品栏...")
            self._notify_state()

    def command_handle_escape(self):
        d = self.data
        if d.state in (GameState.MENU, GameState.BATTLE):
            return
        if d.state in (GameState.INVENTORY, GameState.TOWN,
                        GameState.SHOP, GameState.DIALOG):
            d.state = GameState.WORLD
            self._notify_state()
        elif d.state == GameState.BOUNTY:
            d.state = GameState.TOWN  # 悬赏榜返回城镇菜单
            self._notify_state()
        elif d.state == GameState.GARAGE:
            d.state = GameState.TOWN  # 改造店返回城镇菜单
            self._notify_state()
        elif d.state == GameState.ENGINE_SHOP:
            d.state = GameState.GARAGE  # 引擎列表返回改造店
            self._notify_state()

    # ═══════════════════════════════════════════════════
    # 命令 — 战车改造店
    # ═══════════════════════════════════════════════════

    def command_open_garage(self):
        """打开战车改造店（城镇菜单进入）"""
        d = self.data
        if d.current_vehicle is None:
            d.add_log("你没有战车，改造店无从下手。")
            return
        d.state = GameState.GARAGE
        d.add_log("欢迎来到战车改造店。")
        self._notify_state()

    def command_mod_action(self, option: int):
        """改造店菜单交互（1-7）"""
        d = self.data
        v = d.current_vehicle
        if v is None or d.state != GameState.GARAGE:
            return

        if option == 1:  # 开主炮孔
            self._do_mod(v, "主炮")
        elif option == 2:  # 开副炮孔
            self._do_mod(v, "副炮")
        elif option == 3:  # 开SE孔
            self._do_mod(v, "SE")
        elif option == 4:  # 底盘防御强化
            cost = ModShop.defense_cost(v)
            if cost is None:
                d.add_log("底盘防御已达上限。")
            elif d.gold >= cost:
                d.gold -= cost
                ModShop.upgrade_defense(v)
                d.add_log(f"底盘防御强化完成（+{ModShop.DEF_STEP}），花费{cost}金币！")
            else:
                d.add_log(f"金币不足！需要{cost}金币。")
        elif option == 5:  # 装甲片扩容
            cost = ModShop.plate_cost(v)
            if d.gold >= cost:
                d.gold -= cost
                ModShop.expand_plates(v)
                d.add_log(f"装甲片容量 +{ModShop.PLATE_STEP}，花费{cost}金币！")
            else:
                d.add_log(f"金币不足！需要{cost}金币。")
        elif option == 6:  # 更换引擎
            self.command_open_engine_shop()
        elif option == 7:  # 离开
            d.state = GameState.TOWN
            self._notify_state()

    def _do_mod(self, vehicle, kind: str):
        """开孔改造（带费用结算）"""
        d = self.data
        cost = ModShop.hole_cost(vehicle, kind)
        if cost is None:
            d.add_log(f"{kind}孔已满。")
            return
        if d.gold < cost:
            d.add_log(f"金币不足！需要{cost}金币。")
            return
        d.gold -= cost
        ModShop.add_hole(vehicle, kind)
        d.add_log(f" {kind}孔开启完成，花费{cost}金币！")

    def command_open_engine_shop(self):
        """打开引擎更换列表"""
        d = self.data
        if not any(e.price > 0 for e in self.config.engines.values()):
            d.add_log("本店没有可更换的引擎。")
            return
        d.state = GameState.ENGINE_SHOP
        self._notify_state()

    def command_engine_interact(self, index: int):
        """购买/更换引擎（按编号）"""
        d = self.data
        v = d.current_vehicle
        if v is None or d.state != GameState.ENGINE_SHOP:
            return
        engines = [e for e in self.config.engines.values() if e.price > 0]
        engines.sort(key=lambda e: e.id)
        if index < 0 or index >= len(engines):
            return
        engine = engines[index]
        if v.engine.id == engine.id:
            d.add_log("已经装配着这个引擎了。")
            return
        if d.gold < engine.price:
            d.add_log(f"金币不足！需要{engine.price}金币。")
            return
        d.gold -= engine.price
        ModShop.change_engine(v, engine)
        d.add_log(f"引擎更换为{engine.name}（载重 {int(engine.load)}t），花费{engine.price}金币！")

    def command_show_quests(self):
        """显示任务日志"""
        d = self.data
        if d.state == GameState.WORLD:
            d.state = GameState.DIALOG  # 复用对话显示
            d.current_npc = type('obj', (object,), {
                'name': '任务日志',
                'dialog': self._render_quests()
            })()
            self._notify_state()

    # ═══════════════════════════════════════════════════
    # 命令 — 悬赏榜（城镇设施）
    # ═══════════════════════════════════════════════════

    def command_open_bounty_board(self):
        """打开悬赏榜（城镇菜单进入）"""
        d = self.data
        if not self.config.bounties:
            d.add_log("悬赏榜空着，没有通缉犯。")
            return
        d.state = GameState.BOUNTY
        d.add_log("浏览悬赏榜...")
        self._notify_state()

    def command_bounty_interact(self, index: int):
        """悬赏榜交互：接取 / 领赏（按编号）"""
        d = self.data
        bounty_ids = sorted(self.config.bounties.keys())
        if index < 0 or index >= len(bounty_ids):
            return
        bounty_id = bounty_ids[index]
        bounty = self.config.bounties[bounty_id]
        status = BountyManager.status(d, bounty_id)

        if status == "locked":
            if BountyManager.accept(d, bounty_id):
                d.add_log(f"接取了悬赏: {bounty.name}（悬赏 {bounty.reward} 金币）。")
        elif status == "defeated":
            payout = BountyManager.claim(d, bounty_id)
            if payout > 0:
                d.add_log(f"领取了{bounty.name}的悬赏，获得 {payout} 金币！")
        elif status == "active":
            d.add_log(f"悬赏进行中: {bounty.name}，目标在荒野中（地图标记 B）。")
        else:
            d.add_log(f"{bounty.name}的悬赏已领取。")

    def command_new_game(self, class_id: int = 1):
        """开始新游戏（class_id：1=猎人 2=机械师 3=战士）"""
        self.init_new_game(class_id)

    # ═══════════════════════════════════════════════════
    # 命令 — 存档 / 读档
    # ═══════════════════════════════════════════════════

    def has_save(self, slot: int) -> bool:
        """指定槽位是否有存档"""
        return self.save_manager.has_save(slot)

    def list_saves(self) -> list:
        """列出所有有存档的槽位"""
        return self.save_manager.list_saves()

    def command_save(self, slot: int) -> bool:
        """保存游戏到指定槽位（战斗中/主菜单禁止保存）"""
        d = self.data
        if d.state == GameState.BATTLE:
            d.add_log("战斗中无法保存游戏！")
            return False
        if d.state == GameState.MENU or not d.player:
            d.add_log("当前没有可保存的游戏进度。")
            return False
        ok = self.save_manager.save(slot, d.to_dict())
        if ok:
            d.add_log(f"游戏已保存到槽位 {slot}。")
        else:
            d.add_log(f"保存失败（槽位 {slot}）！")
        return ok

    def command_load(self, slot: int) -> bool:
        """从指定槽位读取游戏"""
        if not self.save_manager.has_save(slot):
            self.data.add_log(f"槽位 {slot} 没有存档。")
            return False
        raw = self.save_manager.load(slot)
        if raw is None:
            self.data.add_log(f"读取槽位 {slot} 失败：存档文件损坏。")
            return False
        try:
            new_data = GameData.from_dict(raw, self.config)
        except Exception as e:
            self.data.add_log(f"读取槽位 {slot} 失败：{e}")
            return False
        self.data = new_data
        self.data.add_log(f"已读取槽位 {slot} 的存档。")
        # 重建地图入口与有限地图网格（网格不持久化，读档后按配置重新生成）。
        # 注意：不在此处触发探索任务追踪——进度已随存档保存，
        # 重复触发会在"站在目标地图里读档"时误判新任务完成。
        MapManager.create_map(self.data, self.config.maps, self.config.npcs)
        self._notify_state()
        self._refresh_all()
        return True

    # ═══════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════

    def _random_encounter(self):
        enemy_data = self.config.get_random_enemy(self.data.current_map_id)
        if enemy_data:
            enemy = Enemy(enemy_data)
            self._start_battle(enemy)
            self.data.add_log(f"遭遇了{enemy.name}！")

    def _start_battle(self, enemy: Enemy):
        self.data.state = GameState.BATTLE
        self.data.current_enemy = enemy
        self.battle_text.set(f"遭遇了{enemy.name}！")
        self._notify_state()

    def _start_bounty_battle(self, bounty):
        """赏金首明雷战斗：记录 bounty、强制人战则切步行形态"""
        d = self.data
        enemy_data = self.config.enemies.get(bounty.enemy_id)
        if enemy_data is None:
            d.add_log(f"{bounty.name}的战斗数据缺失（敌人ID {bounty.enemy_id}）！")
            return
        d.current_bounty_id = bounty.id
        if bounty.on_foot:
            # 强制人战：切步行形态，战斗结束后自动恢复乘车
            d.player.combat_on_foot = True
        enemy = Enemy(enemy_data)
        d.state = GameState.BATTLE
        d.current_enemy = enemy
        self.battle_text.set(f"遭遇了赏金首{bounty.name}！悬赏 {bounty.reward} 金币！")
        if bounty.on_foot:
            self.battle_text.set(
                self.battle_text.get()
                + f"\n{bounty.name}拦住了去路：“下车吧，这不是钢铁该管的事。”"
            )
        d.add_log(f"遭遇了赏金首{bounty.name}！")
        self._notify_state()

    def command_toggle_vehicle(self):
        """战斗中乘降切换（战车损坏或强制人战不可乘车）"""
        d = self.data
        if d.state != GameState.BATTLE:
            return
        player = d.player
        vehicle = player.vehicle
        if vehicle is None or not vehicle.is_alive():
            d.add_log("战车已损坏，无法乘车！")
            return
        if player.combat_on_foot:
            player.combat_on_foot = False
            self.battle_text.set(self.battle_text.get() + "\n你跳上了战车。")
            d.add_log("乘上了战车。")
        else:
            player.combat_on_foot = True
            self.battle_text.set(self.battle_text.get() + "\n你跳下了战车。")
            d.add_log("跳下了战车。")
        self._notify_state()

    def _end_battle(self):
        """结束战斗：恢复乘车形态、重置战斗倍率与技能冷却"""
        BattleEngine.reset_battle_state(self.data.player)
        if self.data.player.vehicle is not None:
            self.data.player.vehicle.battle_atk_mult = 1.0
        self.data.player.combat_on_foot = False
        BattleEngine.end_battle(self.data)

    def _apply_battle_result(self, result):
        """应用战斗回合结果"""
        for msg in result.messages:
            self.battle_text.set(self.battle_text.get() + msg + "\n")

        if result.player_dead:
            self.data.add_log("你战败了...")
            if self.on_game_over:
                self.on_game_over()
            return

        if result.enemy_dead or result.escaped:
            if result.enemy_dead:
                # 结算奖励
                vr = BattleEngine.resolve_victory(self.data, self.config.items)
                self.battle_text.set(
                    f"胜利！获得{vr.exp_gained}经验和{vr.gold_gained}金币！"
                )
                if vr.leveled_up:
                    self.battle_text.set(
                        self.battle_text.get() + f"\n升级了！现在等级 {self.data.player.level}！"
                    )
                if vr.item_dropped:
                    self.battle_text.set(
                        self.battle_text.get() + f"\n获得了{vr.item_dropped.name}！"
                    )
                    # 掉落计入收集任务
                    QuestManager.track_collect(self.data, vr.item_dropped.id)
                # 赏金首结算（接取状态下击杀即时入账）
                bounty_id = self.data.current_bounty_id
                if bounty_id is not None:
                    payout = BountyManager.on_defeated(self.data, bounty_id)
                    bounty = self.config.bounties.get(bounty_id)
                    if bounty is not None:
                        if payout > 0:
                            self.battle_text.set(
                                self.battle_text.get()
                                + f"\n悬赏到账：{bounty.name}，{payout} 金币！"
                            )
                        else:
                            self.battle_text.set(
                                self.battle_text.get()
                                + f"\n{bounty.name}已被击败，回城镇悬赏榜可领取悬赏。"
                            )
                    self.data.current_bounty_id = None
            self._end_battle()
            self._notify_state()

    def _notify_state(self):
        if self.on_state_changed:
            self.on_state_changed(self.data.state)
