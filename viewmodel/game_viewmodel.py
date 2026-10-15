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
    BattleEngine, MapManager, InfiniteTerrain,
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

    def init_new_game(self):
        """初始化新游戏"""
        self.data.player = Character("雷班纳", 100, 100, 15, 8, 12)
        self.data.gold = 500
        self.data.player_x = 10
        self.data.player_y = 10
        self.data.inventory = []
        self.data.vehicles = []
        self.data.active_quests = []
        self.data.completed_quests = []
        self.data.quest_progress = []
        self.data.game_time = 0.0

        # 初始技能
        for skill_data in self.config.skills.values():
            self.data.player.learn_skill(Skill(skill_data))

        # 初始物品
        for item_data in self.config.get_starting_items():
            self.data.inventory.append(Item(item_data))

        # 初始战车
        if 1 in self.config.vehicles:
            v = Vehicle(self.config.vehicles[1])
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

        # 随机遇敌（使用地图遭遇率）
        if self.data.state == GameState.WORLD:
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

    def _refresh_all(self):
        """刷新所有 Observable 属性"""
        d = self.data

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
            self.vehicle_text.set(
                f"战车: {v.name}\n"
                f"HP: {v.hp}/{v.max_hp}\n"
                f"燃料: {int(v.fuel)}/{int(v.max_fuel)}"
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

        return (
            f"\n"
            f"        ╔══════════════════════════════════════════════════════╗\n"
            f"        ║                     战 斗                           ║\n"
            f"        ╠══════════════════════════════════════════════════════╣\n"
            f"        ║                                                      ║\n"
            f"        ║  {enemy.name:^20}                                    ║\n"
            f"        ║  HP: {enemy.hp:>3}/{enemy.max_hp:<3}                                      ║\n"
            f"{desc_line}"
            f"        ║                                                      ║\n"
            f"        ║              VS                                      ║\n"
            f"        ║                                                      ║\n"
            f"        ║  {self.data.player.name:^20}                                    ║\n"
            f"        ║  HP: {self.data.player.hp:>3}/{self.data.player.max_hp:<3}                                      ║\n"
            f"        ║                                                      ║\n"
            f"        ╚══════════════════════════════════════════════════════╝\n"
        )

    def _render_inventory(self) -> str:
        lines = ["=== 物品栏 ===\n"]
        if not self.data.inventory:
            lines.append("物品栏是空的。\n")
        else:
            for i, item in enumerate(self.data.inventory):
                usable = "✓" if item.usable_in_battle else " "
                lines.append(f"{i+1}. [{usable}] {item.name:15} - {item.description}\n")
                lines.append(f"    类型: {item.type}, 效果: {item.effect_value}\n\n")
        lines.append("\n按数字键使用物品，按ESC返回游戏。")
        return "".join(lines)

    def _render_town(self) -> str:
        return (
            "=== 城镇 ===\n\n"
            "欢迎来到城镇！\n\n"
            "1. 商店\n"
            "2. 旅馆\n"
            "3. 修理店\n"
            "4. 离开城镇\n\n"
            "请选择选项..."
        )

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
            QuestManager.track_explore_map(self.data, self.data.current_map_id)

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
            BattleEngine.end_battle(self.data)
            self._notify_state()
            return
        self._apply_battle_result(result)

    # ═══════════════════════════════════════════════════
    # 命令 — 物品 / 购买 / 修理 / 休息
    # ═══════════════════════════════════════════════════

    def command_use_item(self, index: int):
        if index < 0 or index >= len(self.data.inventory):
            return
        item = self.data.inventory[index]
        d = self.data

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
        if d.current_vehicle and d.current_vehicle.hp < d.current_vehicle.max_hp:
            cost = d.current_vehicle.repair_cost  # 使用 VehicleData 配置
            if cost == 0:
                cost = (d.current_vehicle.max_hp - d.current_vehicle.hp) * 2
            if d.gold >= cost:
                d.gold -= cost
                d.current_vehicle.repair()
                d.add_log(f"战车修复完成，花费{cost}金币！")
            else:
                d.add_log(f"金币不足！需要{cost}金币。")
        elif d.current_vehicle:
            d.add_log("战车状态完好，无需修理。")
        else:
            d.add_log("没有战车可以修理。")

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

    def command_new_game(self):
        self.init_new_game()

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
            BattleEngine.end_battle(self.data)
            self._notify_state()

    def _notify_state(self):
        if self.on_state_changed:
            self.on_state_changed(self.data.state)
