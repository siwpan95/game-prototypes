"""主窗口 — 组装所有 View 组件，绑定 ViewModel"""
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import TYPE_CHECKING

from model import GameState, Direction, MapManager, VIEWPORT_H, VIEWPORT_W
from .components import TaggedTextDisplay, InfoPanel, ButtonBar, show_messagebox

if TYPE_CHECKING:
    from viewmodel import GameViewModel


class MainWindow:
    """游戏主窗口 View — 只负责 Tkinter 渲染和用户输入转发"""

    def __init__(self, root: tk.Tk, vm: "GameViewModel"):
        self.root = root
        self.vm = vm

        self._setup_window()
        self._create_widgets()
        self._bind_vm_properties()
        self._bind_keys()
        self._bind_mouse()

        # 启动 VM 回调
        vm.on_game_over = self._on_game_over
        vm.on_state_changed = self._on_state_changed

    def _setup_window(self):
        self.root.title("重装机兵同人 - Metal Max Fan Game [MVVM]")
        self.root.geometry("1000x750")
        self.root.resizable(False, False)

    # ═══════════════════════════════════════════════════
    # 创建控件
    # ═══════════════════════════════════════════════════

    def _create_widgets(self):
        # 主容器
        self.main_frame = tk.Frame(self.root, bg="#2c3e50")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 游戏显示区域
        self.game_frame = tk.Frame(self.main_frame, bg="black", bd=2, relief=tk.RAISED)
        self.game_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.game_display = TaggedTextDisplay(self.game_frame)
        self.game_display.pack(padx=5, pady=5)

        # 右侧信息面板
        self.info_panel = InfoPanel(self.main_frame)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # 玩家信息
        self.player_info = tk.Label(self.info_panel,
                                    bg="#34495e", fg="#f1c40f",
                                    font=("Arial", 12, "bold"), anchor=tk.W,
                                    textvariable=self.vm.player_name_text)
        self.player_info.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.stats_label = tk.Label(self.info_panel,
                                    bg="#34495e", fg="#ecf0f1",
                                    font=("Arial", 10), justify=tk.LEFT, anchor=tk.W,
                                    textvariable=self.vm.stats_text)
        self.stats_label.pack(fill=tk.X, padx=10, pady=5)

        # 战车信息
        self.vehicle_label = tk.Label(self.info_panel,
                                      bg="#34495e", fg="#3498db",
                                      font=("Arial", 10), justify=tk.LEFT, anchor=tk.W,
                                      textvariable=self.vm.vehicle_text)
        self.vehicle_label.pack(fill=tk.X, padx=10, pady=5)

        self.info_panel.add_separator()

        # 消息日志
        self.info_panel.add_section_label("消息日志")
        self.log_text = tk.Text(self.info_panel, bg="#2c3e50", fg="#bdc3c7",
                                font=("Arial", 9), height=8, width=32,
                                state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 追踪日志更新
        self.vm.log_text.trace_add("write", self._update_log_display)

        # 控制按钮
        buttons = [
            ("物品(I)", lambda: self.vm.command_open_inventory()),
            ("战车(V)", self._show_vehicles),
            ("任务(Q)", lambda: self.vm.command_show_quests()),
            ("休息(R)", lambda: self.vm.command_rest()),
        ]
        ButtonBar(self.info_panel, buttons).pack(fill=tk.X, padx=10, pady=5)

        # 战斗面板（初始隐藏）
        self._create_battle_panel()

        # 技能面板（战斗中显示）
        self._create_skill_panel()

        # 菜单栏
        self._create_menu_bar()

    def _create_battle_panel(self):
        self.battle_panel = tk.Frame(self.info_panel, bg="#34495e")

        self.battle_text = tk.Text(self.battle_panel, bg="#2c3e50", fg="#e74c3c",
                                   font=("Courier New", 10), height=6, width=32,
                                   state=tk.DISABLED)
        self.battle_text.pack(fill=tk.X, padx=10, pady=5)

        battle_frame = tk.Frame(self.battle_panel, bg="#34495e")
        battle_frame.pack(fill=tk.X, padx=10, pady=5)

        battle_buttons = [
            ("攻击(1)", lambda: self.vm.command_attack()),
            ("防御(2)", lambda: self.vm.command_defend()),
            ("道具(3)", lambda: self.vm.command_open_inventory()),
            ("逃跑(4)", lambda: self.vm.command_escape()),
        ]
        for text, cmd in battle_buttons:
            tk.Button(battle_frame, text=text, command=cmd,
                      bg="#e74c3c", fg="white",
                      font=("Arial", 9), width=8).pack(side=tk.LEFT, padx=2)

    def _create_skill_panel(self):
        """创建技能面板（战斗中动态生成技能按钮）"""
        self.skill_panel = tk.Frame(self.info_panel, bg="#34495e")

        self.skill_buttons_frame = tk.Frame(self.skill_panel, bg="#34495e")
        self.skill_buttons_frame.pack(fill=tk.X, padx=10, pady=2)

        self.skill_label = tk.Label(self.skill_panel,
                                    bg="#34495e", fg="#f39c12",
                                    font=("Arial", 9, "bold"), anchor=tk.W,
                                    text="技能:")
        self.skill_label.pack(fill=tk.X, padx=10, pady=(5, 0))

    def _create_menu_bar(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="新游戏", command=self._on_new_game)
        file_menu.add_command(label="保存游戏", command=self._on_save)
        file_menu.add_command(label="加载游戏", command=self._on_load)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menu_bar.add_cascade(label="游戏", menu=file_menu)

        quest_menu = tk.Menu(menu_bar, tearoff=0)
        quest_menu.add_command(label="任务日志", command=lambda: self.vm.command_show_quests())
        menu_bar.add_cascade(label="任务", menu=quest_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="操作说明", command=self._show_help)
        help_menu.add_command(label="关于", command=self._show_about)
        menu_bar.add_cascade(label="帮助", menu=help_menu)

    # ═══════════════════════════════════════════════════
    # VM 属性绑定
    # ═══════════════════════════════════════════════════

    def _bind_vm_properties(self):
        """将 VM 的 Observable 属性绑定到 View 控件"""
        self.vm.display_text.trace_add("write", self._on_display_changed)
        self.vm.battle_text.trace_add("write", self._on_battle_text_changed)
        self.vm.battle_visible.trace_add("write", self._on_battle_visible_changed)
        self.vm.skill_visible.trace_add("write", self._on_skill_visible_changed)

    def _on_display_changed(self, *args):
        text = self.vm.display_text.get()
        self.game_display.set_content(text)

    def _on_battle_text_changed(self, *args):
        text = self.vm.battle_text.get()
        self.battle_text.config(state=tk.NORMAL)
        self.battle_text.delete(1.0, tk.END)
        self.battle_text.insert(1.0, text)
        self.battle_text.config(state=tk.DISABLED)

    def _on_battle_visible_changed(self, *args):
        if self.vm.battle_visible.get():
            self.battle_panel.pack(fill=tk.X, padx=10, pady=5)
            self._refresh_skill_buttons()
        else:
            self.battle_panel.pack_forget()
            self.skill_panel.pack_forget()

    def _on_skill_visible_changed(self, *args):
        """技能面板可见性变更"""
        if self.vm.skill_visible.get() and self.vm.battle_visible.get():
            self.skill_panel.pack(fill=tk.X, padx=10, pady=2)
            self._refresh_skill_buttons()
        else:
            self.skill_panel.pack_forget()

    def _refresh_skill_buttons(self):
        """刷新技能按钮（根据玩家当前技能列表）"""
        for widget in self.skill_buttons_frame.winfo_children():
            widget.destroy()

        player = self.vm.data.player
        if not player:
            return

        for i, skill in enumerate(player.skills[:5]):
            idx = i
            btn = tk.Button(self.skill_buttons_frame,
                           text=f"{skill.name}({5+i})",
                           command=lambda j=idx: self.vm.command_use_skill(j),
                           bg="#f39c12", fg="white",
                           font=("Arial", 8), width=10)
            btn.pack(side=tk.LEFT, padx=1)

    def _update_log_display(self, *args):
        text = self.vm.log_text.get()
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(1.0, text)
        self.log_text.config(state=tk.DISABLED)

    def _on_state_changed(self, state: GameState):
        """状态变更时更新战斗面板可见性"""
        # battle_visible 已通过 BooleanVar 自动处理
        pass

    # ═══════════════════════════════════════════════════
    # 键盘绑定
    # ═══════════════════════════════════════════════════

    def _bind_keys(self):
        root = self.root
        root.bind("<Up>", lambda e: self.vm.command_move(Direction.UP))
        root.bind("<Down>", lambda e: self.vm.command_move(Direction.DOWN))
        root.bind("<Left>", lambda e: self.vm.command_move(Direction.LEFT))
        root.bind("<Right>", lambda e: self.vm.command_move(Direction.RIGHT))
        root.bind("<space>", lambda e: self.vm.command_interact())
        root.bind("<Escape>", self._on_escape)
        root.bind("<i>", lambda e: self.vm.command_open_inventory())
        root.bind("<v>", lambda e: self._show_vehicles())
        root.bind("<q>", lambda e: self.vm.command_show_quests())
        root.bind("<r>", lambda e: self.vm.command_rest())
        root.bind("<s>", lambda e: self._on_save())
        root.bind("<Key>", self._handle_key)

    def _on_escape(self, event):
        d = self.vm.data
        if d.state == GameState.MENU:
            if d.player is not None:
                d.state = GameState.WORLD  # 有进度时 ESC 返回游戏（暂停菜单）
            else:
                self.root.quit()
        elif d.state == GameState.BATTLE:
            d.add_log("战斗中不能退出！")
        elif d.state == GameState.WORLD:
            d.state = GameState.MENU
        else:
            self.vm.command_handle_escape()

    def _handle_key(self, event):
        d = self.vm.data
        if d.state == GameState.MENU:
            if event.char == '1':
                self._on_new_game()
            elif event.char == '2':
                self._on_load()
            elif event.char == '3':
                self.vm.command_show_quests()
            elif event.char == '4':
                self.root.quit()
        elif d.state == GameState.INVENTORY:
            if event.char.isdigit():
                idx = int(event.char) - 1
                # 序号范围：物品栏 + 已装备区（续排编号用于卸下）
                max_idx = len(d.inventory) + len(d.player.equipped_slots()) - 1
                if 0 <= idx <= max_idx:
                    self.vm.command_use_item(idx)
        elif d.state == GameState.BATTLE:
            if event.char == '1':
                self.vm.command_attack()
            elif event.char == '2':
                self.vm.command_defend()
            elif event.char == '3':
                self.vm.command_open_inventory()
            elif event.char == '4':
                self.vm.command_escape()
            elif event.char in '56789':
                skill_idx = int(event.char) - 5
                if skill_idx < len(d.player.skills):
                    self.vm.command_use_skill(skill_idx)
        elif d.state == GameState.TOWN:
            if event.char == '1':
                self.vm.command_enter_shop()
            elif event.char == '2':
                self.vm.command_rest()
            elif event.char == '3':
                self.vm.command_repair_vehicle()
            elif event.char == '4':
                self.vm.command_leave_town()
        elif d.state == GameState.SHOP:
            if event.char.isdigit():
                self.vm.command_buy_item(int(event.char) - 1)
        elif d.state == GameState.DIALOG:
            # 对话中按任意键继续（任务日志也复用此状态）
            self.vm.command_interact()

    def _bind_mouse(self):
        self.game_display.bind("<Button-1>", self._on_click)

    def _on_click(self, event):
        if self.vm.data.state == GameState.WORLD:
            index = self.game_display.index(f"@{event.x},{event.y}")
            line, char = map(int, index.split('.'))
            d = self.vm.data
            # 视口原点换算：与 MapManager.get_viewport_origin 保持一致
            origin_x, origin_y, pad_x, pad_y = MapManager.get_viewport_origin(d)
            world_x = origin_x + (char - pad_x)
            world_y = origin_y + ((line - 1) - pad_y)
            if 0 <= line - 1 < VIEWPORT_H and 0 <= char < VIEWPORT_W:
                d.add_log(f"点击了位置({world_x}, {world_y})")

    # ═══════════════════════════════════════════════════
    # UI 回调
    # ═══════════════════════════════════════════════════

    def _on_new_game(self):
        self.vm.command_new_game()

    def _ask_slot(self, title: str):
        """弹出槽位选择框（1-3），取消返回 None"""
        return simpledialog.askinteger(
            title, "选择存档槽位 (1-3)：",
            minvalue=1, maxvalue=3, parent=self.root
        )

    def _on_save(self):
        slot = self._ask_slot("保存游戏")
        if slot is None:
            return
        ok = self.vm.command_save(slot)
        if ok:
            show_messagebox("保存", f"游戏已保存到槽位 {slot}。")
        else:
            show_messagebox("保存", "保存失败！战斗中或主菜单下无法保存。", kind="warning")

    def _on_load(self):
        slot = self._ask_slot("读取游戏")
        if slot is None:
            return
        if not self.vm.has_save(slot):
            show_messagebox("读取", f"槽位 {slot} 没有存档。", kind="warning")
            return
        ok = self.vm.command_load(slot)
        if ok:
            show_messagebox("读取", f"已读取槽位 {slot} 的存档。")
        else:
            show_messagebox("读取", "读取失败！存档可能已损坏。", kind="error")

    def _show_vehicles(self):
        d = self.vm.data
        d.add_log("打开战车管理...")
        lines = ["战车信息:"]
        for i, v in enumerate(d.vehicles):
            status = "损坏" if v.broken else f"燃料:{v.fuel}/{v.max_fuel}"
            lines.append(f"{i+1}. {v.name}: HP {v.hp}/{v.max_hp} {status}")
        show_messagebox("战车", "\n".join(lines))

    def _on_game_over(self):
        show_messagebox("游戏结束", "你战败了！游戏将重新开始。")
        self._on_new_game()

    def _show_help(self):
        show_messagebox("操作说明", """
        操作说明：
        方向键：移动角色
        空格键：互动/确认
        I键：打开物品栏
        V键：查看战车
        Q键：任务日志
        R键：休息（仅在城镇）
        ESC键：返回/打开菜单
        数字键：选择选项
        5-9键：战斗中释放技能
        
        游戏提示：
        - 探索无限世界，击败敌人
        - 学习技能，在战斗中释放
        - 完成任务获取丰厚奖励
        - 乘坐战车获得属性加成
        - 收集金钱和装备
        - 升级角色能力
        """)

    def _show_about(self):
        show_messagebox("关于", """
        重装机兵同人游戏
        Metal Max Fan Game
        
        基于Python + Tkinter开发（MVVM架构）
        ASCII艺术风格
        
        致敬经典RPG游戏《重装机兵》
        本作为非商业同人作品
        """)

    def run(self):
        """启动游戏循环并进入主循环"""
        self.vm.init_new_game()
        self.vm.start_game_loop(self.root)
        self.root.mainloop()
