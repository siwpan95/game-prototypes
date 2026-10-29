"""gui/app.py — LordOfMysteriesGUI 主类。

职责：窗口骨架构建(__init__/_build_*/switch_view/refresh_all/set_character)
      与控制器组合；渲染逻辑已全部拆分为 gui/panels 下的自由函数
      draw_*(canvas, state, callbacks)，由本类在编排时传入 canvas / state / callbacks。

设计要点：
  - 渲染面板是无 self 的自由函数，可被完全独立的单元测试覆盖；
  - callbacks 字典把「用户点击」映射到 ControllersMixin 的各 _do_* 处理器；
  - GUIState 持有运行时状态（character/old_one_info/event_log/view_mode/fonts/
    pathway_items），对外的 gui.character / gui.old_one_info 等访问经属性代理不变。
"""
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import math
import os
import sys
from typing import Optional
from gui.theme import CLR, TAROT_ICONS, FONT_REGULAR, FONT_BOLD, register_fonts
from gui.drawing import (draw_rounded_rect, draw_gauge, pathway_sort_key,
                         group_key_of, _wrap_text)
from pathways_data import (PATHWAYS, PATHWAY_GROUPS, get_pathway, get_sequence_data,
                           get_compatible_pathways, needs_ritual, will_gender_change,
                           get_gender_change_message)
from sequences import Sequence, make_sequence
from anchor import Anchor
from pollution import PollutionLevel, PollutionSource, PollutionManager, InsanityError
from ascension import (ascend, switch_pathway, Potion, AscensionManager,
                       SequenceError, AnchorBreakError)
from uniqueness import Uniqueness, SequenceOneCharacteristic
from pathway_groups import OldOnePath, FOUR_PILLARS, promote_to_old_one, OldOneTier
from gui.state import GUIState
from gui.panels.character_view import draw_character_card, draw_gauges
from gui.panels.pathways_view import draw_pathway_list, draw_pathways_view
from gui.panels.groups_view import draw_groups_view
from gui.panels.action_panel import draw_action_panel
from gui.panels.log_panel import add_log as log_add_log, draw_log
from gui.panels.factions_view import draw_factions_view
from gui.panels.rivals_view import draw_rivals_view
from gui.panels.codex_view import draw_codex_view
from gui.panels.event_panel import draw_event_overlay
from gui.controllers import ControllersMixin


class LordOfMysteriesGUI(ControllersMixin):

    # ─── GUIState 中介属性（外部访问 self.character 等写法保持不变）───
    @property
    def character(self):
        return self.state.character

    @character.setter
    def character(self, value):
        self.state.character = value

    @property
    def old_one_info(self):
        return self.state.old_one_info

    @old_one_info.setter
    def old_one_info(self, value):
        self.state.old_one_info = value

    @property
    def event_log(self):
        return self.state.event_log

    @event_log.setter
    def event_log(self, value):
        self.state.event_log = value

    @property
    def view_mode(self):
        return self.state.view_mode

    @view_mode.setter
    def view_mode(self, value):
        self.state.view_mode = value

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("诡秘之主 — 序列途径模拟系统")
        self.root.geometry("1480x880+100+50")
        self.root.configure(bg=CLR["bg"])
        self.root.minsize(1200, 700)

        # 注册字体
        self.FONT = register_fonts(self.root)
        self.state = GUIState()
        self.state.fonts = self.FONT

        # 构建 UI
        self._build_ui()

        # 初始状态：创建一个默认角色
        self._create_default_character()

        # 窗口大小变化时刷新
        self.root.bind("<Configure>", self._on_resize)
        self._resize_after_id = None

    # ─── 字体 ───

    def _on_resize(self, event):
        """窗口大小变化时防抖刷新"""
        if event.widget != self.root:
            return
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(200, self.refresh_all)

    # ─── 构建 UI ───

    def _build_ui(self):
        """构建主界面布局"""
        # 顶部工具栏
        self._build_toolbar()

        # 主容器：横向三栏
        self.main_container = tk.Frame(self.root, bg=CLR["bg"])
        self.main_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # 左栏：途径列表 (260px)
        self._build_left_panel(self.main_container)
        # 中栏：角色状态 (580px)
        self._build_center_panel(self.main_container)
        # 右栏：操作 + 日志 (剩余)
        self._build_right_panel(self.main_container)

    # ─── 工具栏 ───

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=CLR["panel"], height=48)
        bar.pack(fill="x", padx=8, pady=(8, 0))
        bar.pack_propagate(False)

        # 标题
        lbl = tk.Label(bar, text="🜃 诡秘之主  序列途径模拟系统",
                       font=self.FONT["h2"], fg=CLR["gold"], bg=CLR["panel"])
        lbl.pack(side="left", padx=16, pady=8)

        # 视图切换按钮
        btn_style = {"font": self.FONT["small"], "bd": 0, "cursor": "hand2",
                      "padx": 14, "pady": 6}

        self.btn_char = tk.Button(bar, text="角色视图", command=lambda: self.switch_view("character"), **btn_style)
        self.btn_char.configure(bg=CLR["gold_dim"], fg=CLR["text_bright"])
        self.btn_char.pack(side="left", padx=4, pady=8)

        self.btn_path = tk.Button(bar, text="途径全景", command=lambda: self.switch_view("pathways"), **btn_style)
        self.btn_path.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_path.pack(side="left", padx=4, pady=8)

        self.btn_group = tk.Button(bar, text="权柄体系", command=lambda: self.switch_view("groups"), **btn_style)
        self.btn_group.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_group.pack(side="left", padx=4, pady=8)

        self.btn_faction = tk.Button(bar, text="阵营社交", command=lambda: self.switch_view("factions"), **btn_style)
        self.btn_faction.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_faction.pack(side="left", padx=4, pady=8)

        self.btn_rival = tk.Button(bar, text="对手", command=lambda: self.switch_view("rivals"), **btn_style)
        self.btn_rival.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_rival.pack(side="left", padx=4, pady=8)

        self.btn_codex = tk.Button(bar, text="成就图鉴", command=lambda: self.switch_view("codex"), **btn_style)
        self.btn_codex.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_codex.pack(side="left", padx=4, pady=8)

        self.btn_ambient = tk.Button(bar, text="🌫 灰雾", command=lambda: self._do_toggle_ambient(), **btn_style)
        self.btn_ambient.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_ambient.pack(side="left", padx=4, pady=8)

        # 存档 / 读档（E4）
        self.btn_save = tk.Button(bar, text="💾 存档", command=lambda: self._do_save("quicksave"), **btn_style)
        self.btn_save.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_save.pack(side="left", padx=4, pady=8)
        self.btn_load = tk.Button(bar, text="📂 读档", command=lambda: self._do_load("quicksave"), **btn_style)
        self.btn_load.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])
        self.btn_load.pack(side="left", padx=4, pady=8)

        # 版本
        ver = tk.Label(bar, text="v2.1 · Canvas Edition", font=self.FONT["tiny"],
                       fg=CLR["text_dim"], bg=CLR["panel"])
        ver.pack(side="right", padx=16)

    # ─── 左栏：途径列表 ───

    def _build_left_panel(self, parent):
        self.left_frame = tk.Frame(parent, width=260, bg=CLR["panel"])
        self.left_frame.pack(side="left", fill="y", padx=(0, 4))
        self.left_frame.pack_propagate(False)

        # 标题
        hdr = tk.Frame(self.left_frame, bg=CLR["panel"], height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="▎22 条神之途径", font=self.FONT["title"],
                 fg=CLR["gold"], bg=CLR["panel"]).pack(side="left", padx=12, pady=4)

        # Canvas 列表
        self.pathway_canvas = tk.Canvas(self.left_frame, bg=CLR["panel"],
                                         highlightthickness=0, width=260)
        self.pathway_canvas.pack(fill="both", expand=True)

        # 滚动条
        sb = tk.Scrollbar(self.left_frame, orient="vertical",
                          command=self.pathway_canvas.yview)
        sb.pack(side="right", fill="y")
        self.pathway_canvas.configure(yscrollcommand=sb.set)

        # 鼠标滚轮滚动
        self.pathway_canvas.bind("<MouseWheel>",
            lambda e: self.pathway_canvas.yview_scroll(-e.delta//120, "units"))

        self._draw_pathway_list()

    def _build_center_panel(self, parent):
        self.center_frame = tk.Frame(parent, bg=CLR["bg"])
        self.center_frame.pack(side="left", fill="both", expand=True, padx=4)

        # 上方：角色卡片 Canvas
        self.char_canvas = tk.Canvas(self.center_frame, bg=CLR["panel"],
                                      highlightthickness=0)
        self.char_canvas.pack(fill="both", expand=True)
        self.char_canvas.bind("<MouseWheel>", lambda e: None)  # 角色卡片不需滚动

        # 下方：仪表盘 Canvas (固定高度 180)
        self.gauge_canvas = tk.Canvas(self.center_frame, bg=CLR["panel"],
                                       highlightthickness=0, height=180)
        self.gauge_canvas.pack(fill="x", pady=(4, 0))

    # ─── 右栏：操作 + 日志 ───

    def _build_right_panel(self, parent):
        self.right_frame = tk.Frame(parent, width=340, bg=CLR["panel"])
        self.right_frame.pack(side="right", fill="y", padx=(4, 0))
        self.right_frame.pack_propagate(False)

        # 操作区
        act_hdr = tk.Frame(self.right_frame, bg=CLR["panel"], height=32)
        act_hdr.pack(fill="x")
        act_hdr.pack_propagate(False)
        tk.Label(act_hdr, text="▎操作", font=self.FONT["title"],
                 fg=CLR["gold"], bg=CLR["panel"]).pack(side="left", padx=12, pady=4)

        # 操作 Canvas（可滚动，适配权柄收集/旧日晋升新增面板）
        self.action_canvas = tk.Canvas(self.right_frame, bg=CLR["panel"],
                                        highlightthickness=0)
        self.action_canvas.pack(side="left", fill="both", expand=True)
        self.action_sb = tk.Scrollbar(self.right_frame, orient="vertical",
                                      command=self.action_canvas.yview)
        self.action_sb.pack(side="right", fill="y")
        self.action_canvas.configure(yscrollcommand=self.action_sb.set)
        self.action_canvas.bind("<MouseWheel>",
            lambda e: self.action_canvas.yview_scroll(-e.delta//120, "units"))

        # 分割线
        sep = tk.Frame(self.right_frame, bg=CLR["border"], height=1)
        sep.pack(fill="x", padx=8)

        # 日志区
        log_hdr = tk.Frame(self.right_frame, bg=CLR["panel"], height=32)
        log_hdr.pack(fill="x")
        log_hdr.pack_propagate(False)
        tk.Label(log_hdr, text="▎事件日志", font=self.FONT["title"],
                 fg=CLR["gold"], bg=CLR["panel"]).pack(side="left", padx=12, pady=4)

        # 日志 Canvas
        self.log_canvas = tk.Canvas(self.right_frame, bg=CLR["panel_light"],
                                     highlightthickness=0)
        self.log_canvas.pack(fill="both", expand=True)

        # 日志滚动条
        self.log_sb = tk.Scrollbar(self.right_frame, orient="vertical",
                                    command=self.log_canvas.yview)
        self.log_sb.pack(side="right", fill="y")
        self.log_canvas.configure(yscrollcommand=self.log_sb.set)
        self.log_canvas.bind("<MouseWheel>",
            lambda e: self.log_canvas.yview_scroll(-e.delta//120, "units"))

    # ═══════════════════════════════════════════════════════
    # 绘制核心方法（薄包装：把 canvas/state/callbacks 交给自由函数）
    # ═══════════════════════════════════════════════════════

    def _callbacks(self) -> dict:
        """把用户交互映射到底层控制器方法。"""
        return {
            "do_action":              self._do_action,
            "do_ascend":              self._do_ascend,
            "do_switch":              self._do_switch,
            "do_random_event":        self._do_random_event,
            "do_collect_seq1":        self._do_collect_seq1,
            "do_collect_uniqueness":  self._do_collect_uniqueness,
            "do_promote_old_one":     self._do_promote_old_one,
            "do_gather":              self._do_gather_materials,
            "do_event_choice":        self._do_event_choice,
            "do_save":                self._do_save,
            "do_load":                self._do_load,
            "do_faction_action":      self._do_faction_action,
            "do_rival_tick":          self._do_rival_tick,
            "do_add_rival":           self._do_add_rival,
            "do_toggle_ambient":      self._do_toggle_ambient,
            "select_pathway":         self._select_pathway,
            "select_pathway_from_view": self.select_pathway,
            "on_group_click":         self._on_group_click,
        }

    def set_character(self, char: Sequence):
        """设置当前角色并刷新所有面板"""
        self.character = char
        self.old_one_info = None  # 切换角色后清空旧日位阶缓存
        self.refresh_all()

    def refresh_all(self):
        """刷新所有面板"""
        # E9：在每次重绘时刷新图鉴并记录新解锁的成就（纯逻辑，失败不影响渲染）
        try:
            from achievements import record_codex, evaluate_achievements
            record_codex(self.state)
            for name in evaluate_achievements(self.state):
                self.add_log(f"🏆 解锁成就：{name}")
        except Exception:
            pass
        if self.view_mode == "character":
            if self.state.pending_event:
                self._draw_event_overlay()
            else:
                self._draw_character_card()
                self._draw_gauges()
                self._draw_action_panel()
            self._draw_log()
        elif self.view_mode == "pathways":
            self._draw_pathways_view()
        elif self.view_mode == "groups":
            self._draw_groups_view()
        elif self.view_mode == "factions":
            self._draw_factions_view()
        elif self.view_mode == "rivals":
            self._draw_rivals_view()
        elif self.view_mode == "codex":
            self._draw_codex_view()

    def switch_view(self, mode: str):
        """切换视图"""
        self.view_mode = mode
        # 更新按钮样式
        for btn, m in [(self.btn_char, "character"), (self.btn_path, "pathways"),
                       (self.btn_group, "groups"), (self.btn_faction, "factions"),
                       (self.btn_rival, "rivals"), (self.btn_codex, "codex")]:
            if m == mode:
                btn.configure(bg=CLR["gold_dim"], fg=CLR["text_bright"])
            else:
                btn.configure(bg=CLR["panel_light"], fg=CLR["text_dim"])

        # 隐藏/显示面板
        if mode == "character":
            self.char_canvas.pack(fill="both", expand=True)
            self.gauge_canvas.pack(fill="x", pady=(4, 0))
            self.right_frame.pack(side="right", fill="y", padx=(4, 0))
            self._draw_character_card()
            self._draw_gauges()
            self._draw_action_panel()
        elif mode == "pathways":
            self.char_canvas.pack_forget()
            self.gauge_canvas.pack_forget()
            self.right_frame.pack_forget()
            self._draw_pathways_view()
        elif mode == "groups":
            self.char_canvas.pack_forget()
            self.gauge_canvas.pack_forget()
            self.right_frame.pack_forget()
            self._draw_groups_view()
        elif mode == "factions":
            self.char_canvas.pack(fill="both", expand=True)
            self.gauge_canvas.pack_forget()
            self.right_frame.pack_forget()
            self._draw_factions_view()
        elif mode == "rivals":
            self.char_canvas.pack(fill="both", expand=True)
            self.gauge_canvas.pack_forget()
            self.right_frame.pack_forget()
            self._draw_rivals_view()
        elif mode == "codex":
            self.char_canvas.pack(fill="both", expand=True)
            self.gauge_canvas.pack_forget()
            self.right_frame.pack_forget()
            self._draw_codex_view()

    # ─── 绘制包装（供 refresh_all / switch_view / 控制器调用）───

    def _draw_character_card(self):
        draw_character_card(self.char_canvas, self.state)

    def _draw_gauges(self):
        draw_gauges(self.gauge_canvas, self.state)

    def _draw_action_panel(self):
        draw_action_panel(self.action_canvas, self.state, self._callbacks())

    def _draw_pathway_list(self):
        draw_pathway_list(self.pathway_canvas, self.state, self._callbacks())

    def _draw_pathways_view(self):
        draw_pathways_view(self.char_canvas, self.state, self._callbacks())

    def _draw_groups_view(self):
        draw_groups_view(self.char_canvas, self.state, self._callbacks())

    def _draw_factions_view(self):
        draw_factions_view(self.char_canvas, self.state, self._callbacks())

    def _draw_rivals_view(self):
        draw_rivals_view(self.char_canvas, self.state, self._callbacks())

    def _draw_codex_view(self):
        draw_codex_view(self.char_canvas, self.state, self._callbacks())

    def _draw_event_overlay(self):
        draw_event_overlay(self.char_canvas, self.state, self._callbacks())

    def _draw_log(self):
        draw_log(self.log_canvas, self.state)

    def add_log(self, msg: str):
        """追加日志并重绘日志面板"""
        log_add_log(self.state, msg)
        self._draw_log()

    # ═══════════════════════════════════════════════════════
    # 途径选择 / 视图联动（编排层，原属 panels mixin）
    # ═══════════════════════════════════════════════════════

    def _select_pathway(self, pk: str):
        """选择一条途径创建/切换角色"""
        p = get_pathway(pk)
        self.add_log(f"选择途径：{p['name']}")
        try:
            char = make_sequence(pk, 9)
            char.anchor = Anchor(humanity=80, connections=5, name=f"{p['name']}之锚")
            char.PATHWAY_KEY = pk  # 确保正确
            self.set_character(char)
            self._draw_pathway_list()  # 刷新指示点
        except Exception as e:
            self.add_log(f"❌ 创建角色失败：{e}")

    def select_pathway(self, pk: str):
        """从全景/权柄体系视图选择途径：创建角色并切回角色视图"""
        self._select_pathway(pk)
        self.switch_view("character")

    def _on_group_click(self, gk: str):
        """点击权柄体系——选择第一个途径"""
        pathways = PATHWAY_GROUPS[gk]["pathways"]
        if pathways:
            self.select_pathway(pathways[0])

    # ─── 初始默认角色 ───

    def _create_default_character(self):
        """创建默认角色：错误途径·偷盗者"""
        char = make_sequence("error", 9)
        char.anchor = Anchor(humanity=85, connections=5, name="克喵之锚")
        self.set_character(char)
        self.add_log("系统启动：诡秘之主序列途径模拟 v2.1 · Canvas Edition")
        self.add_log(f"初始角色：{char.summary}（可用操作执行）")
        self.add_log("提示：执行所有扮演行为以消化魔药 → 晋升下一序列")

    # ─── 主循环 ───

    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════
