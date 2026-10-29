"""gui.py — 地牢冒险者 图形界面版（tkinter）。

在现有 Game 类之上包装一层 GUI，不改动任何游戏逻辑：
  python gui.py                # 默认种子 20260717，5 层
  python gui.py --seed 7       # 指定种子
  python gui.py --floors 8     # 指定层数

操作（与控制台版一致，也可直接点按钮）：
  移动：W/A/S/D 或 方向键   拾取 G   装备/背包 E、I
  喝药 U   下层 >（站楼梯上）  帮助 ?   退出 Q
  战斗：1 攻击 / 2 防御 / 3 逃跑（或点按钮）
"""
from __future__ import annotations

import argparse
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import Game
from entities import Position, MobBrain, BOSS_ART
from progression import apply_perk, roll_perk_choices, PERK_MAP
from alloy.utils.font import (
    load_local_tk_font, get_default_local_font_name,
)

# ── 配色 ──────────────────────────────────────────────────
COL_BG = "#14141f"
COL_WALL = "#1b1b2e"
COL_WALL_FG = "#262640"
COL_FLOOR = "#23233a"
COL_FLOOR_FG = "#2f2f4a"
COL_STAIRS = "#16321f"
COL_STAIRS_FG = "#46d17a"
COL_ITEM = "#3a2e10"
COL_ITEM_FG = "#f2c14e"
COL_MON = "#3a1414"
COL_MON_FG = "#ff5a5a"
COL_PLAYER = "#3a3410"
COL_PLAYER_FG = "#ffe14e"
# 稀有度配色（tkinter 友好 hex，顺序对应 affixes.RARITY 的 ANSI）
RARITY_HEX = {
    "common":    "#dfe6f5",
    "magic":     "#4fd6e0",
    "rare":      "#5a8cff",
    "epic":      "#d36cff",
    "legendary": "#ffd24a",
}
COL_TRAP_SPIKE = "#9aa3b2"
COL_TRAP_LAVA  = "#ff7a3c"
COL_RANGED     = "#c08bff"   # 远程怪高亮（提示会被放风筝）
CELL = 18
FONT = ("Consolas", 12, "bold")


class DungeonGUI:
    def __init__(self, root: tk.Tk, seed: int, floors: int):
        self.root = root
        self.root.title("地牢冒险者 — 图形界面版")
        self.root.configure(bg=COL_BG)
        self.root.resizable(False, False)

        # 品牌字体：优先使用包内手写体（fonts/），失败回退系统字体
        self.brand_font = self._load_brand_font()


        self.game = Game(seed=seed, floors=floors)
        self.busy = False  # 弹窗（背包/新游戏）打开时屏蔽键盘
        self._boss_art_shown = False  # BOSS 立绘只弹一次

        self._build_menu()
        self._build_widgets()
        self._bind_keys()
        self.refresh_all()

    # ──────────────────────────────────────────────────
    #  本地字体（包内手写体）
    # ──────────────────────────────────────────────────
    def _load_brand_font(self):
        """加载包内手写体作品牌字体；失败回退系统字体。

        需在一个 Tk 根窗口已存在的环境下调用（__init__ 已创建 root）。
        """
        try:
            name = get_default_local_font_name()
            f = load_local_tk_font(22, name=name, bold=True)
            if f is not None:
                return f
        except Exception:
            pass
        return ("Microsoft YaHei", 14, "bold")

    # ──────────────────────────────────────────────────
    #  菜单 / 控件
    # ──────────────────────────────────────────────────
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="新游戏…", command=self.new_game_dialog)
        game_menu.add_separator()
        game_menu.add_command(label="退出", command=self.root.destroy)
        menubar.add_cascade(label="游戏", menu=game_menu)
        self.root.config(menu=menubar)

    def _build_widgets(self) -> None:
        # 左侧：地图
        left = tk.Frame(self.root, bg=COL_BG)
        left.pack(side=tk.LEFT, padx=8, pady=8)

        t = self.game.floor["terrain"]
        cw, ch = t.width * CELL, t.height * CELL
        self.canvas = tk.Canvas(left, width=cw, height=ch,
                                bg=COL_BG, highlightthickness=0)
        self.canvas.pack()

        # 右侧：HUD + 背包
        right = tk.Frame(self.root, bg=COL_BG, width=260)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=8)

        # 品牌标题：使用包内手写体（补回的 50MB 字体 + utils.font 真正被使用）
        tk.Label(right, text="地牢冒险者", fg="#ffe14e", bg=COL_BG,
                 font=self.brand_font, anchor="w", justify="left"
                 ).pack(fill=tk.X, pady=(0, 2))

        self.title_var = tk.StringVar()
        tk.Label(right, textvariable=self.title_var, fg="#cfe3ff",
                 bg=COL_BG, font=("Microsoft YaHei", 12, "bold"),
                 anchor="w", justify="left").pack(fill=tk.X, pady=(0, 6))


        # HP 条
        tk.Label(right, text="生命", fg="#9aa", bg=COL_BG, anchor="w"
                 ).pack(fill=tk.X)
        self.hp_bar = ttk.Progressbar(right, maximum=100, length=240)
        self.hp_bar.pack(fill=tk.X)
        self.hp_var = tk.StringVar()
        tk.Label(right, textvariable=self.hp_var, fg="#ff8080", bg=COL_BG,
                 anchor="w").pack(fill=tk.X, pady=(0, 6))

        # 状态行
        self.stat_var = tk.StringVar()
        tk.Label(right, textvariable=self.stat_var, fg="#cfe3ff", bg=COL_BG,
                 font=("Microsoft YaHei", 9), anchor="w",
                 justify="left").pack(fill=tk.X, pady=(0, 6))

        # 背包列表
        tk.Label(right, text="背包", fg="#9aa", bg=COL_BG, anchor="w"
                 ).pack(fill=tk.X)
        self.inv_list = tk.Listbox(right, bg="#1d1d2c", fg="#dfe6f5",
                                    font=("Microsoft YaHei", 9), height=10,
                                    borderwidth=0, highlightthickness=0)
        self.inv_list.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # 战斗面板（始终保留，靠内部控件显隐切换）
        self.battle_frame = tk.Frame(right, bg=COL_BG)
        self.battle_frame.pack(fill=tk.X, pady=(0, 6))
        self.battle_var = tk.StringVar()
        self.battle_label = tk.Label(self.battle_frame, textvariable=self.battle_var,
                                     fg="#ffb3b3", bg=COL_BG,
                                     font=("Microsoft YaHei", 10),
                                     anchor="w", justify="left")
        bf = tk.Frame(self.battle_frame, bg=COL_BG)
        for txt, cmd in (("攻击 1", "1"), ("防御 2", "2"),
                         ("特技 4", "4"), ("喝药 U", "u"), ("逃跑 3", "3")):
            tk.Button(bf, text=txt, command=lambda c=cmd: self.do_battle(c),
                      bg="#3a2030", fg="#ffd2d2", width=7,
                      relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        self.battle_btns = bf

        # 小地图（已探索区域 2x2 降采样）
        tk.Label(right, text="小地图", fg="#9aa", bg=COL_BG, anchor="w"
                 ).pack(fill=tk.X)
        self.minimap_text = tk.Text(right, height=12, width=30, bg="#101019",
                                    fg="#8fa6c8", font=("Consolas", 8),
                                    borderwidth=0, highlightthickness=0,
                                    state=tk.DISABLED)
        self.minimap_text.pack(fill=tk.X, pady=(0, 6))

        # 动作按钮
        self._make_action_buttons(right)

        # 底部：日志
        bottom = tk.Frame(self.root, bg=COL_BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))
        self.log_text = tk.Text(bottom, height=6, bg="#101019", fg="#bcd1e8",
                                font=("Microsoft YaHei", 9), borderwidth=0,
                                highlightthickness=0, state=tk.DISABLED)
        self.log_text.pack(fill=tk.X)

    def _make_action_buttons(self, parent: tk.Widget) -> None:
        pad = {"bg": "#1f2a3a", "fg": "#cfe3ff",
               "relief": tk.FLAT, "width": 7}
        # 移动
        mv = tk.Frame(parent, bg=COL_BG)
        mv.pack(fill=tk.X, pady=(0, 6))
        tk.Button(mv, text="↑", command=lambda: self.do_move(0, -1), **pad
                  ).grid(row=0, column=1)
        tk.Button(mv, text="←", command=lambda: self.do_move(-1, 0), **pad
                  ).grid(row=1, column=0)
        tk.Button(mv, text="↓", command=lambda: self.do_move(0, 1), **pad
                  ).grid(row=1, column=1)
        tk.Button(mv, text="→", command=lambda: self.do_move(1, 0), **pad
                  ).grid(row=1, column=2)
        # 其它动作
        act = tk.Frame(parent, bg=COL_BG)
        act.pack(fill=tk.X)
        btns = [("拾取", lambda: self.do_simple("g")),
                ("背包", self.open_inventory),
                ("面板", self.open_character),
                ("装备", self.open_inventory),
                ("喝药", lambda: self.do_simple("u")),
                ("休息", lambda: self.do_simple("r")),
                ("商店", lambda: self.do_simple("b")),
                ("下层", lambda: self.do_simple(">")),
                ("帮助", lambda: self.do_simple("?")),
                ("退出", lambda: self.do_simple("q"))]
        for i, (txt, cmd) in enumerate(btns):
            tk.Button(act, text=txt, command=cmd, **pad
                      ).grid(row=i // 4, column=i % 4, padx=2, pady=2)

    # ──────────────────────────────────────────────────
    #  键盘绑定
    # ──────────────────────────────────────────────────
    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self.on_key)

    def on_key(self, event: tk.Event) -> None:
        if self.busy:
            return
        g = self.game
        if g.status not in ("playing", "battle"):
            return
        ks = event.keysym
        ch = event.char
        lower = (ch or "").lower()

        if g.status == "battle":
            if ch in ("1", "2", "3"):
                self.do_battle(ch)
            elif ch == "4":
                self.do_battle("4")
            elif lower == "u":
                self.do_battle("u")
            return

        # 地图模式
        if ks == "Up":
            self.do_move(0, -1)
        elif ks == "Down":
            self.do_move(0, 1)
        elif ks == "Left":
            self.do_move(-1, 0)
        elif ks == "Right":
            self.do_move(1, 0)
        elif lower == "w":
            self.do_move(0, -1)
        elif lower == "s":
            self.do_move(0, 1)
        elif lower == "a":
            self.do_move(-1, 0)
        elif lower == "d":
            self.do_move(1, 0)
        elif lower == "g":
            self.do_simple("g")
        elif lower == "e":
            self.open_inventory()
        elif lower == "i":
            self.open_inventory()
        elif lower == "c":
            self.open_character()
        elif lower == "u":
            self.do_simple("u")
        elif ch == ">":
            self.do_simple(">")
        elif lower == "?":
            self.do_simple("?")
        elif lower == "q":
            self.do_simple("q")

    # ──────────────────────────────────────────────────
    #  动作分发
    # ──────────────────────────────────────────────────
    def do_move(self, dx: int, dy: int) -> None:
        if self.game.status != "playing":
            return
        self.game.move(dx, dy)
        self.after_action()

    def do_simple(self, cmd: str) -> None:
        g = self.game
        # 保险闸：有待处理升级时先弹三选一，绝不让 handle 走到 input() 阻塞
        if g.pending_levels:
            self.open_level_up()
            return
        if cmd == "q":
            g.handle("q")
        else:
            g.handle(cmd)
        self.after_action()

    def do_battle(self, cmd: str) -> None:
        if self.game.status != "battle":
            return
        self.game.battle_command(cmd)
        self.after_action()

    def after_action(self) -> None:
        self.refresh_all()
        g = self.game
        # BOSS 立绘：进入 Boss 战时弹一次
        if g.status == "battle" and g.battle_mob is not None \
                and g.battle_mob.get(MobBrain).template.mob_type == "boss" \
                and not self._boss_art_shown:
            self.show_boss_art(g.battle_mob.get(MobBrain))
        # 升级三选一：有待处理升级时弹窗（模态，关闭即结算完）
        if g.pending_levels:
            self.open_level_up()
            self.refresh_all()
        st = g.status
        if st == "won":
            messagebox.showinfo("通关", "🏆 通关！你成为了地牢的传奇冒险者。")
        elif st == "lost":
            messagebox.showinfo("失败", "💀 你死在了地牢深处。冒险者，下次好运。")
        elif st == "quit":
            messagebox.showinfo("退出", "已退出游戏。")

    # ──────────────────────────────────────────────────
    #  渲染
    # ──────────────────────────────────────────────────
    def refresh_all(self) -> None:
        self.draw_map()
        self.update_hud()
        self.update_log()

    def draw_map(self) -> None:
        g = self.game
        t = g.floor["terrain"]
        cv = self.canvas
        cv.delete("all")

        monsters = {(m.get(Position).x, m.get(Position).y): m
                    for m in g.monsters
                    if m.get(MobBrain).alive}
        items = {it["pos"]: it for it in g.floor["items"]}
        trap_types = g.floor.get("trap_types", {})
        structs = g.floor.get("structures", {})
        struct_pos = {pos: ("H" if k == "inn" else "¥")
                      for k, pos in structs.items()}

        for r in range(t.height):
            for c in range(t.width):
                x0, y0 = c * CELL, r * CELL
                x1, y1 = x0 + CELL, y0 + CELL
                if (c, r) == (g.px, g.py):
                    fill, glyph, fg = COL_PLAYER, "@", COL_PLAYER_FG
                elif (c, r) in monsters:
                    mb = monsters[(c, r)].get(MobBrain)
                    fill, glyph, fg = COL_MON, mb.template.icon, COL_MON_FG
                    if getattr(mb, "attack_range", 1) > 1:
                        fg = COL_RANGED   # 远程怪高亮，提示「会被放风筝」
                elif (c, r) in items:
                    it = items[(c, r)]
                    fill, glyph, fg = COL_ITEM, "$", \
                        RARITY_HEX.get(it.get("rarity", "common"), COL_ITEM_FG)
                elif (c, r) in trap_types:
                    if trap_types[(c, r)] == "lava":
                        fill, glyph, fg = "#2a1408", "~", COL_TRAP_LAVA
                    else:
                        fill, glyph, fg = "#1a1a24", "^", COL_TRAP_SPIKE
                elif (c, r) in struct_pos:
                    fill, glyph, fg = COL_ITEM, struct_pos[(c, r)], COL_ITEM_FG
                else:
                    ch = t.get(c, r)
                    if ch == "#":
                        fill, glyph, fg = COL_WALL, "", COL_WALL_FG
                    elif ch == ">":
                        fill, glyph, fg = COL_STAIRS, ">", COL_STAIRS_FG
                    else:
                        fill, glyph, fg = COL_FLOOR, "·", COL_FLOOR_FG
                cv.create_rectangle(x0, y0, x1, y1, fill=fill, outline="")
                if glyph:
                    cv.create_text(x0 + CELL / 2, y0 + CELL / 2, text=glyph,
                                   fill=fg, font=FONT)

    def update_hud(self) -> None:
        g = self.game
        f = g.floor
        self.title_var.set(
            f"第 {g.floor_index}/{g.total_floors} 层 · Lv{g.progression.level}"
            f" · {f['region']}地牢"
            + ("（BOSS 层！）" if f["is_boss"] else "")
        )
        self.hp_bar["maximum"] = g.ps.max_hp
        self.hp_bar["value"] = max(0, g.ps.hp)
        self.hp_var.set(f"HP {max(0, g.ps.hp)} / {g.ps.max_hp}")

        stat = (f"金币 {g.gold}    背包 {len(g.inv.list_all())}\n"
                f"武器 {g._eq_name('weapon')}    护甲 {g._eq_name('armor')}")
        if g.status_effects:
            effs = " ".join(
                f"{'中毒' if e['kind'] == 'poison' else '灼烧'}{e['turns']}"
                for e in g.status_effects)
            stat += f"\n异常: {effs}"
        self.stat_var.set(stat)

        # 背包列表（按稀有度着色）
        self.inv_list.delete(0, tk.END)
        for it in g.inv.list_all():
            tag = "◆" if it.item_id in (g.equipped_weapon, g.equipped_armor) \
                else " "
            self.inv_list.insert(tk.END,
                                 f"[{tag}] {it.name} x{it.quantity}")
            self.inv_list.itemconfig(
                tk.END,
                foreground=RARITY_HEX.get(
                    it.metadata.get("rarity", "common"), COL_ITEM_FG))

        # 小地图
        self.minimap_text.configure(state=tk.NORMAL)
        self.minimap_text.delete(1.0, tk.END)
        self.minimap_text.insert(tk.END, g._render_minimap())
        self.minimap_text.configure(state=tk.DISABLED)

        # 战斗面板
        if g.status == "battle" and g.battle_mob is not None:
            mb = g.battle_mob.get(MobBrain)
            bs = g.battle_state
            self.battle_var.set(
                f"⚔ 对战 {mb.name}\n"
                f"  {mb.name} {bs.mob_hp}/{bs.mob_max_hp}\n"
                f"  你   {bs.player_hp}/{g.ps.max_hp}"
            )
            self.battle_label.pack(fill=tk.X, pady=(0, 4))
            self.battle_btns.pack(fill=tk.X)
        else:
            self.battle_label.pack_forget()
            self.battle_btns.pack_forget()

    def update_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        for m in self.game.logs[-6:]:
            self.log_text.insert(tk.END, "» " + m + "\n")
        self.log_text.configure(state=tk.DISABLED)

    # ──────────────────────────────────────────────────
    #  升级三选一 / 角色面板 / Boss 立绘
    # ──────────────────────────────────────────────────
    def open_level_up(self) -> None:
        """升级弹窗：从 3 个随机 perk 中选 1（zooz 半随机层设计）。"""
        g = self.game
        if not g.pending_levels:
            return
        self.busy = True
        level = g.pending_levels[0]   # 先处理最旧的待升级
        choices = roll_perk_choices(g.rng, 3)
        win = tk.Toplevel(self.root)
        win.title(f"升级！第 {level} 级")
        win.configure(bg=COL_BG)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=f"🎉 你达到 {level} 级！选择一项强化：",
                 fg="#ffe14e", bg=COL_BG,
                 font=("Microsoft YaHei", 12, "bold")
                 ).pack(padx=14, pady=(10, 6))

        def pick(perk: dict) -> None:
            apply_perk(g, perk["id"])
            g.pending_levels.pop(0)
            win.destroy()
            self.busy = False
            self.refresh_all()
            if g.pending_levels:        # 一次升多级时继续弹
                self.open_level_up()

        for p in choices:
            row = tk.Frame(win, bg=COL_BG)
            row.pack(fill=tk.X, padx=12, pady=3)
            tk.Label(row, text=p["name"], fg="#cfe3ff", bg=COL_BG,
                     font=("Microsoft YaHei", 11, "bold"), width=10,
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=p.get("desc", ""), fg="#9aa", bg=COL_BG,
                     anchor="w", width=42).pack(side=tk.LEFT)
            tk.Button(row, text="选择", width=8, relief=tk.FLAT,
                      bg="#1f3a2a", fg="#bff0c8",
                      command=lambda pk=p: pick(pk)
                      ).pack(side=tk.LEFT, padx=6)
        win.wait_window(win)
        self.busy = False

    def open_character(self) -> None:
        """角色面板（C）：等级 / 属性 / 已选 perk / AI Director 状态。"""
        if self.game.status not in ("playing", "battle"):
            return
        g = self.game
        p = g.progression
        d = g.director
        lines = [
            f"等级 {p.level}  (经验 {p.xp}/{p.xp_next})",
            f"生命 {g.ps.hp}/{g.ps.max_hp}   攻击 {g.weapon_damage()}"
            f"   防御 {g.armor_val()}   暴击 {int(g.crit_chance() * 100)}%",
        ]
        if g.mods.get("lifesteal") or g.mods.get("special") \
                or g.damage_reduction() or g.regen_per_turn():
            lines.append(
                f"吸血 {int(g.lifesteal() * 100)}%   特技x{g.special_mult():.2f}"
                f"   减伤 {g.damage_reduction()}   再生 {g.regen_per_turn()}/回合")
        perks = [PERK_MAP[i]["name"] for i in p.perks]
        lines.append("已选强化：" + ("、".join(perks) if perks else "无"))
        lines.append(
            f"AI Director：击杀 {d.kills}  死亡 {d.deaths}"
            f"  挣扎 {d.struggle:.1f}  压制 {d.challenge:.1f}")
        self.busy = True
        win = tk.Toplevel(self.root)
        win.title("角色面板")
        win.configure(bg=COL_BG)
        win.transient(self.root)

        def close() -> None:
            win.destroy()
            self.busy = False

        win.protocol("WM_DELETE_WINDOW", close)
        tk.Label(win, text="—— 角色面板 ——", fg="#ffe14e", bg=COL_BG,
                 font=("Microsoft YaHei", 12, "bold")
                 ).pack(padx=14, pady=(10, 4))
        txt = tk.Text(win, bg="#101019", fg="#bcd1e8",
                      font=("Microsoft YaHei", 10), borderwidth=0,
                      highlightthickness=0, width=48, height=8)
        txt.insert(tk.END, "\n".join(lines))
        txt.configure(state=tk.DISABLED)
        txt.pack(padx=14, pady=(0, 10))
        tk.Button(win, text="关闭", width=10, relief=tk.FLAT, bg="#2a2a3a",
                  fg="#cfe3ff", command=close).pack(pady=(0, 10))

    def show_boss_art(self, mb: MobBrain) -> None:
        """Boss 遭遇立绘（一次）：在弹窗里展示 ASCII 立绘与名字。"""
        self._boss_art_shown = True
        art = BOSS_ART.get(mb.template.mob_id, [])
        win = tk.Toplevel(self.root)
        win.title(f"BOSS · {mb.name}")
        win.configure(bg=COL_BG)
        win.transient(self.root)
        tk.Label(win, text=f"⚠ 遭遇 BOSS：{mb.name} ⚠", fg="#ff7a3c",
                 bg=COL_BG, font=("Microsoft YaHei", 13, "bold")
                 ).pack(padx=14, pady=(10, 4))
        txt = tk.Text(win, bg="#101019", fg="#ffb38a", font=("Consolas", 12),
                      borderwidth=0, highlightthickness=0, width=46, height=12)
        txt.insert(tk.END, "\n".join(art))
        txt.configure(state=tk.DISABLED)
        txt.pack(padx=14, pady=(0, 8))
        tk.Button(win, text="迎战", width=12, relief=tk.FLAT, bg="#3a1f1f",
                  fg="#ffd2d2", command=win.destroy).pack(pady=(0, 10))

    # ──────────────────────────────────────────────────
    #  背包 / 装备 / 喝药 弹窗
    # ──────────────────────────────────────────────────
    def open_inventory(self) -> None:
        if self.game.status != "playing":
            return
        self.busy = True
        win = tk.Toplevel(self.root)
        win.title("背包 / 装备 / 喝药")
        win.configure(bg=COL_BG)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_busy(win))

        tk.Label(win, text="点击对应按钮进行装备或使用",
                 fg="#9aa", bg=COL_BG).pack(padx=10, pady=(8, 4))

        items = self.game.inv.list_all()
        if not items:
            tk.Label(win, text="（背包为空）", fg="#cfe3ff",
                     bg=COL_BG).pack(padx=10, pady=10)
        for it in items:
            row = tk.Frame(win, bg=COL_BG)
            row.pack(fill=tk.X, padx=10, pady=2)
            eq = it.item_id in (self.game.equipped_weapon,
                                self.game.equipped_armor)
            tag = " [已装备]" if eq else ""
            tk.Label(row, text=f"{it.name} x{it.quantity} ({it.item_type}){tag}",
                     fg="#dfe6f5", bg=COL_BG, anchor="w",
                     width=34).pack(side=tk.LEFT)
            if it.item_type in ("weapon", "armor"):
                tk.Button(row, text="装备", width=6, relief=tk.FLAT,
                          bg="#1f3a2a", fg="#bff0c8",
                          command=lambda iid=it.item_id: self._equip(iid, win)
                          ).pack(side=tk.LEFT, padx=4)
            elif it.item_type == "consumable":
                tk.Button(row, text="使用", width=6, relief=tk.FLAT,
                          bg="#3a2a1f", fg="#ffd9b3",
                          command=lambda iid=it.item_id: self._use(iid, win)
                          ).pack(side=tk.LEFT, padx=4)

        tk.Button(win, text="关闭", width=10, relief=tk.FLAT,
                  bg="#2a2a3a", fg="#cfe3ff",
                  command=lambda: self._close_busy(win)).pack(pady=8)

    def _equip(self, iid: str, win: tk.Toplevel) -> None:
        self.game._equip(iid)
        self.refresh_all()
        self._rebuild_inventory(win)

    def _use(self, iid: str, win: tk.Toplevel) -> None:
        g = self.game
        item = g.catalog[iid]
        hp = item.get_effect("hp")
        g.ps.adjust_hp(hp)
        g.inv.remove(iid, quantity=1)
        g.log(f"使用 {item.name}，恢复 {hp} 点生命")
        self.refresh_all()
        self._rebuild_inventory(win)

    def _rebuild_inventory(self, win: tk.Toplevel) -> None:
        # 简单重建：关掉再开，保证状态最新
        self._close_busy(win)
        self.open_inventory()

    def _close_busy(self, win: tk.Toplevel) -> None:
        win.destroy()
        self.busy = False

    # ──────────────────────────────────────────────────
    #  新游戏
    # ──────────────────────────────────────────────────
    def new_game_dialog(self) -> None:
        self.busy = True
        seed = simpledialog.askinteger("新游戏", "随机种子：",
                                       initialvalue=self.game.seed, parent=self.root)
        if seed is None:
            self.busy = False
            return
        floors = simpledialog.askinteger("新游戏", "地牢层数：",
                                         initialvalue=self.game.total_floors,
                                         minvalue=1, maxvalue=50, parent=self.root)
        self.busy = False
        if floors is None:
            return
        self.game = Game(seed=seed, floors=floors)
        self._boss_art_shown = False
        self.refresh_all()
        messagebox.showinfo("新游戏", f"已开始新游戏：种子 {seed}，{floors} 层。")


def main() -> None:
    ap = argparse.ArgumentParser(description="地牢冒险者 — 图形界面版")
    ap.add_argument("--seed", type=int, default=20260717, help="随机种子")
    ap.add_argument("--floors", type=int, default=5, help="地牢总层数")
    args = ap.parse_args()

    root = tk.Tk()
    try:
        DungeonGUI(root, seed=args.seed, floors=args.floors)
    except Exception as exc:  # 启动失败时给出可读提示（控制台 GBK 环境）
        messagebox.showerror("启动失败", str(exc))
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
