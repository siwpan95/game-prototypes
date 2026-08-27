import tkinter as tk
from tkinter import messagebox
import random
import time
from enum import Enum
import os
import sys

# 确保脚本所在目录在搜索路径中
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# 导入配置加载器
try:
    from loader import ConfigLoader, EnemyData, ItemData, VehicleData, NPCData
except ImportError:
    print("错误: 无法导入loader.py，请确保文件存在")
    exit(1)

class GameState(Enum):
    MENU = 0
    WORLD = 1
    BATTLE = 2
    INVENTORY = 3
    DIALOG = 4
    SHOP = 5
    TOWN = 6

class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

class Character:
    def __init__(self, name, hp, max_hp, attack, defense, speed):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self.attack = attack
        self.defense = defense
        self.speed = speed
        self.level = 1
        self.exp = 0
        self.exp_to_next = 100
        
    def is_alive(self):
        return self.hp > 0
    
    def take_damage(self, damage):
        actual_damage = max(1, damage - self.defense // 2)
        self.hp -= actual_damage
        if self.hp < 0:
            self.hp = 0
        return actual_damage
    
    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)
    
    def gain_exp(self, exp):
        self.exp += exp
        if self.exp >= self.exp_to_next:
            self.level_up()
    
    def level_up(self):
        self.level += 1
        self.exp -= self.exp_to_next
        self.exp_to_next = int(self.exp_to_next * 1.5)
        self.max_hp += 10
        self.attack += 3
        self.defense += 2
        self.speed += 1
        self.hp = self.max_hp

class Enemy(Character):
    def __init__(self, enemy_data: EnemyData):
        super().__init__(
            enemy_data.name,
            enemy_data.hp,
            enemy_data.hp,
            enemy_data.attack,
            enemy_data.defense,
            enemy_data.speed
        )
        self.exp_reward = enemy_data.exp_reward
        self.gold_reward = enemy_data.gold_reward
        self.data = enemy_data

class Item:
    def __init__(self, item_data: ItemData):
        self.id = item_data.id
        self.name = item_data.name
        self.type = item_data.type
        self.effect_value = item_data.effect_value
        self.price = item_data.price
        self.description = item_data.description
        self.usable_in_battle = item_data.usable_in_battle
        self.data = item_data

class Vehicle:
    def __init__(self, vehicle_data: VehicleData):
        self.id = vehicle_data.id
        self.name = vehicle_data.name
        self.hp = vehicle_data.hp
        self.max_hp = vehicle_data.hp
        self.attack = vehicle_data.attack
        self.defense = vehicle_data.defense
        self.speed = vehicle_data.speed
        self.fuel = vehicle_data.fuel_capacity
        self.max_fuel = vehicle_data.fuel_capacity
        self.fuel_consumption = vehicle_data.fuel_consumption
        self.repair_cost = vehicle_data.repair_cost
        self.broken = False
        self.data = vehicle_data

class NPC:
    def __init__(self, npc_data: NPCData):
        self.id = npc_data.id
        self.name = npc_data.name
        self.role = npc_data.role
        self.dialog = npc_data.dialog
        self.location_x = npc_data.location_x
        self.location_y = npc_data.location_y
        self.map_id = npc_data.map_id
        self.data = npc_data

class MMGame:
    def __init__(self, root):
        self.root = root
        self.root.title("重装机兵同人 - Metal Max Fan Game")
        self.root.geometry("1000x750")
        self.root.resizable(False, False)
        
        # 加载配置（使用脚本所在目录的绝对路径）
        config_path = os.path.join(SCRIPT_DIR, "config.xlsx")
        self.config_loader = ConfigLoader(config_path)
        self.config_loaded = self.config_loader.load_all()
        
        if not self.config_loaded:
            messagebox.showerror("错误", "无法加载配置文件！\n请确保config.xlsx存在且格式正确。")
            root.destroy()
            return
        
        # 游戏状态
        self.state = GameState.MENU
        self.player = Character("雷班纳", 100, 100, 15, 8, 12)
        self.current_enemy = None
        self.current_npc = None
        self.current_map_id = 1
        self.player_x = 10
        self.player_y = 10
        self.game_time = 0
        self.gold = 500
        self.current_vehicle = None
        
        # 游戏数据
        self.inventory = []
        self.vehicles = []
        self.active_quests = []
        self.completed_quests = []
        
        # 初始化游戏数据
        self.init_game_data()
        
        # 创建UI
        self.create_ui()
        
        # 绑定按键
        self.bind_keys()
        
        # 游戏循环
        self.last_update = time.time()
        self.game_loop()
    
    def init_game_data(self):
        """初始化游戏数据"""
        # 从配置加载初始物品
        starting_items = self.config_loader.get_starting_items()
        for item_data in starting_items:
            self.inventory.append(Item(item_data))
        
        # 从配置加载初始战车
        if 1 in self.config_loader.vehicles:
            self.vehicles.append(Vehicle(self.config_loader.vehicles[1]))
            self.current_vehicle = self.vehicles[0]
        
        # 创建地图
        self.create_map()
        
        # 初始化日志
        self.log_messages = []
        self.add_log("欢迎来到重装机兵的世界！")
        
        # 获取初始任务
        if self.config_loader.quests:
            first_quest = next(iter(self.config_loader.quests.values()))
            self.active_quests.append(first_quest)
            self.add_log(f"接到新任务: {first_quest.name}")
    
    def create_map(self):
        """根据配置创建地图"""
        if self.current_map_id in self.config_loader.maps:
            map_data = self.config_loader.maps[self.current_map_id]
            width, height = map_data.width, map_data.height
        else:
            width, height = 20, 20
        
        # 创建空地图
        self.current_map = [['.' for _ in range(width)] for _ in range(height)]
        
        # 添加地形
        terrain_types = ['^', '~', 'T', '□']
        for i in range(min(5, width//4)):
            x, y = random.randint(0, width-1), random.randint(0, height-1)
            self.current_map[y][x] = random.choice(terrain_types[:3])
        
        # 添加城镇
        self.town_positions = []
        for npc in self.config_loader.npcs.values():
            if npc.map_id == self.current_map_id and npc.role in ['镇长', '向导']:
                self.town_positions.append((npc.location_x, npc.location_y))
                self.current_map[npc.location_y][npc.location_x] = '□'
        
        # 如果没有找到城镇，添加一个默认城镇
        if not self.town_positions:
            self.town_positions.append((width//2, height//2))
            self.current_map[height//2][width//2] = '□'
    
    def create_ui(self):
        """创建游戏界面"""
        # 主容器
        self.main_frame = tk.Frame(self.root, bg="#2c3e50")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 游戏区域
        self.game_frame = tk.Frame(self.main_frame, bg="black", bd=2, relief=tk.RAISED)
        self.game_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # ASCII游戏显示
        self.game_display = tk.Text(
            self.game_frame, 
            bg="black", 
            fg="#ecf0f1", 
            font=("Courier New", 12),
            width=60, 
            height=30,
            state=tk.DISABLED,
            cursor="arrow"
        )
        self.game_display.pack(padx=5, pady=5)
        
        # 信息面板
        self.info_panel = tk.Frame(self.main_frame, bg="#34495e", width=280, bd=2, relief=tk.RAISED)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # 玩家信息
        self.player_info = tk.Label(
            self.info_panel, 
            text=f"{self.player.name} Lv.{self.player.level}",
            bg="#34495e", 
            fg="#f1c40f",
            font=("Arial", 12, "bold"),
            anchor=tk.W
        )
        self.player_info.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.stats_label = tk.Label(
            self.info_panel,
            text=f"HP: {self.player.hp}/{self.player.max_hp}\n"
                 f"攻击: {self.player.attack}  防御: {self.player.defense}\n"
                 f"速度: {self.player.speed}  金币: {self.gold}",
            bg="#34495e",
            fg="#ecf0f1",
            font=("Arial", 10),
            justify=tk.LEFT,
            anchor=tk.W
        )
        self.stats_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 战车信息
        if self.current_vehicle:
            vehicle_text = f"战车: {self.current_vehicle.name}\n"
            vehicle_text += f"HP: {self.current_vehicle.hp}/{self.current_vehicle.max_hp}\n"
            vehicle_text += f"燃料: {self.current_vehicle.fuel}/{self.current_vehicle.max_fuel}"
        else:
            vehicle_text = "战车: 无"
        
        self.vehicle_label = tk.Label(
            self.info_panel,
            text=vehicle_text,
            bg="#34495e",
            fg="#3498db",
            font=("Arial", 10),
            justify=tk.LEFT,
            anchor=tk.W
        )
        self.vehicle_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 分隔线
        tk.Frame(self.info_panel, bg="#7f8c8d", height=2).pack(fill=tk.X, padx=10, pady=10)
        
        # 消息日志
        self.log_label = tk.Label(
            self.info_panel,
            text="消息日志",
            bg="#34495e",
            fg="#3498db",
            font=("Arial", 11, "bold")
        )
        self.log_label.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.log_text = tk.Text(
            self.info_panel,
            bg="#2c3e50",
            fg="#bdc3c7",
            font=("Arial", 9),
            height=8,
            width=32,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 控制按钮
        self.control_frame = tk.Frame(self.info_panel, bg="#34495e")
        self.control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        buttons = [
            ("物品(I)", self.open_inventory),
            ("战车(V)", self.open_vehicles),
            ("休息(R)", self.rest),
            ("保存(S)", self.save_game)
        ]
        
        for text, command in buttons:
            btn = tk.Button(
                self.control_frame,
                text=text,
                command=command,
                bg="#3498db",
                fg="white",
                font=("Arial", 9),
                width=8
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # 战斗面板（初始隐藏）
        self.battle_panel = tk.Frame(self.info_panel, bg="#34495e")
        
        self.battle_text = tk.Text(
            self.battle_panel,
            bg="#2c3e50",
            fg="#e74c3c",
            font=("Courier New", 10),
            height=6,
            width=32,
            state=tk.DISABLED
        )
        self.battle_text.pack(fill=tk.X, padx=10, pady=5)
        
        # 战斗选项
        self.battle_options = tk.Frame(self.battle_panel, bg="#34495e")
        self.battle_options.pack(fill=tk.X, padx=10, pady=5)
        
        battle_buttons = [
            ("攻击(1)", self.attack_enemy),
            ("防御(2)", self.defend),
            ("道具(3)", self.use_item_in_battle),
            ("逃跑(4)", self.try_escape)
        ]
        
        for text, command in battle_buttons:
            btn = tk.Button(
                self.battle_options,
                text=text,
                command=command,
                bg="#e74c3c",
                fg="white",
                font=("Arial", 9),
                width=8
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # 菜单栏
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="新游戏", command=self.new_game)
        file_menu.add_command(label="保存游戏", command=self.save_game)
        file_menu.add_command(label="加载游戏", command=self.load_game)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        self.menu_bar.add_cascade(label="游戏", menu=file_menu)
        
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="操作说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        self.menu_bar.add_cascade(label="帮助", menu=help_menu)
    
    def bind_keys(self):
        """绑定键盘事件"""
        self.root.bind("<Up>", lambda e: self.move_player(Direction.UP))
        self.root.bind("<Down>", lambda e: self.move_player(Direction.DOWN))
        self.root.bind("<Left>", lambda e: self.move_player(Direction.LEFT))
        self.root.bind("<Right>", lambda e: self.move_player(Direction.RIGHT))
        self.root.bind("<space>", lambda e: self.interact())
        self.root.bind("<Escape>", lambda e: self.handle_escape())
        self.root.bind("<i>", lambda e: self.open_inventory())
        self.root.bind("<v>", lambda e: self.open_vehicles())
        self.root.bind("<r>", lambda e: self.rest())
        self.root.bind("<s>", lambda e: self.save_game())
        self.root.bind("<Key>", self.handle_key_press)
        
        # 鼠标点击
        self.game_display.bind("<Button-1>", self.on_click)
    
    def handle_key_press(self, event):
        """处理键盘按键"""
        if self.state == GameState.MENU:
            # 主菜单
            if event.char == '1':
                self.new_game()
            elif event.char == '2':
                self.load_game()
            elif event.char == '3':
                self.show_settings()
            elif event.char == '4':
                self.root.quit()
        elif self.state == GameState.INVENTORY:
            # 物品栏界面，数字键使用物品
            if event.char.isdigit():
                item_num = int(event.char) - 1
                if 0 <= item_num < len(self.inventory):
                    self.use_item(item_num)
        elif self.state == GameState.BATTLE:
            # 战斗界面
            if event.char == '1':
                self.attack_enemy()
            elif event.char == '2':
                self.defend()
            elif event.char == '3':
                self.use_item_in_battle()
            elif event.char == '4':
                self.try_escape()
        elif self.state == GameState.TOWN:
            # 城镇界面
            if event.char == '1':
                self.enter_shop()
            elif event.char == '2':
                self.rest()
            elif event.char == '3':
                self.repair_vehicle()
            elif event.char == '4':
                self.state = GameState.WORLD
                self.add_log("离开了城镇。")
        elif self.state == GameState.SHOP:
            # 商店界面
            if event.char.isdigit():
                item_num = int(event.char) - 1
                self.buy_item(item_num)
    
    def handle_escape(self):
        """处理ESC键"""
        if self.state == GameState.MENU:
            self.root.quit()
        elif self.state == GameState.WORLD:
            self.state = GameState.MENU
        elif self.state in [GameState.INVENTORY, GameState.TOWN, GameState.SHOP, GameState.DIALOG]:
            self.state = GameState.WORLD
        elif self.state == GameState.BATTLE:
            # 战斗中不能按ESC退出
            self.add_log("战斗中不能退出！")
    
    def game_loop(self):
        """游戏主循环"""
        current_time = time.time()
        delta = current_time - self.last_update
        self.last_update = current_time
        
        # 更新游戏时间
        self.game_time += delta
        
        # 随机遭遇敌人
        if self.state == GameState.WORLD and random.random() < 0.01:
            self.start_random_encounter()
        
        # 更新显示
        self.update_display()
        
        # 继续游戏循环
        self.root.after(100, self.game_loop)
    
    def update_display(self):
        """更新游戏显示"""
        self.game_display.config(state=tk.NORMAL)
        self.game_display.delete(1.0, tk.END)
        
        if self.state == GameState.MENU:
            self.draw_menu()
        elif self.state == GameState.WORLD:
            self.draw_world()
        elif self.state == GameState.BATTLE:
            self.draw_battle()
        elif self.state == GameState.INVENTORY:
            self.draw_inventory()
        elif self.state == GameState.TOWN:
            self.draw_town()
        elif self.state == GameState.SHOP:
            self.draw_shop()
        elif self.state == GameState.DIALOG:
            self.draw_dialog()
        
        self.game_display.config(state=tk.DISABLED)
        
        # 更新信息面板
        self.player_info.config(text=f"{self.player.name} Lv.{self.player.level}")
        self.stats_label.config(
            text=f"HP: {self.player.hp}/{self.player.max_hp}\n"
                 f"攻击: {self.player.attack}  防御: {self.player.defense}\n"
                 f"速度: {self.player.speed}  金币: {self.gold}"
        )
        
        # 更新战车信息
        if self.current_vehicle:
            vehicle_text = f"战车: {self.current_vehicle.name}\n"
            vehicle_text += f"HP: {self.current_vehicle.hp}/{self.current_vehicle.max_hp}\n"
            vehicle_text += f"燃料: {self.current_vehicle.fuel}/{self.current_vehicle.max_fuel}"
        else:
            vehicle_text = "战车: 无"
        self.vehicle_label.config(text=vehicle_text)
        
        # 更新日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(1.0, "\n".join(self.get_recent_logs()))
        self.log_text.config(state=tk.DISABLED)
    
    def draw_menu(self):
        """绘制主菜单"""
        title = """
        ╔══════════════════════════════════════════════════════╗
        ║                 重装机兵同人游戏                     ║
        ║               Metal Max Fan Game                     ║
        ╚══════════════════════════════════════════════════════╝
        """
        self.game_display.insert(1.0, title)
        self.game_display.insert(tk.END, "\n\n")
        self.game_display.insert(tk.END, "        1. 开始新游戏\n")
        self.game_display.insert(tk.END, "        2. 继续游戏\n")
        self.game_display.insert(tk.END, "        3. 游戏设置\n")
        self.game_display.insert(tk.END, "        4. 退出游戏\n")
        self.game_display.insert(tk.END, "\n\n        按对应数字键选择...")
    
    def draw_world(self):
        """绘制世界地图"""
        # 绘制地图
        display_map = [row[:] for row in self.current_map]
        
        # 先放置NPC（后放置玩家，确保玩家不会被NPC覆盖）
        for npc in self.config_loader.npcs.values():
            if npc.map_id == self.current_map_id:
                nx, ny = npc.location_x, npc.location_y
                if 0 <= nx < len(display_map[0]) and 0 <= ny < len(display_map):
                    display_map[ny][nx] = 'N'
        
        # 放置玩家（覆盖NPC位置，确保玩家始终可见）
        display_map[self.player_y][self.player_x] = 'P'
        
        # 绘制地图
        for y in range(len(display_map)):
            for x in range(len(display_map[0])):
                char = display_map[y][x]
                if char == 'P':
                    self.game_display.insert(tk.END, char, "player")
                elif char == 'N':
                    self.game_display.insert(tk.END, char, "npc")
                elif char == '□':
                    self.game_display.insert(tk.END, char, "town")
                elif char == '^':
                    self.game_display.insert(tk.END, char, "mountain")
                elif char == '~':
                    self.game_display.insert(tk.END, char, "water")
                elif char == 'T':
                    self.game_display.insert(tk.END, char, "tree")
                else:
                    self.game_display.insert(tk.END, char)
            self.game_display.insert(tk.END, "\n")
        
        # 添加标签配置
        self.game_display.tag_config("player", foreground="#f1c40f", font=("Courier New", 12, "bold"))
        self.game_display.tag_config("npc", foreground="#9b59b6", font=("Courier New", 12, "bold"))
        self.game_display.tag_config("town", foreground="#3498db")
        self.game_display.tag_config("mountain", foreground="#95a5a6")
        self.game_display.tag_config("water", foreground="#2980b9")
        self.game_display.tag_config("tree", foreground="#27ae60")
        
        # 显示位置信息
        self.game_display.insert(tk.END, f"\n位置: ({self.player_x}, {self.player_y})")
        self.game_display.insert(tk.END, f"\n时间: {int(self.game_time//3600)}:{int((self.game_time%3600)//60):02d}")
        
        # 检查是否在城镇
        if (self.player_x, self.player_y) in self.town_positions:
            self.game_display.insert(tk.END, "\n你来到了一个城镇。按空格键进入。")
    
    def draw_battle(self):
        """绘制战斗画面"""
        if not self.current_enemy:
            self.game_display.insert(1.0, "没有敌人！\n")
            return
        
        enemy = self.current_enemy
        battle_ascii = f"""
        ╔══════════════════════════════════════════════════════╗
        ║                     战 斗                           ║
        ╠══════════════════════════════════════════════════════╣
        ║                                                      ║
        ║  {enemy.name:^20}                                    ║
        ║  HP: {enemy.hp:>3}/{enemy.max_hp:<3}                                      ║
        ║                                                      ║
        ║              VS                                      ║
        ║                                                      ║
        ║  {self.player.name:^20}                                    ║
        ║  HP: {self.player.hp:>3}/{self.player.max_hp:<3}                                      ║
        ║                                                      ║
        ╚══════════════════════════════════════════════════════╝
        """
        self.game_display.insert(1.0, battle_ascii)
        
        # 显示战斗选项
        self.battle_panel.pack(fill=tk.X, padx=10, pady=5)
    
    def draw_inventory(self):
        """绘制物品栏"""
        self.game_display.insert(1.0, "=== 物品栏 ===\n\n")
        
        if not self.inventory:
            self.game_display.insert(tk.END, "物品栏是空的。\n")
        else:
            for i, item in enumerate(self.inventory):
                usable = "✓" if item.usable_in_battle else " "
                self.game_display.insert(tk.END, 
                    f"{i+1}. [{usable}] {item.name:15} - {item.description}\n")
                self.game_display.insert(tk.END, 
                    f"    类型: {item.type}, 效果: {item.effect_value}\n\n")
        
        self.game_display.insert(tk.END, "\n按数字键使用物品，按ESC返回游戏。")
    
    def draw_town(self):
        """绘制城镇界面"""
        self.game_display.insert(1.0, "=== 城镇 ===\n\n")
        self.game_display.insert(tk.END, "欢迎来到城镇！\n\n")
        self.game_display.insert(tk.END, "1. 商店\n")
        self.game_display.insert(tk.END, "2. 旅馆\n")
        self.game_display.insert(tk.END, "3. 修理店\n")
        self.game_display.insert(tk.END, "4. 离开城镇\n\n")
        self.game_display.insert(tk.END, "请选择选项...")
    
    def draw_shop(self):
        """绘制商店界面"""
        self.game_display.insert(1.0, "=== 商店 ===\n\n")
        self.game_display.insert(tk.END, "欢迎光临！想买点什么？\n\n")
        
        # 显示商品
        for i, item_id in enumerate([1, 2, 3, 4]):
            item_data = self.config_loader.get_item_by_id(item_id)
            if item_data:
                self.game_display.insert(tk.END, 
                    f"{i+1}. {item_data.name:15} - {item_data.price}金币\n")
                self.game_display.insert(tk.END, 
                    f"   {item_data.description}\n\n")
        
        self.game_display.insert(tk.END, "\n按数字键购买，按ESC离开。")
    
    def draw_dialog(self):
        """绘制对话界面"""
        if not self.current_npc:
            return
        
        self.game_display.insert(1.0, f"=== {self.current_npc.name} ===\n\n")
        self.game_display.insert(tk.END, f"{self.current_npc.dialog}\n\n")
        self.game_display.insert(tk.END, "\n按空格键继续...")
    
    def move_player(self, direction):
        """移动玩家"""
        if self.state != GameState.WORLD:
            return
        
        new_x, new_y = self.player_x, self.player_y
        
        if direction == Direction.UP:
            new_y -= 1
        elif direction == Direction.DOWN:
            new_y += 1
        elif direction == Direction.LEFT:
            new_x -= 1
        elif direction == Direction.RIGHT:
            new_x += 1
        
        # 检查边界
        if 0 <= new_x < len(self.current_map[0]) and 0 <= new_y < len(self.current_map):
            # 检查是否可通行
            terrain = self.current_map[new_y][new_x]
            if terrain != '~' and terrain != '^':  # 水和山不能通行
                self.player_x, self.player_y = new_x, new_y
                
                # 检查是否遇到NPC
                for npc in self.config_loader.npcs.values():
                    if (npc.map_id == self.current_map_id and 
                        npc.location_x == new_x and npc.location_y == new_y):
                        self.start_dialog(npc)
                        break
    
    def interact(self):
        """互动"""
        if self.state == GameState.WORLD:
            # 检查是否在城镇
            if (self.player_x, self.player_y) in self.town_positions:
                self.enter_town()
            else:
                # 检查周围是否有敌人
                for dx, dy in [(0,1), (1,0), (0,-1), (-1,0)]:
                    nx, ny = self.player_x + dx, self.player_y + dy
                    # 这里可以添加敌人检测逻辑
                    pass
                
                self.add_log("这里什么都没有。")
        elif self.state == GameState.DIALOG:
            self.state = GameState.WORLD
        elif self.state == GameState.TOWN:
            # 处理城镇选项
            pass
        elif self.state == GameState.SHOP:
            # 处理商店选项
            pass
    
    def start_dialog(self, npc):
        """开始对话"""
        self.current_npc = npc
        self.state = GameState.DIALOG
        self.add_log(f"与{npc.name}交谈")
    
    def enter_town(self):
        """进入城镇"""
        self.state = GameState.TOWN
        self.add_log("进入了城镇。")
    
    def enter_shop(self):
        """进入商店"""
        self.state = GameState.SHOP
        self.add_log("进入了商店。")
    
    def show_settings(self):
        """显示设置"""
        messagebox.showinfo("游戏设置", "设置功能开发中...\n敬请期待！")
    
    def repair_vehicle(self):
        """修理战车"""
        if self.current_vehicle and self.current_vehicle.hp < self.current_vehicle.max_hp:
            cost = (self.current_vehicle.max_hp - self.current_vehicle.hp) * 2
            if self.gold >= cost:
                self.gold -= cost
                self.current_vehicle.hp = self.current_vehicle.max_hp
                self.add_log(f"战车修复完成，花费{cost}金币！")
            else:
                self.add_log(f"金币不足！需要{cost}金币。")
        elif self.current_vehicle:
            self.add_log("战车状态完好，无需修理。")
        else:
            self.add_log("没有战车可以修理。")
    
    def buy_item(self, item_num):
        """购买物品"""
        item_ids = [1, 2, 3, 4]
        if 0 <= item_num < len(item_ids):
            item_data = self.config_loader.get_item_by_id(item_ids[item_num])
            if item_data:
                if self.gold >= item_data.price:
                    self.gold -= item_data.price
                    self.inventory.append(Item(item_data))
                    self.add_log(f"购买了{item_data.name}！")
                else:
                    self.add_log("金币不足！")
    
    def start_random_encounter(self):
        """随机遭遇敌人"""
        enemy_data = self.config_loader.get_random_enemy(self.current_map_id)
        if enemy_data:
            enemy = Enemy(enemy_data)
            self.start_battle(enemy)
            self.add_log(f"遭遇了{enemy.name}！")
    
    def start_battle(self, enemy):
        """开始战斗"""
        self.state = GameState.BATTLE
        self.current_enemy = enemy
        self.battle_panel.pack(fill=tk.X, padx=10, pady=5)
        self.update_battle_text(f"遭遇了{enemy.name}！")
    
    def attack_enemy(self):
        """攻击敌人"""
        if self.state != GameState.BATTLE or not self.current_enemy:
            return
        
        enemy = self.current_enemy
        
        # 玩家攻击
        player_damage = self.player.attack + random.randint(-5, 5)
        actual_damage = enemy.take_damage(player_damage)
        self.update_battle_text(f"{self.player.name}攻击造成{actual_damage}点伤害！")
        
        if not enemy.is_alive():
            self.victory()
            return
        
        # 敌人反击
        enemy_damage = enemy.attack + random.randint(-3, 3)
        actual_damage = self.player.take_damage(enemy_damage)
        self.update_battle_text(f"{enemy.name}反击造成{actual_damage}点伤害！")
        
        if not self.player.is_alive():
            self.game_over()
    
    def defend(self):
        """防御"""
        if self.state != GameState.BATTLE or not self.current_enemy:
            return
        
        self.update_battle_text(f"{self.player.name}采取了防御姿态！")
        # 临时增加防御
        original_defense = self.player.defense
        self.player.defense *= 2
        
        # 敌人攻击
        enemy = self.current_enemy
        enemy_damage = enemy.attack + random.randint(-3, 3)
        actual_damage = self.player.take_damage(enemy_damage)
        self.update_battle_text(f"{enemy.name}攻击造成{actual_damage}点伤害！")
        
        # 恢复防御
        self.player.defense = original_defense
        
        if not self.player.is_alive():
            self.game_over()
    
    def use_item_in_battle(self):
        """在战斗中使用物品"""
        if self.state != GameState.BATTLE:
            return
        
        # 切换到物品界面
        self.state = GameState.INVENTORY
        self.add_log("选择要使用的物品...")
    
    def try_escape(self):
        """尝试逃跑"""
        if self.state != GameState.BATTLE or not self.current_enemy:
            return
        
        escape_chance = self.player.speed / (self.player.speed + self.current_enemy.speed)
        if random.random() < escape_chance:
            self.update_battle_text("成功逃跑了！")
            self.end_battle()
        else:
            self.update_battle_text("逃跑失败！")
            # 敌人攻击
            enemy = self.current_enemy
            enemy_damage = enemy.attack + random.randint(-3, 3)
            actual_damage = self.player.take_damage(enemy_damage)
            self.update_battle_text(f"{enemy.name}攻击造成{actual_damage}点伤害！")
            
            if not self.player.is_alive():
                self.game_over()
    
    def victory(self):
        """胜利"""
        enemy = self.current_enemy
        if enemy is None:
            self.end_battle()
            return
        exp_gained = enemy.exp_reward
        gold_gained = enemy.gold_reward
        
        self.player.gain_exp(exp_gained)
        self.gold += gold_gained
        
        self.update_battle_text(f"胜利！获得{exp_gained}经验和{gold_gained}金币！")
        self.add_log(f"击败了{enemy.name}，获得{exp_gained}经验值！")
        
        # 可能获得物品
        if random.random() < 0.3:
            item_data = random.choice(list(self.config_loader.items.values()))
            self.inventory.append(Item(item_data))
            self.update_battle_text(f"获得了{item_data.name}！")
        
        self.root.after(2000, self.end_battle)
    
    def end_battle(self):
        """结束战斗"""
        self.state = GameState.WORLD
        self.battle_panel.pack_forget()
        self.current_enemy = None
    
    def game_over(self):
        """游戏结束"""
        self.update_battle_text("游戏结束！")
        self.add_log("你战败了...")
        messagebox.showinfo("游戏结束", "你战败了！游戏将重新开始。")
        self.new_game()
    
    def use_item(self, item_index):
        """使用物品"""
        if item_index < 0 or item_index >= len(self.inventory):
            return
        
        item = self.inventory[item_index]
        
        if item.type == "heal":
            heal_amount = item.effect_value
            self.player.heal(heal_amount)
            self.add_log(f"使用了{item.name}，恢复了{heal_amount}点HP！")
            
            # 从背包移除
            self.inventory.pop(item_index)
            
            if self.state == GameState.INVENTORY:
                self.update_display()
        elif item.type == "fuel":
            if self.current_vehicle:
                refuel_amount = item.effect_value
                self.current_vehicle.fuel = min(
                    self.current_vehicle.max_fuel, 
                    self.current_vehicle.fuel + refuel_amount
                )
                self.add_log(f"使用了{item.name}，恢复了{refuel_amount}点燃料！")
                self.inventory.pop(item_index)
                if self.state == GameState.INVENTORY:
                    self.update_display()
            else:
                self.add_log("没有战车可以使用燃料！")
    
    def open_inventory(self):
        """打开物品栏"""
        if self.state == GameState.BATTLE:
            self.state = GameState.INVENTORY
        elif self.state == GameState.WORLD:
            self.state = GameState.INVENTORY
        self.add_log("打开物品栏...")
    
    def open_vehicles(self):
        """打开战车管理"""
        self.add_log("打开战车管理...")
        vehicle_info = "战车信息:\n"
        for i, vehicle in enumerate(self.vehicles):
            status = "损坏" if vehicle.broken else f"燃料:{vehicle.fuel}/{vehicle.max_fuel}"
            vehicle_info += f"{i+1}. {vehicle.name}: HP {vehicle.hp}/{vehicle.max_hp} {status}\n"
        
        messagebox.showinfo("战车", vehicle_info)
    
    def rest(self):
        """休息"""
        if self.state != GameState.WORLD:
            return
        
        if (self.player_x, self.player_y) in self.town_positions:
            self.player.heal(self.player.max_hp)
            if self.current_vehicle:
                self.current_vehicle.fuel = self.current_vehicle.max_fuel
            self.add_log("在旅馆休息后，HP和燃料都恢复了！")
        else:
            self.add_log("只能在城镇里休息。")
    
    def save_game(self):
        """保存游戏"""
        self.add_log("游戏已保存（演示版不实际保存）")
        messagebox.showinfo("保存", "游戏已保存！")
    
    def load_game(self):
        """加载游戏"""
        self.add_log("游戏已加载（演示版不实际加载）")
        messagebox.showinfo("加载", "游戏已加载！")
    
    def new_game(self):
        """新游戏"""
        self.player = Character("雷班纳", 100, 100, 15, 8, 12)
        self.gold = 500
        self.player_x, self.player_y = 10, 10
        self.inventory = []
        self.vehicles = []
        self.active_quests = []
        self.completed_quests = []
        self.game_time = 0
        self.state = GameState.WORLD
        
        # 重新初始化
        self.init_game_data()
        self.add_log("新游戏开始！")
    
    def update_battle_text(self, text):
        """更新战斗文本"""
        self.battle_text.config(state=tk.NORMAL)
        self.battle_text.delete(1.0, tk.END)
        self.battle_text.insert(1.0, text)
        self.battle_text.config(state=tk.DISABLED)
    
    def add_log(self, message):
        """添加日志"""
        if not hasattr(self, 'log_messages'):
            self.log_messages = []
        
        timestamp = f"[{int(self.game_time//60):02d}:{int(self.game_time%60):02d}] "
        self.log_messages.append(timestamp + message)
        
        # 只保留最近10条消息
        if len(self.log_messages) > 10:
            self.log_messages.pop(0)
    
    def get_recent_logs(self):
        """获取最近的日志"""
        if not hasattr(self, 'log_messages'):
            return []
        return self.log_messages[-5:]  # 返回最近5条
    
    def on_click(self, event):
        """处理鼠标点击"""
        # 获取点击位置的字符坐标
        index = self.game_display.index(f"@{event.x},{event.y}")
        line, char = map(int, index.split('.'))
        
        if self.state == GameState.WORLD:
            # 计算点击的地图位置
            map_x = char
            map_y = line - 1
            
            if 0 <= map_x < len(self.current_map[0]) and 0 <= map_y < len(self.current_map):
                self.add_log(f"点击了位置({map_x}, {map_y})")
    
    def show_help(self):
        """显示帮助"""
        help_text = """
        操作说明：
        方向键：移动角色
        空格键：互动/确认
        I键：打开物品栏
        V键：查看战车
        R键：休息（仅在城镇）
        S键：保存游戏
        ESC键：返回/打开菜单
        数字键：选择选项
        
        游戏提示：
        - 探索世界，击败敌人
        - 收集金钱和装备
        - 升级角色能力
        - 修复和升级战车
        """
        messagebox.showinfo("操作说明", help_text)
    
    def show_about(self):
        """显示关于"""
        about_text = """
        重装机兵同人游戏
        Metal Max Fan Game
        
        基于Python + Tkinter开发
        ASCII艺术风格
        
        致敬经典RPG游戏《重装机兵》
        本作为非商业同人作品
        """
        messagebox.showinfo("关于", about_text)

def main():
    """主函数"""
    root = tk.Tk()
    game = MMGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()