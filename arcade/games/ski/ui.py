"""UI 渲染层 - 负责所有 tkinter 界面绘制与显示。

性能优化要点（参考 tkinter Canvas/Text 性能反模式）：
1. 取消「每像素 delete + insert」的逐字符绘制；
   改为构建内存二维网格 → 整帧一次写入 → 仅对彩色单元打 tag。
2. 背景道路仅在每行写一次（拼接字符串）。
3. 渲染状态分离：snapshot 输入 → 网格 → 文本，纯函数式无副作用。

视觉增强：
- HUD：分数 / 距离 / 速度 / 风格分 / 加速槽 / 雪人警告 / 难度
- 开始画面：标题 + 模式选择 + 图例 + 控制说明
- 撞击特效：撞树/吃旗子/跳跃/加速 各有视觉提示
- 雪人逼近时屏幕底部红色警告条
- 游戏结束画面：分类统计 + 高分对比 + 死因
"""

from __future__ import annotations

import tkinter as tk

from config import (
    BOOST_COOLDOWN,
    COLOR_TAGS,
    HEIGHT,
    JUMP_STYLE_BONUS,
    MODE_DESCRIPTIONS,
    MODE_ENDLESS,
    MODE_NAMES,
    OBSTACLE_TYPES,
    ROAD_CHAR,
    SNOW_CHAR,
    WIDTH,
    YETI_TRIGGER_DISTANCE,
)


class GameUI:
    """游戏界面：创建和管理所有 tkinter 控件，根据引擎快照渲染画面。"""

    # 颜色 → tag 名（tkinter tag 名不能含 '#'，故映射为短名）
    _COLOR_TAG_MAP = {
        "red": "c_red",
        "blue": "c_blue",
        "green": "c_green",
        "gray": "c_gray",
        "black": "c_black",
        "yellow": "c_yellow",
        "magenta": "c_magenta",
        "cyan": "c_cyan",
        "orange": "c_orange",
        "white": "c_white",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ASCII 滑雪游戏 · SkiFree 增强版")
        self.width = WIDTH
        self.height = HEIGHT

        # 当前选中的模式（开始菜单用）
        self.selected_mode = MODE_ENDLESS

        self._setup_ui()

    # ========== 界面构建 ==========

    def _setup_ui(self):
        """创建所有 UI 控件并配置颜色标签。"""
        # 顶部 HUD 区
        self.hud_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.hud_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

        self.hud_label = tk.Label(
            self.hud_frame,
            text="",
            font=("Courier", 11),
            bg="#1a1a2e",
            fg="#e0e0e0",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.hud_label.pack(fill=tk.X, padx=6, pady=2)

        # 游戏画布（Text 控件模拟 ASCII 网格）
        self.game_canvas = tk.Text(
            self.root,
            width=self.width,
            height=self.height,
            font=("Courier", 12),
            bg="#0f0f1a",
            fg="#cfcfcf",
            insertbackground="#cfcfcf",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=6,
            wrap=tk.NONE,
        )
        self.game_canvas.pack(padx=4, pady=2)
        self.game_canvas.configure(state=tk.NORMAL)

        # 配置颜色 tag
        for color_name, hex_val in COLOR_TAGS.items():
            tag = self._COLOR_TAG_MAP.get(color_name, "c_black")
            self.game_canvas.tag_configure(tag, foreground=hex_val)

        # 控制说明底栏
        self.controls_label = tk.Label(
            self.root,
            text=(
                "←/→ 或 A/D 转弯  |  F 加速  |  P 暂停  |  T 单帧步进  |  "
                "1/2/3 选模式  |  R 重开"
            ),
            font=("Courier", 9),
            bg="#1a1a2e",
            fg="#9e9e9e",
        )
        self.controls_label.pack(fill=tk.X, padx=4, pady=(2, 4))

    # ========== 画布操作 ==========

    def _write_frame(self, grid: list[list[str]], color_grid: list[list[str]]):
        """一次性写入整帧文本，再用 tag_add 批量着色。

        Args:
            grid: 二维字符网格 [y][x] -> 单字符
            color_grid: 同形状 [y][x] -> 颜色名（"" 表示默认色）
        """
        # 1. 一次性清空 + 写入所有行（按 \\n 拼接）
        self.game_canvas.delete("1.0", tk.END)
        lines = ["".join(row) for row in grid]
        full_text = "\n".join(lines)
        self.game_canvas.insert("1.0", full_text)

        # 2. 仅对「非默认色」单元批量打 tag
        for y, row in enumerate(color_grid):
            for x, color_name in enumerate(row):
                if not color_name:
                    continue
                tag = self._COLOR_TAG_MAP.get(color_name, "c_black")
                # Text 索引：行从 1 开始，列从 0 开始
                start = f"{y + 1}.{x}"
                end = f"{y + 1}.{x + 1}"
                self.game_canvas.tag_add(tag, start, end)

    # ========== 画面渲染 ==========

    def render(self, snapshot: dict):
        """根据引擎状态快照绘制完整游戏画面。"""
        # 1. 构建二维网格（道路背景）
        grid = [[SNOW_CHAR] * self.width for _ in range(self.height)]
        color_grid: list[list[str]] = [[""] * self.width for _ in range(self.height)]

        # 道路：每隔 4 格放一个点，营造雪地纹理（减少字符数，提升性能）
        for y in range(self.height):
            for x in range(0, self.width, 4):
                grid[y][x] = ROAD_CHAR
                color_grid[y][x] = "gray"

        # 2. 障碍物
        for obstacle in snapshot["obstacles"]:
            x, y, obstacle_type, _ = obstacle
            if not (0 <= y < self.height and 0 <= x < self.width):
                continue
            cfg = OBSTACLE_TYPES.get(obstacle_type)
            if cfg is None:
                continue
            grid[y][x] = cfg["char"]
            color_grid[y][x] = cfg["color"]

        # 3. 雪人
        if snapshot["yeti_active"]:
            yy = snapshot["yeti_y"]
            if 0 <= yy < self.height:
                # 雪人占 2 行：顶部头 + 底部身
                grid[yy][snapshot["skier_x"]] = ""  # 占位
                # 写雪人字符
                grid[yy][max(0, snapshot["skier_x"] - 1)] = "☃"
                color_grid[yy][max(0, snapshot["skier_x"] - 1)] = "orange"
                # 警告条
                self._draw_yeti_warning(grid, color_grid, yy)

        # 4. 滑雪者
        sx, sy = snapshot["skier_x"], snapshot["skier_y"]
        if 0 <= sx < self.width and 0 <= sy < self.height:
            grid[sy][sx] = snapshot["skier_char"]
            # 跳跃/加速时给个发光色
            if snapshot["jumping"]:
                color_grid[sy][sx] = "yellow"
            elif snapshot["boosting"]:
                color_grid[sy][sx] = "cyan"
            else:
                color_grid[sy][sx] = "blue"

        # 5. 写入画布
        self._write_frame(grid, color_grid)

        # 6. 更新 HUD
        self._update_hud(snapshot)

        self.root.update_idletasks()
        self.root.update()

    def _draw_yeti_warning(self, grid, color_grid, yeti_y: int):
        """在屏幕底部画雪人警告条（距离越近越红）。"""
        # 警告强度：雪人越靠上越危险
        danger = max(0, 1 - yeti_y / self.height)
        if danger < 0.3:
            return  # 太远不画
        warn_row = self.height - 1
        warn_color = "red" if danger > 0.6 else "orange"
        for x in range(self.width):
            grid[warn_row][x] = "▔"
            color_grid[warn_row][x] = warn_color

    def _update_hud(self, snapshot: dict):
        """更新顶部 HUD 信息条。"""
        # 加速槽
        boost_pct = 0
        if snapshot["boosting"]:
            boost_pct = int(snapshot.get("boost_cooldown", 0))
        elif snapshot.get("boost_cooldown", 0) > 0:
            boost_pct = -int(snapshot["boost_cooldown"])  # 冷却中显示负值

        boost_bar_full = 10
        if snapshot["boosting"]:
            filled = boost_bar_full
            boost_str = "▓" * filled + " 加速中"
        elif snapshot.get("boost_cooldown", 0) > 0:
            cd = snapshot["boost_cooldown"]
            cd_max = snapshot.get("boost_cooldown_max", BOOST_COOLDOWN)
            filled = int(boost_bar_full * (1 - cd / cd_max))
            boost_str = "░" * boost_bar_full + f" 冷却({cd})"
        else:
            boost_str = "▓" * boost_bar_full + " 就绪"

        # 雪人警告
        yeti_warn = ""
        if snapshot["yeti_active"]:
            yy = snapshot["yeti_y"]
            gap = yy - snapshot["skier_y"]
            if gap <= 3:
                yeti_warn = "  ⚠ 雪人即将追上！"
            else:
                yeti_warn = f"  雪人距离 {gap} 行"

        mode_name = MODE_NAMES.get(snapshot.get("mode", MODE_ENDLESS), "")

        hud_text = (
            f"分数 {snapshot['score']:>5}   "
            f"距离 {int(snapshot['distance']):>4}m   "
            f"风格 {snapshot.get('style_score', 0):>4}   "
            f"速度 Lv{snapshot.get('difficulty', 1)}   "
            f"[{mode_name}]   "
            f"加速[{boost_str}]{yeti_warn}"
        )
        self.hud_label.config(text=hud_text)

    def show_crash_effect(self, kind: str = "tree"):
        """显示撞击效果画面。"""
        self.game_canvas.delete("1.0", tk.END)
        msgs = {
            "tree": ("✗ 撞到树了! -50 分", "red"),
            "rock": ("✗ 撞到岩石! -30 分", "gray"),
            "flag": ("✦ 收集旗子! +10 分", "yellow"),
            "jump": ("▲ 起跳!", "magenta"),
        }
        text, color = msgs.get(kind, msgs["tree"])
        tag = self._COLOR_TAG_MAP.get(color, "c_red")
        y = self.height // 2
        x = (self.width - len(text)) // 2
        self.game_canvas.insert("1.0", "\n" * y + " " * x + text)
        start = f"{y + 1}.{x}"
        end = f"{y + 1}.{x + len(text)}"
        self.game_canvas.tag_add(tag, start, end)
        self.root.update()

    # ========== 画面场景 ==========

    def show_start_screen(self, high_score: int = 0, mode: str = MODE_ENDLESS):
        """显示开始界面（含模式选择）。"""
        self.selected_mode = mode
        grid = [[SNOW_CHAR] * self.width for _ in range(self.height)]
        color_grid: list[list[str]] = [[""] * self.width for _ in range(self.height)]

        title = "╔══════════════════════════════════╗"
        title2 = "║   ASCII 滑雪游戏 · SkiFree 增强版   ║"
        title3 = "╚══════════════════════════════════╝"

        lines = [
            (title, "cyan"),
            (title2, "yellow"),
            (title3, "cyan"),
            ("", ""),
            ("选择模式 (1/2/3 切换)：", "green"),
            (f"  ▶ {MODE_NAMES[MODE_ENDLESS]}  -  {MODE_DESCRIPTIONS[MODE_ENDLESS]}", 
             "yellow" if mode == MODE_ENDLESS else "white"),
            (f"  ▶ {MODE_NAMES['slalom']}  -  {MODE_DESCRIPTIONS['slalom']}", 
             "yellow" if mode == "slalom" else "white"),
            (f"  ▶ {MODE_NAMES['freestyle']}  -  {MODE_DESCRIPTIONS['freestyle']}", 
             "yellow" if mode == "freestyle" else "white"),
            ("", ""),
            (f"当前模式：{MODE_NAMES[mode]}    历史最高：{high_score}", "magenta"),
            ("", ""),
            ("按 空格/回车 开始游戏", "green"),
            ("", ""),
            ("── 图例 ──────────────────────────", "gray"),
            ("▲ 滑雪者        ♣ 树 (-50)        ● 岩石 (-30)", "blue"),
            ("¶ 旗子 (+10)    ♦ 跳台 (起跳)      ☃ 雪人 (致命!)", "red"),
            ("", ""),
            ("── 控制 ──────────────────────────", "gray"),
            ("←/→ 或 A/D 转弯    F 加速    P 暂停    T 单帧    R 重开", "white"),
        ]

        start_y = (self.height - len(lines)) // 2
        for i, (text, color) in enumerate(lines):
            y = start_y + i
            if 0 <= y < self.height:
                x = max(0, (self.width - len(text)) // 2)
                for j, ch in enumerate(text):
                    if x + j < self.width:
                        grid[y][x + j] = ch
                        if color:
                            color_grid[y][x + j] = color

        self._write_frame(grid, color_grid)
        self.hud_label.config(text=f"准备就绪 · 模式 {MODE_NAMES[mode]} · 最高分 {high_score}")
        self.root.update()

    def show_game_over(self, snapshot: dict, high_score: int = 0, is_new_record: bool = False):
        """显示游戏结束画面（含分类统计）。"""
        grid = [[SNOW_CHAR] * self.width for _ in range(self.height)]
        color_grid: list[list[str]] = [[""] * self.width for _ in range(self.height)]

        reason_text = {
            "score": "分数过低，game over",
            "yeti": "☃ 被雪人吃掉了！",
        }.get(snapshot.get("death_reason"), "游戏结束")

        lines = [
            ("╔══════════════════════════════╗", "red"),
            ("║        游 戏 结 束          ║", "red"),
            ("╚══════════════════════════════╝", "red"),
            ("", ""),
            (f"死因：{reason_text}", "orange"),
            ("", ""),
            ("── 本局战绩 ──────────────────", "gray"),
            (f"  最终分数：  {snapshot['score']}", "yellow"),
            (f"  滑行距离：  {int(snapshot['distance'])} m", "blue"),
            (f"  风格分：    {snapshot.get('style_score', 0)}", "magenta"),
            (f"  最高难度：  Lv{snapshot.get('difficulty', 1)}", "cyan"),
            (f"  游戏模式：  {MODE_NAMES.get(snapshot.get('mode', ''), '')}", "green"),
            ("", ""),
            (f"历史最高分：{high_score}", "magenta"),
            ("★ 新纪录！恭喜 ★" if is_new_record else "", "yellow"),
            ("", ""),
            ("按 R 重新开始    按 ESC 返回主菜单", "green"),
        ]

        start_y = (self.height - len(lines)) // 2
        for i, (text, color) in enumerate(lines):
            y = start_y + i
            if 0 <= y < self.height:
                x = max(0, (self.width - len(text)) // 2)
                for j, ch in enumerate(text):
                    if x + j < self.width:
                        grid[y][x + j] = ch
                        if color:
                            color_grid[y][x + j] = color

        self._write_frame(grid, color_grid)
        self.hud_label.config(text="游戏结束 · 按 R 重开 / ESC 返回菜单")
        self.root.update()

    def show_paused(self):
        """显示暂停遮罩。"""
        # 在现有画面上叠加暂停文字（不清屏，保留游戏画面）
        overlay = "▒▒▒ 暂停中 · 按 P 继续 · 按 T 单帧步进 ▒▒▒"
        y = self.height // 2
        x = max(0, (self.width - len(overlay)) // 2)
        self.game_canvas.insert(tk.END, "\n" + " " * x + overlay)
        self.root.update()
