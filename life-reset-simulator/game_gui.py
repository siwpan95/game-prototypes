#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人生重开模拟器 - Tkinter图形界面版
基于命令行版完整移植，包含SBTI出身选择+王权决策树+传统冒险+修行模式
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import random
import json
import os
from typing import Dict, List, Tuple, Any, Optional

from core import constants
from core.content_loader import ContentLoader

# ── 获取脚本所在目录 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════
#  配色方案
# ══════════════════════════════════════════════
COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_mid": "#16213e",
    "bg_light": "#0f3460",
    "accent": "#e94560",
    "accent2": "#533483",
    "gold": "#f5c518",
    "text": "#eaeaea",
    "text_dim": "#8a8a9a",
    "green": "#4ecca3",
    "red": "#e94560",
    "blue": "#3282b8",
    "orange": "#f08a5d",
    "purple": "#6c5ce7",
    "cyan": "#00cec9",
    "bar_bg": "#2d2d44",
    "card_bg": "#1e2746",
    "btn_left": "#e94560",
    "btn_right": "#4ecca3",
    "highlight": "#ffeaa7",
}

# ── 稀有度 / 分类 / 难度 展示映射（结局库 + 传家宝 + 挑战共用）──
RARITY_LABEL = {
    "common": "普通", "uncommon": "少见", "rare": "稀有",
    "epic": "史诗", "legendary": "传说", "mythic": "神话",
}
RARITY_COLORS = {
    "common": "#8a8a9a", "uncommon": "#4ecca3", "rare": "#3282b8",
    "epic": "#6c5ce7", "legendary": "#f5c518", "mythic": "#e94560",
}
CATEGORY_LABEL = {
    "normal": "普通结局", "career": "事业结局", "emotion": "情感结局",
    "hidden": "隐藏结局", "death": "死亡结局", "legendary": "传说结局",
}
DIFFICULTY_LABEL = {
    "easy": "简单", "normal": "普通", "hard": "困难",
    "very_hard": "地狱", "extreme": "噩梦",
}
DIFFICULTY_COLORS = {
    "easy": "#4ecca3", "normal": "#3282b8", "hard": "#f08a5d",
    "very_hard": "#e94560", "extreme": "#6c5ce7",
}


# ══════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════
def fmt_conditions(conds: Dict) -> str:
    """把挑战 win_conditions 翻成人话。"""
    name_map = {
        "wealth_gte": "财富≥", "wealth_lte": "财富≤",
        "age_gte": "年龄≥", "age_lte": "年龄≤",
        "happiness_gte": "幸福≥", "intelligence_gte": "智力≥",
        "career_tier_gte": "职业阶梯≥", "health_gte": "健康≥",
        "education_max": "学历不超过", "mode": "模式为",
    }
    parts = []
    for k, v in (conds or {}).items():
        label = name_map.get(k, k)
        if isinstance(v, bool):
            parts.append(label if v else f"非{label}")
        else:
            parts.append(f"{label}{v}")
    return "，".join(parts)


def fmt_override(ov: Dict) -> str:
    """把挑战 start_override 翻成人话。"""
    parts = []
    for k, v in (ov or {}).items():
        if k.endswith("_blacklist"):
            parts.append(f"禁用 {len(v) if isinstance(v, list) else 0} 项")
        elif isinstance(v, (int, float, str)):
            parts.append(f"{k}={v}")
    return "，".join(parts) or "无"


def load_json(filename: str) -> Dict:
    filepath = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_json(filepath: str, data: Dict):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_age_group(age: int) -> str:
    if age < 30:
        return "20s"
    elif age < 40:
        return "30s"
    elif age < 50:
        return "40s"
    elif age < 60:
        return "50s"
    else:
        return "60+"


# ══════════════════════════════════════════════
#  Player 数据类（复用命令行版逻辑）
# ══════════════════════════════════════════════
class Player:
    def __init__(self):
        self.name = ""
        self.gender = ""
        self.title = "平民"
        self.strength = 5
        self.intelligence = 5
        self.agility = 5
        self.charisma = 5
        self.luck = 5
        self.wealth = 3
        self.happiness = 5
        self.health = 80
        self.EI = 0
        self.SN = 0
        self.TF = 0
        self.JP = 0
        self.traits: List[str] = []
        self.age = 0
        self.decision_tree = None
        self._sbti_types = self._load_sbti_types()

        # ── B1 新增字段（§3.11，全部在 __init__ 赋默认值，R1）──
        self.schema_version = 2          # int  R3
        self.game_mode = ""              # str  BUG-2 修复：收敛进 to_dict
        self.birth_era = ""              # str
        self.region = ""                 # str
        self.siblings = ""               # str
        self.aptitude = ""               # str
        self.life_goal = ""              # str
        self.talents: List[str] = []     # list[str]
        self.talent_offered: List[str] = []  # list[str]
        self.era = "dynasty"             # str
        self.education = "none"          # str
        self.career_id = None            # str|None
        self.career_tier = 0             # int
        self.career_years = 0            # int
        self.relationships = {"parent": 60, "partner": 0, "friend": 40}  # dict[str,int]
        self.seen_content = {"cards": [], "events": []}   # dict[str, list[str]]
        self.run_flags: List[str] = []   # list[str]
        self.run_log: List[dict] = []    # list[dict]
        self.achievements_run: List[str] = []  # list[str]
        self.score = 0                   # int

    def _load_sbti_types(self) -> Dict:
        return {
            'INTJ': {'name': '卷王之王（INTJ）', 'desc': '你是那种"嘴上说着躺平，私下卷死所有人"的类型。表面佛系，实则早已规划到十年后。'},
            'INTP': {'name': '躺平学家（INTP）', 'desc': '人间清醒，看透一切，但懒。典型的"道理我都懂，但我就是不想动"。'},
            'ENTJ': {'name': '霸道总裁（ENTJ）', 'desc': '天生的领导，坚信"不听我的就滚蛋"。效率至上，但人际关系经常爆炸。'},
            'ENTP': {'name': '互联网杠精（ENTP）', 'desc': '行走的ETC，自动抬杠。看到观点就想辩驳，哪怕对方是你妈。'},
            'INFJ': {'name': '流泪圣母（INFJ）', 'desc': '表面温柔，内心戏精。一边治愈别人，一边自己深夜emo。'},
            'INFP': {'name': '流泪猫猫头（INFP）', 'desc': '高敏感人群，泪点极低。看到流浪猫能哭半小时，看到感人视频能哭一小时。'},
            'ENFJ': {'name': '人生导师（ENFJ）', 'desc': '人均心理医生，朋友的情绪垃圾桶。热心到让人怀疑是不是有社交NB症。'},
            'ENFP': {'name': '快乐修勾（ENFP）', 'desc': '快乐小狗，人形向日葵。有你的地方就有笑声，但专注力约等于金鱼。'},
            'ISTJ': {'name': '人形Excel（ISTJ）', 'desc': '人形规章，行走的SOP。讨厌变化，热爱清单，是老板最爱的打工人。'},
            'ISFJ': {'name': '老好人（ISFJ）', 'desc': '老好人，不会拒绝。帮同事带咖啡，帮朋友搬家，帮陌生人指路。'},
            'ESTJ': {'name': '职场卷王（ESTJ）', 'desc': '卷王本王，坚信"不加班的人生不完整"。口头禅是"你这个需求不合理"。'},
            'ESFJ': {'name': '社交悍匪（ESFJ）', 'desc': '社交悍匪，没有你暖不起来的场。但有时热情过度，让人想逃。'},
            'ISTP': {'name': '手艺人（ISTP）', 'desc': '手艺人，信奉"能动手就不哔哔"。工具控，动手能力强，但社交能力弱。'},
            'ISFP': {'name': '佛系艺术家（ISFP）', 'desc': '佛系艺术家，活在当下。口头禅是"都行，可以，没关系"，但审美极高。'},
            'ESTP': {'name': '社会人（ESTP）', 'desc': '社会人，人脉王。擅长见人说人话，见鬼说鬼话，但缺乏深度。'},
            'ESFP': {'name': '派对动物（ESFP）', 'desc': '派对动物，气氛组担当。有你在就不会冷场，但经常被说"不够稳重"。'}
        }

    @property
    def mbti_code(self) -> str:
        return ('E' if self.EI > 0 else 'I') + \
               ('S' if self.SN > 0 else 'N') + \
               ('T' if self.TF > 0 else 'F') + \
               ('J' if self.JP > 0 else 'P')

    @property
    def sbti(self) -> str:
        return self._sbti_types.get(self.mbti_code, {}).get('name', self.mbti_code)

    def get_sbti_description(self) -> str:
        return self._sbti_types.get(self.mbti_code, {}).get('desc', '你的性格很特别。')

    def adjust(self, **kwargs):
        for attr, delta in kwargs.items():
            if attr == 'traits':
                if isinstance(delta, list):
                    self.traits.extend(delta)
                elif isinstance(delta, str):
                    self.traits.append(delta)
            elif hasattr(self, attr):
                current = getattr(self, attr)
                if isinstance(current, (int, float)):
                    setattr(self, attr, current + delta)
            else:
                if attr in ['EI', 'SN', 'TF', 'JP']:
                    setattr(self, attr, getattr(self, attr, 0) + delta)
        for attr in ['strength', 'intelligence', 'agility', 'charisma', 'luck', 'wealth', 'happiness']:
            val = getattr(self, attr)
            setattr(self, attr, max(0, min(20, val)))
        self.health = max(0, min(100, self.health))

    def init_decision_tree(self):
        from decision_tree import DecisionTree, Dimension
        self.decision_tree = DecisionTree(self)
        trait_dim_map = {
            "高贵血统": [(Dimension.NOBLES, 20), (Dimension.CHARISMA, 10)],
            "富二代": [(Dimension.WEALTH, 25)],
            "草根": [(Dimension.COMMONERS, 20), (Dimension.NOBLES, -10)],
            "骑士训练": [(Dimension.STRENGTH, 20)],
            "学术熏陶": [(Dimension.INTELLIGENCE, 20)],
            "街头智慧": [(Dimension.INTELLIGENCE, 10), (Dimension.STABILITY, -5)],
            "冒险精神": [(Dimension.STRENGTH, 10), (Dimension.STABILITY, -5)],
            "商业头脑": [(Dimension.WEALTH, 15)],
            "神秘知识": [(Dimension.INTELLIGENCE, 15), (Dimension.CHURCH, -10)],
        }
        for trait, adjustments in trait_dim_map.items():
            if trait in self.traits:
                for dim, val in adjustments:
                    self.decision_tree.adjust_dimension(dim, val)
        mbti_code = self.mbti_code
        if mbti_code[0] == 'E':
            self.decision_tree.adjust_dimension(Dimension.CHARISMA, 10)
        else:
            self.decision_tree.adjust_dimension(Dimension.INTELLIGENCE, 10)
        if mbti_code[3] == 'J':
            self.decision_tree.adjust_dimension(Dimension.STABILITY, 10)

    def to_dict(self) -> Dict:
        return {
            'name': self.name, 'gender': self.gender, 'title': self.title,
            'strength': self.strength, 'intelligence': self.intelligence,
            'agility': self.agility, 'charisma': self.charisma,
            'luck': self.luck, 'wealth': self.wealth,
            'happiness': self.happiness, 'health': self.health,
            'EI': self.EI, 'SN': self.SN, 'TF': self.TF, 'JP': self.JP,
            'traits': self.traits, 'age': self.age
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Player':
        player = cls()
        for key, value in data.items():
            if hasattr(player, key):
                setattr(player, key, value)
        return player


# ══════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════
class GameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("人生重开模拟器 - SBTI毒舌版")
        self.geometry("960x720")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg_dark"])

        self.player: Optional[Player] = None
        self.game_mode = ""
        self.backgrounds = {}
        self.events_data = {}
        self.current_step = 0
        self.bg_step_keys = ['gender', 'father_job', 'childhood', 'teenage', 'adulthood']
        self.cultivation_events = self._make_cultivation_events()

        # 主容器
        self.main_frame = tk.Frame(self, bg=COLORS["bg_dark"])
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.show_main_menu()
        # 连胜提示浮层（任务 #12）：每进程一次打卡
        self._show_streak_toast()

    # ── 清屏 ──
    def clear_screen(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    # ── 标题栏组件 ──
    def make_title_bar(self, parent, title, subtitle=""):
        frame = tk.Frame(parent, bg=COLORS["bg_mid"], pady=12)
        frame.pack(fill=tk.X)
        tk.Label(frame, text=title, font=("Microsoft YaHei", 18, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_mid"]).pack()
        if subtitle:
            tk.Label(frame, text=subtitle, font=("Microsoft YaHei", 10),
                     fg=COLORS["text_dim"], bg=COLORS["bg_mid"]).pack()

    # ── 属性进度条 ──
    def make_stat_bar(self, parent, label, value, max_val, color, row):
        tk.Label(parent, text=label, font=("Microsoft YaHei", 10),
                 fg=COLORS["text"], bg=COLORS["card_bg"], anchor="e", width=6).grid(
            row=row, column=0, padx=(8, 4), pady=2, sticky="e")
        canvas = tk.Canvas(parent, width=180, height=16, bg=COLORS["bar_bg"],
                           highlightthickness=0)
        canvas.grid(row=row, column=1, padx=4, pady=2, sticky="w")
        fill_w = int(180 * min(value, max_val) / max_val)
        canvas.create_rectangle(0, 0, fill_w, 16, fill=color, outline="")
        tk.Label(parent, text=str(int(value)), font=("Microsoft YaHei", 9),
                 fg=COLORS["text_dim"], bg=COLORS["card_bg"], width=4).grid(
            row=row, column=2, padx=(2, 8), pady=2, sticky="w")

    # ── 状态面板（右侧） ──
    def make_stats_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["card_bg"], bd=1, relief="ridge")
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=8)

        p = self.player
        header = f"{p.name} ({p.title})" if p.name else "角色"
        tk.Label(panel, text=header, font=("Microsoft YaHei", 12, "bold"),
                 fg=COLORS["gold"], bg=COLORS["card_bg"]).pack(pady=(8, 2))
        info = f"{p.gender} | {p.age}岁 | {p.sbti}"
        tk.Label(panel, text=info, font=("Microsoft YaHei", 9),
                 fg=COLORS["text_dim"], bg=COLORS["card_bg"]).pack(pady=(0, 6))

        grid_frame = tk.Frame(panel, bg=COLORS["card_bg"])
        grid_frame.pack(padx=4, pady=4)

        stats = [
            ("力量", p.strength, 20, COLORS["red"]),
            ("智力", p.intelligence, 20, COLORS["blue"]),
            ("敏捷", p.agility, 20, COLORS["green"]),
            ("魅力", p.charisma, 20, COLORS["orange"]),
            ("运气", p.luck, 20, COLORS["purple"]),
            ("财富", p.wealth, 20, COLORS["gold"]),
            ("幸福", p.happiness, 20, COLORS["cyan"]),
            ("健康", p.health, 100, COLORS["red"]),
        ]
        for i, (label, val, mx, color) in enumerate(stats):
            self.make_stat_bar(grid_frame, label, val, mx, color, i)

        # MBTI维度
        mbti_frame = tk.Frame(panel, bg=COLORS["card_bg"])
        mbti_frame.pack(padx=8, pady=(6, 2), fill=tk.X)
        dims = [("EI", p.EI, "外向E/内向I"), ("SN", p.SN, "实感S/直觉N"),
                ("TF", p.TF, "思考T/情感F"), ("JP", p.JP, "判断J/知觉P")]
        for dim_name, val, hint in dims:
            row = tk.Frame(mbti_frame, bg=COLORS["card_bg"])
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{dim_name}: {val:+.0f}", font=("Microsoft YaHei", 9),
                     fg=COLORS["text_dim"], bg=COLORS["card_bg"], width=9, anchor="w").pack(side=tk.LEFT)
            # 偏向指示
            parts = hint.split("/")
            idx = 0 if val > 0 else 1
            tk.Label(row, text=parts[idx], font=("Microsoft YaHei", 9, "bold"),
                     fg=COLORS["accent"] if idx == 0 else COLORS["cyan"],
                     bg=COLORS["card_bg"]).pack(side=tk.LEFT)

        # 特质
        if p.traits:
            tk.Label(panel, text="─ 特质 ─", font=("Microsoft YaHei", 9),
                     fg=COLORS["text_dim"], bg=COLORS["card_bg"]).pack(pady=(6, 2))
            traits_text = "、".join(p.traits[:6])
            if len(p.traits) > 6:
                traits_text += "..."
            tk.Label(panel, text=traits_text, font=("Microsoft YaHei", 9),
                     fg=COLORS["highlight"], bg=COLORS["card_bg"],
                     wraplength=200, justify="left").pack(padx=8)

        return panel

    # ══════════════════════════════════════
    #  主菜单
    # ══════════════════════════════════════
    def show_main_menu(self):
        self.clear_screen()
        self.player = None

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="人生重开模拟器", font=("Microsoft YaHei", 32, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"]).pack(pady=(0, 4))
        tk.Label(center, text="SBTI毒舌版 · 含王权决策树",
                 font=("Microsoft YaHei", 13), fg=COLORS["accent"],
                 bg=COLORS["bg_dark"]).pack(pady=(0, 6))
        tk.Label(center, text="温馨提示：本游戏可能引起不适，玻璃心请退出",
                 font=("Microsoft YaHei", 10), fg=COLORS["text_dim"],
                 bg=COLORS["bg_dark"]).pack(pady=(0, 30))

        btn_style = {"font": ("Microsoft YaHei", 14), "width": 18, "height": 2,
                     "bd": 0, "cursor": "hand2", "activeforeground": "white"}

        tk.Button(center, text="🎮  新游戏", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.start_new_game,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="📂  加载游戏", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.load_game,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="📖  关于", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.show_about,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="🎯  挑战模式", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.show_challenge_menu,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="🏺  家族传承", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.show_lineage_panel,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="📜  结局图鉴", bg=COLORS["bg_light"], fg=COLORS["text"],
                  activebackground=COLORS["accent"], command=self.show_ending_codex,
                  **btn_style).pack(pady=6)
        tk.Button(center, text="🚪  退出", bg=COLORS["bg_light"], fg=COLORS["text_dim"],
                  activebackground=COLORS["accent"], command=self.quit,
                  **btn_style).pack(pady=6)

    # ══════════════════════════════════════
    #  关于
    # ══════════════════════════════════════
    def show_about(self):
        self.clear_screen()
        self.make_title_bar(self.main_frame, "📖 关于", "人生重开模拟器 v2.1.0")
        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")
        features = [
            "✦ SBTI风格毒舌出身选择",
            "✦ 王权决策树系统（11维度平衡）",
            "✦ 传统人生 / 修行之路 / 王权模式",
            "✦ 存档/读档功能",
            "✦ 60 数据驱动结局 + 结局图鉴",
            "✦ 挑战模式（开局强制条件 + 奖励解锁）",
            "✦ 家族传承：传家宝图鉴与掷骰继承",
            "✦ 每日连胜打卡与里程碑 buff",
        ]
        for feat in features:
            tk.Label(center, text=feat, font=("Microsoft YaHei", 13),
                     fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=3)
        tk.Button(center, text="返回主菜单", font=("Microsoft YaHei", 12),
                  bg=COLORS["bg_light"], fg=COLORS["text"],
                  command=self.show_main_menu, width=16, bd=0,
                  cursor="hand2").pack(pady=30)

    # ══════════════════════════════════════
    #  出身选择流程
    # ══════════════════════════════════════
    def start_new_game(self):
        # 走 ContentLoader 深合并，使 GUI 也能看到 content/ 下的全部增强内容
        # （含 by_age / by_career / by_trait 新增事件、现代篇卡、generic 等），
        # 与 CLI 共用同一加载入口，避免两套数据源漂移。
        cl = ContentLoader().load()
        self.content = cl
        self.backgrounds = cl.raw.get("backgrounds", []) or []
        self.events_data = cl.raw
        if not self.backgrounds:
            messagebox.showerror("错误", "找不到 backgrounds.json，请确认文件在同一目录。")
            return
        self.player = Player()
        self.current_step = -1  # -1=输入名字
        # 开局接线（任务 #10/#11/#12 收口）：挑战覆写 + 传家宝加成 + 连胜 buff
        try:
            from core import runtime
            runtime.begin_run(self.player)
        except Exception:
            pass
        self.show_background_step()

    def show_background_step(self):
        self.clear_screen()
        p = self.player

        if self.current_step == -1:
            # ── 输入名字 ──
            self.make_title_bar(self.main_frame, "✏️ 第1步：起名", "不输就随机，反正都是命")
            center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
            center.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(center, text="请输入你的名字：", font=("Microsoft YaHei", 14),
                     fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(pady=10)
            name_var = tk.StringVar()
            entry = tk.Entry(center, textvariable=name_var, font=("Microsoft YaHei", 14),
                             width=20, bg=COLORS["card_bg"], fg=COLORS["text"],
                             insertbackground=COLORS["text"])
            entry.pack(pady=8)
            entry.focus_set()

            def confirm_name(event=None):
                name = name_var.get().strip()
                if not name:
                    random_names = self.backgrounds.get('steps', {}).get('name', {}).get('random_names', ['无名氏'])
                    name = random.choice(random_names)
                p.name = name
                self.current_step = 0
                self.show_background_step()

            entry.bind("<Return>", confirm_name)
            tk.Button(center, text="确  定", font=("Microsoft YaHei", 13),
                      bg=COLORS["accent"], fg="white", width=12, bd=0,
                      cursor="hand2", command=confirm_name).pack(pady=16)
        else:
            # ── 选择步骤 ──
            if self.current_step >= len(self.bg_step_keys):
                self.show_background_done()
                return

            step_key = self.bg_step_keys[self.current_step]
            step_data = self.backgrounds.get('steps', {}).get(step_key, {})
            step_title = step_data.get('title', f'第{self.current_step + 2}步')
            step_desc = step_data.get('description', '请选择：')
            options = step_data.get('options', [])

            self.make_title_bar(self.main_frame, step_title, step_desc)

            center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
            center.place(relx=0.5, rely=0.5, anchor="center")

            for opt in options:
                key = opt.get('key', '')
                text = opt.get('text', '')
                btn = tk.Button(center, text=f"  {key}. {text}  ",
                                font=("Microsoft YaHei", 11), width=50, height=2,
                                bg=COLORS["card_bg"], fg=COLORS["text"],
                                activebackground=COLORS["accent"],
                                activeforeground="white", bd=0, cursor="hand2",
                                wraplength=460, justify="left",
                                command=lambda o=opt: self.apply_background_choice(o))
                btn.pack(pady=5)

    def apply_background_choice(self, option):
        p = self.player
        effects = option.get('effects', {})
        if 'gender' in effects:
            p.gender = effects['gender']
        if 'stats' in effects:
            for stat, value in effects['stats'].items():
                if hasattr(p, stat):
                    setattr(p, stat, getattr(p, stat) + value)
        if 'mbti' in effects:
            for dim, value in effects['mbti'].items():
                if hasattr(p, dim):
                    setattr(p, dim, getattr(p, dim) + value)
        if 'traits' in effects:
            p.traits.extend(effects['traits'])

        feedback = option.get('feedback', '')
        self.current_step += 1
        if feedback:
            self.show_feedback_then_continue(feedback)
        else:
            self.show_background_step()

    def show_feedback_then_continue(self, feedback):
        self.clear_screen()
        self.make_title_bar(self.main_frame, "📝 系统评价")
        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text=feedback, font=("Microsoft YaHei", 13),
                 fg=COLORS["highlight"], bg=COLORS["bg_dark"],
                 wraplength=500, justify="left").pack(pady=20)
        tk.Button(center, text="继  续", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=12, bd=0,
                  cursor="hand2", command=self.show_background_step).pack(pady=16)

    def show_background_done(self):
        self.player.age = 20
        self.clear_screen()
        p = self.player

        self.make_title_bar(self.main_frame, "🎉 出身选择完成！")

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        info_lines = [
            f"姓名：{p.name}",
            f"性别：{p.gender}",
            f"年龄：{p.age}岁（法定成年，但心理年龄待定）",
            f"SBTI人格：{p.sbti}",
        ]
        for line in info_lines:
            tk.Label(center, text=line, font=("Microsoft YaHei", 13),
                     fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=2)

        tk.Label(center, text=p.get_sbti_description(), font=("Microsoft YaHei", 11),
                 fg=COLORS["highlight"], bg=COLORS["bg_dark"],
                 wraplength=500, justify="left").pack(pady=8)

        # 显示属性
        self._show_inline_stats(center, p)

        tk.Button(center, text="选择人生道路 →", font=("Microsoft YaHei", 14),
                  bg=COLORS["accent"], fg="white", width=20, bd=0,
                  cursor="hand2", command=self.show_life_path_choice).pack(pady=20)

    def _show_inline_stats(self, parent, p):
        frame = tk.Frame(parent, bg=COLORS["card_bg"], bd=1, relief="ridge")
        frame.pack(pady=8, padx=20, fill=tk.X)
        stats = [
            ("力量", p.strength, 20, COLORS["red"]),
            ("智力", p.intelligence, 20, COLORS["blue"]),
            ("敏捷", p.agility, 20, COLORS["green"]),
            ("魅力", p.charisma, 20, COLORS["orange"]),
            ("运气", p.luck, 20, COLORS["purple"]),
            ("财富", p.wealth, 20, COLORS["gold"]),
            ("幸福", p.happiness, 20, COLORS["cyan"]),
            ("健康", p.health, 100, COLORS["red"]),
        ]
        for i, (label, val, mx, color) in enumerate(stats):
            row = tk.Frame(frame, bg=COLORS["card_bg"])
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=label, font=("Microsoft YaHei", 9), width=4,
                     fg=COLORS["text"], bg=COLORS["card_bg"], anchor="e").pack(side=tk.LEFT)
            canvas = tk.Canvas(row, width=200, height=12, bg=COLORS["bar_bg"], highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=4)
            fill_w = int(200 * min(val, mx) / mx)
            canvas.create_rectangle(0, 0, fill_w, 12, fill=color, outline="")
            tk.Label(row, text=str(int(val)), font=("Microsoft YaHei", 9),
                     fg=COLORS["text_dim"], bg=COLORS["card_bg"], width=4).pack(side=tk.LEFT)

    # ══════════════════════════════════════
    #  人生道路选择
    # ══════════════════════════════════════
    def show_life_path_choice(self):
        self.clear_screen()
        self.make_title_bar(self.main_frame, "🛤️ 人生道路选择", "你已成年，请选择未来")

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        paths = [
            ("👑  权力之路", "进入王权决策系统，统治国家\n管理国家，平衡各方势力，做出重大决策",
             COLORS["accent"], "reigns"),
            ("⚔️  冒险之路", "传统人生事件系统\n经历随机事件，体验多样人生",
             COLORS["green"], "traditional"),
            ("🧘  修行之路", "专注个人成长\n提升自我，探索内心世界",
             COLORS["purple"], "cultivation"),
        ]

        for title, desc, color, mode in paths:
            card = tk.Frame(center, bg=COLORS["card_bg"], bd=1, relief="ridge")
            card.pack(pady=8, fill=tk.X, padx=40)
            tk.Label(card, text=title, font=("Microsoft YaHei", 14, "bold"),
                     fg=color, bg=COLORS["card_bg"]).pack(pady=(8, 2))
            tk.Label(card, text=desc, font=("Microsoft YaHei", 10),
                     fg=COLORS["text_dim"], bg=COLORS["card_bg"],
                     justify="center").pack(pady=(0, 4))
            tk.Button(card, text="选择此路", font=("Microsoft YaHei", 11),
                      bg=color, fg="white", width=14, bd=0, cursor="hand2",
                      command=lambda m=mode: self.start_game_mode(m)).pack(pady=(2, 10))

    # ══════════════════════════════════════
    #  启动游戏模式
    # ══════════════════════════════════════
    def start_game_mode(self, mode):
        # BUG-1 修复（D7）：入口处统一归一化为 canonical 值
        self.game_mode = constants.normalize_mode(mode)
        if self.game_mode == "reigns":
            self.player.init_decision_tree()
            self.show_reigns_screen()
        elif self.game_mode == "traditional":
            self.adventure_stage = 0
            self.show_adventure_event()
        else:  # cultivation
            self.cultivation_stage = 0
            self.show_cultivation_event()

    # ══════════════════════════════════════
    #  王权决策模式
    # ══════════════════════════════════════
    def show_reigns_screen(self):
        self.clear_screen()
        p = self.player
        dt = p.decision_tree

        # 检查游戏结束
        game_over, message = dt.is_game_over()
        if game_over or p.age >= 100:
            self.show_reigns_ending(message if game_over else "你已年迈，决定退位让贤。")
            return

        # 标题
        self.make_title_bar(self.main_frame,
                            f"👑 第{dt.year}年 {dt.get_current_season()}季",
                            f"统治第{len(dt.history) + 1}个决策")

        content = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True)

        # 左侧：决策卡
        left = tk.Frame(content, bg=COLORS["bg_dark"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)

        # 获取可用卡牌
        available_cards = dt.get_available_cards()
        if not available_cards:
            dt.advance_time()
            p.age += 1
            self.after(500, self.show_reigns_screen)
            return

        card = available_cards[0]

        # 危机警告
        warning = dt.get_crisis_warning()
        if warning:
            tk.Label(left, text=warning, font=("Microsoft YaHei", 12, "bold"),
                     fg=COLORS["red"], bg=COLORS["bg_dark"]).pack(pady=(4, 2))

        # 卡牌
        card_frame = tk.Frame(left, bg=COLORS["card_bg"], bd=2, relief="ridge")
        card_frame.pack(pady=8, padx=8, fill=tk.X)

        tk.Label(card_frame, text=card['title'], font=("Microsoft YaHei", 16, "bold"),
                 fg=COLORS["gold"], bg=COLORS["card_bg"]).pack(pady=(12, 4))
        tk.Label(card_frame, text=card['description'], font=("Microsoft YaHei", 12),
                 fg=COLORS["text"], bg=COLORS["card_bg"],
                 wraplength=380, justify="center").pack(pady=(0, 12))

        # 选择按钮
        btn_frame = tk.Frame(left, bg=COLORS["bg_dark"])
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text=f"← {card['left_choice']['text']}",
                  font=("Microsoft YaHei", 12), bg=COLORS["btn_left"], fg="white",
                  width=22, height=2, bd=0, cursor="hand2", wraplength=200,
                  command=lambda: self.apply_reigns_choice(card, "left_choice")).pack(side=tk.LEFT, padx=8)

        tk.Button(btn_frame, text=f"{card['right_choice']['text']} →",
                  font=("Microsoft YaHei", 12), bg=COLORS["btn_right"], fg="white",
                  width=22, height=2, bd=0, cursor="hand2", wraplength=200,
                  command=lambda: self.apply_reigns_choice(card, "right_choice")).pack(side=tk.LEFT, padx=8)

        # 右侧：状态面板
        self._make_reigns_stats_panel(content)

    def _make_reigns_stats_panel(self, parent):
        from decision_tree import Dimension
        dt = self.player.decision_tree

        panel = tk.Frame(parent, bg=COLORS["card_bg"], bd=1, relief="ridge", width=240)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=8)
        panel.pack_propagate(False)

        tk.Label(panel, text="👑 国家状态", font=("Microsoft YaHei", 12, "bold"),
                 fg=COLORS["gold"], bg=COLORS["card_bg"]).pack(pady=(8, 4))

        dims_display = [
            (Dimension.STRENGTH, "军力", COLORS["red"]),
            (Dimension.INTELLIGENCE, "智慧", COLORS["blue"]),
            (Dimension.CHARISMA, "民心", COLORS["orange"]),
            (Dimension.WEALTH, "财政", COLORS["gold"]),
            (Dimension.MORALITY, "道德", COLORS["cyan"]),
            (Dimension.STABILITY, "稳定", COLORS["green"]),
            (Dimension.CHURCH, "教会", COLORS["purple"]),
            (Dimension.NOBLES, "贵族", COLORS["accent2"]),
            (Dimension.COMMONERS, "平民", COLORS["cyan"]),
            (Dimension.HEALTH, "健康", COLORS["red"]),
            (Dimension.HAPPINESS, "幸福", COLORS["green"]),
        ]

        grid = tk.Frame(panel, bg=COLORS["card_bg"])
        grid.pack(padx=4, pady=4)

        for i, (dim, name, color) in enumerate(dims_display):
            val = dt.dimensions[dim]
            _, emoji = dt.get_dimension_status(dim)
            self.make_stat_bar(grid, f"{emoji}{name}", val, 100, color, i)

    def apply_reigns_choice(self, card, choice_key):
        result = self.player.decision_tree.apply_decision(card, choice_key)
        self.player.age += 1
        self._show_reigns_result(result)

    def _show_reigns_result(self, result):
        self.clear_screen()
        self.make_title_bar(self.main_frame, "📜 决策结果")

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        # 台词
        speech = result.get('speech', '')
        if speech:
            tk.Label(center, text=f"「{speech}」", font=("Microsoft YaHei", 14, "italic"),
                     fg=COLORS["highlight"], bg=COLORS["bg_dark"],
                     wraplength=500).pack(pady=10)

        # 效果
        effects = result.get('effects', {})
        if effects:
            from decision_tree import Dimension
            eff_frame = tk.Frame(center, bg=COLORS["card_bg"], bd=1, relief="ridge")
            eff_frame.pack(pady=8, padx=20)
            tk.Label(eff_frame, text="决策影响", font=("Microsoft YaHei", 11, "bold"),
                     fg=COLORS["gold"], bg=COLORS["card_bg"]).pack(pady=(8, 4))
            for dim_name, delta in effects.items():
                try:
                    dim_obj = Dimension[dim_name]
                    sign = "+" if delta > 0 else ""
                    color = COLORS["green"] if delta > 0 else COLORS["red"]
                    tk.Label(eff_frame, text=f"  {dim_obj.value}: {sign}{delta}",
                             font=("Microsoft YaHei", 11), fg=color,
                             bg=COLORS["card_bg"]).pack(anchor="w", padx=12)
                except KeyError:
                    pass
            tk.Label(eff_frame, text="", bg=COLORS["card_bg"]).pack(pady=2)

        # 连锁反应
        chain_reactions = result.get('chain_reactions', [])
        if chain_reactions:
            for reaction in chain_reactions:
                tk.Label(center, text=f"⚡ {reaction['title']}",
                         font=("Microsoft YaHei", 12, "bold"),
                         fg=COLORS["orange"], bg=COLORS["bg_dark"]).pack(pady=(4, 0))
                tk.Label(center, text=reaction['description'],
                         font=("Microsoft YaHei", 10), fg=COLORS["text_dim"],
                         bg=COLORS["bg_dark"], wraplength=400).pack()

        tk.Button(center, text="继续统治 →", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=16, bd=0,
                  cursor="hand2", command=self.show_reigns_screen).pack(pady=20)

    def show_reigns_ending(self, message):
        self.clear_screen()
        p = self.player
        dt = p.decision_tree
        from decision_tree import Dimension

        self.make_title_bar(self.main_frame, "👑 统治结束")

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(center, text=message, font=("Microsoft YaHei", 16, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"],
                 wraplength=500).pack(pady=10)

        if dt:
            tk.Label(center, text=f"统治时间：{dt.year}年 | 重大决策：{len(dt.history)}次",
                     font=("Microsoft YaHei", 12), fg=COLORS["text_dim"],
                     bg=COLORS["bg_dark"]).pack(pady=4)

            ending_text = dt.get_ending_based_on_history()
            tk.Label(center, text=f"历史评价：{ending_text}",
                     font=("Microsoft YaHei", 12), fg=COLORS["text"],
                     bg=COLORS["bg_dark"], wraplength=500).pack(pady=8)

            # 称号
            dims = dt.dimensions
            titles = []
            if dims[Dimension.STRENGTH] >= 80: titles.append("征服者")
            if dims[Dimension.INTELLIGENCE] >= 80: titles.append("智者")
            if dims[Dimension.CHARISMA] >= 80: titles.append("仁君")
            if dims[Dimension.WEALTH] >= 80: titles.append("富王")
            if dims[Dimension.STABILITY] >= 80: titles.append("明君")
            if dims[Dimension.COMMONERS] >= 80 and dims[Dimension.NOBLES] >= 80: titles.append("平衡大师")

            if titles:
                tk.Label(center, text=f"历史称号：{'、'.join(titles)}",
                         font=("Microsoft YaHei", 13, "bold"), fg=COLORS["accent"],
                         bg=COLORS["bg_dark"]).pack(pady=6)
            else:
                tk.Label(center, text="历史评价：普通统治者",
                         font=("Microsoft YaHei", 12), fg=COLORS["text_dim"],
                         bg=COLORS["bg_dark"]).pack(pady=6)

        # 最终结局（含 7 个王权专属结局）
        self._render_ending_block(center, "reigns", wrap=500)

        tk.Button(center, text="保存并返回主菜单", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=20, bd=0,
                  cursor="hand2", command=self.save_and_return).pack(pady=20)

    # ══════════════════════════════════════
    #  冒险模式
    # ══════════════════════════════════════
    def show_adventure_event(self):
        p = self.player
        if self.adventure_stage >= 8 or p.age >= 100:
            self.show_traditional_ending()
            return

        self.clear_screen()
        self.make_title_bar(self.main_frame, f"⚔️ 你 {p.age} 岁了",
                            f"第{self.adventure_stage + 1}/8 个十年")

        content = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True)

        # 右侧状态
        self.make_stats_panel(content)

        # 左侧事件
        left = tk.Frame(content, bg=COLORS["bg_dark"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 获取可用事件
        event = self._pick_adventure_event()
        desc = event.get('desc', '发生了一些事...')
        options = event.get('options', {})

        # 事件描述
        card_frame = tk.Frame(left, bg=COLORS["card_bg"], bd=2, relief="ridge")
        card_frame.pack(pady=8, fill=tk.X, padx=4)

        tk.Label(card_frame, text=desc, font=("Microsoft YaHei", 14),
                 fg=COLORS["text"], bg=COLORS["card_bg"],
                 wraplength=420, justify="center").pack(pady=16, padx=12)

        # 选项按钮
        for key, opt_data in options.items():
            text = opt_data.get('text', key)
            btn = tk.Button(left, text=f"  {key}. {text}  ",
                            font=("Microsoft YaHei", 12), width=40, height=2,
                            bg=COLORS["bg_light"], fg=COLORS["text"],
                            activebackground=COLORS["accent"],
                            activeforeground="white", bd=0, cursor="hand2",
                            wraplength=360, justify="left",
                            command=lambda o=opt_data: self.apply_adventure_choice(o))
            btn.pack(pady=4, padx=20)

    def _pick_adventure_event(self) -> Dict:
        p = self.player
        ev = self.events_data
        templates = ev.get('event_templates', {})

        possible = list(templates.get('generic', []))

        if p.wealth >= 7:
            possible.extend(templates.get('by_wealth', {}).get('rich', []))
        elif p.wealth <= 2:
            possible.extend(templates.get('by_wealth', {}).get('poor', []))

        if p.EI > 0:
            possible.extend(templates.get('by_personality', {}).get('extrovert', []))
        else:
            possible.extend(templates.get('by_personality', {}).get('introvert', []))

        mbti = p.mbti_code
        if mbti in ['INTJ', 'INTP', 'ENTJ', 'ENTP']:
            possible.extend(templates.get('by_personality', {}).get('nt_rational', []))
        if mbti in ['INFP', 'INFJ', 'ENFP', 'ENFJ']:
            possible.extend(templates.get('by_personality', {}).get('nf_idealist', []))
        if p.strength >= 8:
            possible.extend(templates.get('by_personality', {}).get('strong_warrior', []))
        if p.intelligence >= 8:
            possible.extend(templates.get('by_personality', {}).get('smart_scholar', []))
        if "冒险精神" in p.traits:
            possible.extend(templates.get('by_personality', {}).get('adventurer', []))

        age_events = templates.get('by_age', {}).get(get_age_group(p.age), [])
        possible.extend(age_events)

        # 按职业类别（需已选定职业）：career_id -> category（与 CLI life_event 对齐）
        career_id = getattr(p, 'career_id', None)
        if career_id and self.content is not None:
            try:
                career = self.content.career(str(career_id))
                if career is not None:
                    cat = getattr(career, 'category', None)
                    if cat:
                        possible.extend(templates.get('by_career', {}).get(cat, []))
            except Exception:
                pass

        # 按特质：玩家拥有的每个特质若有对应池则接入
        by_trait = templates.get('by_trait', {})
        for t in (getattr(p, 'traits', None) or []):
            if t in by_trait:
                possible.extend(by_trait[t])

        if not possible:
            possible = [{"desc": "平淡的一天，什么都没发生。",
                          "options": {"A": {"text": "继续生活", "effects": {},
                                            "feedback": ["又是平凡的一天。"]}}}]
        return random.choice(possible)

    def apply_adventure_choice(self, opt_data):
        effects = opt_data.get('effects', {})
        self.player.adjust(**effects)
        feedbacks = opt_data.get('feedback', ["这很符合你的人设。"])
        feedback = random.choice(feedbacks)
        self.player.age += 10
        self.adventure_stage += 1
        self._show_event_feedback(feedback, self.show_adventure_event)

    # ══════════════════════════════════════
    #  修行模式
    # ══════════════════════════════════════
    def _make_cultivation_events(self) -> List[Dict]:
        return [
            {
                "desc": "你在山中遇到一位老者，他问你是否愿意听他讲道。",
                "options": {
                    "A": {"text": "虚心求教 (智力+2, 幸福+1)", "effects": {"intelligence": 2, "happiness": 1}, "feedback": ["悟性+1。", "大道至简。"]},
                    "B": {"text": "婉言谢绝，自行参悟 (智力+1, JP+1)", "effects": {"intelligence": 1, "JP": 1}, "feedback": ["独自修行。", "佛在心中。"]},
                    "C": {"text": "和他切磋辩论 (智力+1, 魅力+1, EI+1)", "effects": {"intelligence": 1, "charisma": 1, "EI": 1}, "feedback": ["棋逢对手。", "以辩会友。"]}
                }
            },
            {
                "desc": "你在溪边冥想，忽然顿悟了什么。",
                "options": {
                    "A": {"text": "顺着感觉走 (运气+2, 幸福+2)", "effects": {"luck": 2, "happiness": 2}, "feedback": ["天人合一。", "道法自然。"]},
                    "B": {"text": "记录下来反复研究 (智力+3, JP+1)", "effects": {"intelligence": 3, "JP": 1}, "feedback": ["好记性不如烂笔头。", "格物致知。"]},
                    "C": {"text": "与路过的旅人分享 (魅力+2, 幸福+1)", "effects": {"charisma": 2, "happiness": 1}, "feedback": ["渡人渡己。", "法布施。"]}
                }
            },
            {
                "desc": "山中风雨大作，你的小屋被吹塌了。",
                "options": {
                    "A": {"text": "重建小屋 (力量+2, 敏捷+1)", "effects": {"strength": 2, "agility": 1}, "feedback": ["自力更生。", "锻炼身体。"]},
                    "B": {"text": "在雨中冥想 (幸福+2, 健康-10)", "effects": {"happiness": 2, "health": -10}, "feedback": ["苦行僧。", "身体是革命的本钱啊。"]},
                    "C": {"text": "下山暂避 (财富-1, 魅力+1)", "effects": {"wealth": -1, "charisma": 1}, "feedback": ["入世修行。", "红尘炼心。"]}
                }
            },
            {
                "desc": "你遇到了一群山贼拦路。",
                "options": {
                    "A": {"text": "以武力击退 (力量+2, 魅力-1)", "effects": {"strength": 2, "charisma": -1}, "feedback": ["以暴制暴。", "武功再高也怕菜刀。"]},
                    "B": {"text": "以德服人 (魅力+3, 运气+1)", "effects": {"charisma": 3, "luck": 1}, "feedback": ["感化了。", "浪子回头。"]},
                    "C": {"text": "绕路而行 (敏捷+2)", "effects": {"agility": 2}, "feedback": ["三十六计走为上。", "避其锋芒。"]}
                }
            }
        ]

    def show_cultivation_event(self):
        p = self.player
        if self.cultivation_stage >= 8 or p.age >= 100:
            self.show_cultivation_ending()
            return

        self.clear_screen()
        self.make_title_bar(self.main_frame, f"🧘 修行第{self.cultivation_stage + 1}年",
                            f"{p.age}岁")

        content = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True)

        self.make_stats_panel(content)

        left = tk.Frame(content, bg=COLORS["bg_dark"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 选事件
        if random.random() < 0.5 and self.cultivation_events:
            event = random.choice(self.cultivation_events)
        else:
            generic = self.events_data.get('event_templates', {}).get('generic', [])
            event = random.choice(generic) if generic else random.choice(self.cultivation_events)

        desc = event.get('desc', '发生了一些事...')
        options = event.get('options', {})

        card_frame = tk.Frame(left, bg=COLORS["card_bg"], bd=2, relief="ridge")
        card_frame.pack(pady=8, fill=tk.X, padx=4)
        tk.Label(card_frame, text=desc, font=("Microsoft YaHei", 14),
                 fg=COLORS["text"], bg=COLORS["card_bg"],
                 wraplength=420, justify="center").pack(pady=16, padx=12)

        for key, opt_data in options.items():
            text = opt_data.get('text', key)
            btn = tk.Button(left, text=f"  {key}. {text}  ",
                            font=("Microsoft YaHei", 12), width=40, height=2,
                            bg=COLORS["bg_light"], fg=COLORS["text"],
                            activebackground=COLORS["accent"],
                            activeforeground="white", bd=0, cursor="hand2",
                            wraplength=360, justify="left",
                            command=lambda o=opt_data: self.apply_cultivation_choice(o))
            btn.pack(pady=4, padx=20)

    def apply_cultivation_choice(self, opt_data):
        effects = opt_data.get('effects', {})
        self.player.adjust(**effects)
        feedbacks = opt_data.get('feedback', ["道可道，非常道。"])
        feedback = random.choice(feedbacks)
        self.player.age += 10
        self.cultivation_stage += 1
        self._show_event_feedback(feedback, self.show_cultivation_event)

    # ── 通用事件反馈 ──
    def _show_event_feedback(self, feedback, next_callback):
        self.clear_screen()
        self.make_title_bar(self.main_frame, "✨ 结果")
        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        # 内联显示当前属性
        p = self.player
        self._show_inline_stats(center, p)

        tk.Label(center, text=f"「{feedback}」", font=("Microsoft YaHei", 14, "italic"),
                 fg=COLORS["highlight"], bg=COLORS["bg_dark"],
                 wraplength=500).pack(pady=12)

        tk.Button(center, text="继续 →", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=14, bd=0,
                  cursor="hand2", command=next_callback).pack(pady=16)

    # ══════════════════════════════════════
    #  传统结局
    # ══════════════════════════════════════
    def show_traditional_ending(self):
        self.clear_screen()
        p = self.player

        self.make_title_bar(self.main_frame, "📋 人生总结报告")

        center_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center_frame.pack(fill=tk.BOTH, expand=True)

        # 滚动区域
        canvas = tk.Canvas(center_frame, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(center_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg_dark"])

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        inner = tk.Frame(scroll_frame, bg=COLORS["bg_dark"], padx=40, pady=10)
        inner.pack(fill=tk.X)

        # 基本信息
        info_lines = [
            f"姓名：{p.name}",
            f"性别：{p.gender}",
            f"终年：{p.age}岁",
            f"SBTI类型：{p.sbti}",
        ]
        for line in info_lines:
            tk.Label(inner, text=line, font=("Microsoft YaHei", 13),
                     fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=1)

        tk.Label(inner, text=p.get_sbti_description(), font=("Microsoft YaHei", 11),
                 fg=COLORS["highlight"], bg=COLORS["bg_dark"],
                 wraplength=600, justify="left").pack(anchor="w", pady=(4, 8))

        # 属性总结
        tk.Label(inner, text="【属性总结】", font=("Microsoft YaHei", 13, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=(8, 4))

        attr_summaries = [
            ("财富", p.wealth, {True: "财务自由", None: "刚好够用", False: "有点拮据"}),
            ("幸福", p.happiness, {True: "非常幸福", None: "一般幸福", False: "不太幸福"}),
            ("魅力", p.charisma, {True: "人见人爱", None: "普普通通", False: "存在感低"}),
            ("智力", p.intelligence, {True: "天才", None: "普通人", False: "有待提高"}),
            ("力量", p.strength, {True: "猛人", None: "正常", False: "战五渣"}),
            ("运气", p.luck, {True: "天选之子", None: "一般", False: "非酋"}),
        ]
        for name, val, levels in attr_summaries:
            level = levels[True] if val >= 8 else (levels[False] if val <= 3 else levels[None])
            bar = "█" * min(val, 10) + "░" * (10 - min(val, 10))
            tk.Label(inner, text=f"  {name}：{bar}  {level}",
                     font=("Microsoft YaHei", 11), fg=COLORS["text"],
                     bg=COLORS["bg_dark"]).pack(anchor="w", pady=1)

        # 特质
        if p.traits:
            tk.Label(inner, text="\n【人生特质】", font=("Microsoft YaHei", 13, "bold"),
                     fg=COLORS["gold"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=(8, 4))
            tk.Label(inner, text="  " + "、".join(p.traits),
                     font=("Microsoft YaHei", 11), fg=COLORS["highlight"],
                     bg=COLORS["bg_dark"], wraplength=600, justify="left").pack(anchor="w")

        # 最终评价
        tk.Label(inner, text="\n【最终评价】", font=("Microsoft YaHei", 13, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=(8, 4))

        final_words = {
            'INTJ': "你一生都在计划和执行，但可能忘了为什么出发。",
            'INTP': "你想明白了很多事，但该做的事一件没做。",
            'ENTJ': "你带领团队完成了KPI，但没交到什么朋友。",
            'ENTP': "你赢了所有辩论，但输了所有人际关系。",
            'INFJ': "你治愈了很多人，但深夜自己偷偷emo。",
            'INFP': "你为世界流了太多泪，但世界依然如此。",
            'ENFJ': "你成为了很多人的太阳，但自己也会累。",
            'ENFP': "你给世界带来快乐，但没给自己找到答案。",
            'ISTJ': "你遵守了所有规则，但可能错过了意外之喜。",
            'ISFJ': "你帮助了所有人，但忘了帮助自己。",
            'ESTJ': "你卷赢了所有人，但不知道为了什么。",
            'ESFJ': "你温暖了所有人，但边界感有点模糊。",
            'ISTP': "你动手解决了很多问题，但没解决自己的孤独。",
            'ISFP': "你活得很美，但可能有点不接地气。",
            'ESTP': "你玩得很开心，但深度思考可能不够。",
            'ESFP': "你是派对的中心，但一个人的时候会空虚。"
        }
        mbti = p.mbti_code
        tk.Label(inner, text="  " + final_words.get(mbti, "你度过了独特的一生。"),
                 font=("Microsoft YaHei", 12), fg=COLORS["text"],
                 bg=COLORS["bg_dark"], wraplength=600, justify="left").pack(anchor="w", pady=4)

        # 最终结局（数据驱动，60 结局库按 priority 匹配）
        self._render_ending_block(inner, "traditional", wrap=600)

        # 寿命评价
        age_msg = ""
        if p.age >= 90: age_msg = "活得太久，见证了太多历史"
        elif p.age >= 80: age_msg = "正常退休，开始养生"
        elif p.age >= 70: age_msg = "开始被年轻人叫爷爷/奶奶"
        elif p.age >= 60: age_msg = "刚退休，还没想好干什么"
        else: age_msg = "英年早逝，但可能避免了中年危机"

        tk.Label(inner, text=f"\n寿命评价：{age_msg}", font=("Microsoft YaHei", 11),
                 fg=COLORS["text_dim"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=4)

        tk.Label(inner, text="\n游戏结束，但你的人生还在继续\n（本测试仅供娱乐，别太当真）",
                 font=("Microsoft YaHei", 11), fg=COLORS["text_dim"],
                 bg=COLORS["bg_dark"]).pack(anchor="w", pady=(8, 4))

        tk.Button(inner, text="保存并返回主菜单", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=20, bd=0,
                  cursor="hand2", command=self.save_and_return).pack(pady=20)

    # ══════════════════════════════════════
    #  修行结局
    # ══════════════════════════════════════
    def show_cultivation_ending(self):
        self.clear_screen()
        p = self.player

        self.make_title_bar(self.main_frame, "🧘 修行总结")

        center = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(center, text=f"姓名：{p.name}", font=("Microsoft YaHei", 14),
                 fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=2)
        tk.Label(center, text=f"终年：{p.age}岁", font=("Microsoft YaHei", 14),
                 fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=2)
        tk.Label(center, text=f"SBTI类型：{p.sbti}", font=("Microsoft YaHei", 14),
                 fg=COLORS["text"], bg=COLORS["bg_dark"]).pack(anchor="w", pady=2)

        # 修行结果
        if p.intelligence >= 15:
            result = "你悟道成仙，化为山间一缕清风。"
        elif p.happiness >= 15:
            result = "你修成正果，内心无比宁静。"
        elif p.strength >= 15:
            result = "你武道通神，成为一代宗师。"
        else:
            result = "你虽未成大道，但心有所得，不虚此行。"

        tk.Label(center, text=f"\n{result}", font=("Microsoft YaHei", 15, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"],
                 wraplength=500).pack(pady=12)

        # 最终结局（含 3 个修行专属结局）
        self._render_ending_block(center, "cultivation", wrap=500)

        self._show_inline_stats(center, p)

        tk.Button(center, text="保存并返回主菜单", font=("Microsoft YaHei", 13),
                  bg=COLORS["accent"], fg="white", width=20, bd=0,
                  cursor="hand2", command=self.save_and_return).pack(pady=20)

    # ══════════════════════════════════════
    #  结局解析块（三种模式共用）
    # ══════════════════════════════════════
    def _render_ending_block(self, parent, mode: str, wrap: int = 600):
        """渲染数据驱动结局卡片：结局文案 + 图鉴进度 + 挑战结算 + 传承结果。

        调用 core.runtime.finish_run 一次完成：结局匹配、档案写入、
        挑战判定、传家宝传承掷骰。任何子系统异常都静默降级，不阻断结算页。
        """
        try:
            from core import runtime
            res = runtime.finish_run(self.player, mode)
        except Exception:
            return
        if not res.get("ending_name"):
            return

        rar = res.get("ending_rarity", "common")
        cat = res.get("ending_category", "normal")
        accent = RARITY_COLORS.get(rar, COLORS["text"])

        # 结局卡片
        card = tk.Frame(parent, bg=COLORS["card_bg"], padx=18, pady=14,
                        highlightbackground=accent, highlightthickness=2)
        card.pack(fill=tk.X, pady=(14, 6))

        head = tk.Frame(card, bg=COLORS["card_bg"])
        head.pack(fill=tk.X)
        tk.Label(head, text=f"【{CATEGORY_LABEL.get(cat, '结局')}】",
                 font=("Microsoft YaHei", 11), fg=COLORS["text_dim"],
                 bg=COLORS["card_bg"]).pack(side=tk.LEFT)
        tk.Label(head, text=f"  {res['ending_name']}",
                 font=("Microsoft YaHei", 16, "bold"), fg=accent,
                 bg=COLORS["card_bg"]).pack(side=tk.LEFT)
        tk.Label(head, text=f"  [{RARITY_LABEL.get(rar, rar)}]",
                 font=("Microsoft YaHei", 10), fg=accent,
                 bg=COLORS["card_bg"]).pack(side=tk.LEFT)
        if res.get("is_new_ending"):
            tk.Label(head, text="  ★ NEW", font=("Microsoft YaHei", 11, "bold"),
                     fg=COLORS["gold"], bg=COLORS["card_bg"]).pack(side=tk.LEFT)

        if res.get("ending_text"):
            tk.Label(card, text=res["ending_text"], font=("Microsoft YaHei", 11),
                     fg=COLORS["text"], bg=COLORS["card_bg"], wraplength=wrap,
                     justify="left").pack(anchor="w", pady=(8, 0))

        # 副结局
        others = res.get("also_matched") or []
        if others:
            names = "、".join(getattr(o, "name", "?") for o in others)
            tk.Label(card, text=f"你同时也接近：{names}",
                     font=("Microsoft YaHei", 9), fg=COLORS["text_dim"],
                     bg=COLORS["card_bg"], wraplength=wrap,
                     justify="left").pack(anchor="w", pady=(6, 0))

        # 图鉴进度
        coll = res.get("collection") or {}
        if coll.get("total"):
            seen, total = coll.get("seen", 0), coll["total"]
            ratio = seen / total if total else 0
            bar = "█" * int(20 * ratio) + "░" * (20 - int(20 * ratio))
            tk.Label(card, text=f"结局图鉴  {bar}  {seen}/{total}",
                     font=("Consolas", 10), fg=COLORS["cyan"],
                     bg=COLORS["card_bg"]).pack(anchor="w", pady=(8, 0))

        # 挑战结算
        cr = res.get("challenge_result")
        if cr:
            c = cr.get("challenge") or {}
            won = cr.get("won")
            box = tk.Frame(parent, bg=COLORS["bg_light"], padx=14, pady=10)
            box.pack(fill=tk.X, pady=4)
            tk.Label(box,
                     text=("🏆 挑战达成：" if won else "✗ 挑战未达成：") + c.get("name", "?"),
                     font=("Microsoft YaHei", 12, "bold"),
                     fg=COLORS["green"] if won else COLORS["red"],
                     bg=COLORS["bg_light"]).pack(anchor="w")
            if won:
                reward = cr.get("reward") or {}
                rparts = []
                if reward.get("unlock_talent"):
                    rparts.append(f"天赋 {reward['unlock_talent']}")
                if reward.get("unlock_mode"):
                    rparts.append(f"模式 {reward['unlock_mode']}")
                if reward.get("unlock_achievement"):
                    rparts.append(f"成就 {reward['unlock_achievement']}")
                if rparts:
                    tk.Label(box, text="解锁：" + "、".join(rparts),
                             font=("Microsoft YaHei", 10), fg=COLORS["gold"],
                             bg=COLORS["bg_light"]).pack(anchor="w", pady=(4, 0))
            else:
                for r in (cr.get("reasons_unmet") or [])[:3]:
                    tk.Label(box, text=f"  未满足：{r}", font=("Microsoft YaHei", 10),
                             fg=COLORS["text_dim"], bg=COLORS["bg_light"],
                             wraplength=wrap, justify="left").pack(anchor="w")

        # 传承结果
        inh = res.get("inheritance")
        if inh and (inh.get("kept") or inh.get("lost_names")):
            box = tk.Frame(parent, bg=COLORS["bg_light"], padx=14, pady=10)
            box.pack(fill=tk.X, pady=4)
            tk.Label(box, text="🏺 家族传承", font=("Microsoft YaHei", 12, "bold"),
                     fg=COLORS["purple"], bg=COLORS["bg_light"]).pack(anchor="w")
            if inh.get("kept"):
                tk.Label(box, text=f"  传给下一代：{len(inh['kept'])} 件",
                         font=("Microsoft YaHei", 10), fg=COLORS["green"],
                         bg=COLORS["bg_light"]).pack(anchor="w")
            if inh.get("lost_names"):
                tk.Label(box, text=f"  失落：{'、'.join(inh['lost_names'])}",
                         font=("Microsoft YaHei", 10), fg=COLORS["red"],
                         bg=COLORS["bg_light"], wraplength=wrap,
                         justify="left").pack(anchor="w")

    # ══════════════════════════════════════
    #  连胜提示浮层
    # ══════════════════════════════════════
    def _show_streak_toast(self):
        """右下角无边框浮层显示连胜状态，3 秒后淡出。失败静默跳过。"""
        try:
            from core import runtime
            res = runtime.session_start()
        except Exception:
            return
        if not res.get("ok") or not res.get("streak"):
            return

        streak = res.get("streak", 0)
        best = res.get("best", 0)
        milestone = res.get("milestone")

        try:
            toast = tk.Toplevel(self)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.attributes("-alpha", 0.0)
            toast.configure(bg=COLORS["gold"])
        except Exception:
            return

        inner = tk.Frame(toast, bg=COLORS["bg_mid"], padx=18, pady=12)
        inner.pack(padx=2, pady=2)

        flame = "🔥" * min(streak, 5)
        tk.Label(inner, text=f"{flame}  连胜 {streak} 天",
                 font=("Microsoft YaHei", 14, "bold"), fg=COLORS["gold"],
                 bg=COLORS["bg_mid"]).pack(anchor="w")
        tk.Label(inner, text=f"历史最佳 {best} 天", font=("Microsoft YaHei", 9),
                 fg=COLORS["text_dim"], bg=COLORS["bg_mid"]).pack(anchor="w")

        if milestone:
            buff = (milestone.get("reward") or {}).get("next_run_buff") or {}
            if buff:
                parts = "、".join(f"{k}+{v}" for k, v in buff.items())
                tk.Label(inner, text=f"🎁 里程碑：下一局 {parts}",
                         font=("Microsoft YaHei", 10), fg=COLORS["green"],
                         bg=COLORS["bg_mid"], wraplength=260,
                         justify="left").pack(anchor="w", pady=(6, 0))
        else:
            nxt = res.get("next_milestone")
            if nxt and nxt > streak:
                tk.Label(inner, text=f"再连 {nxt - streak} 天解锁里程碑",
                         font=("Microsoft YaHei", 9), fg=COLORS["cyan"],
                         bg=COLORS["bg_mid"]).pack(anchor="w", pady=(6, 0))

        # 定位到主窗口右下角
        self.update_idletasks()
        toast.update_idletasks()
        try:
            tw, th = toast.winfo_reqwidth(), toast.winfo_reqheight()
            x = self.winfo_rootx() + self.winfo_width() - tw - 24
            y = self.winfo_rooty() + self.winfo_height() - th - 24
            toast.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        toast.bind("<Button-1>", lambda e: toast.destroy())
        self._fade_toast(toast, 0.0, +0.1, hold_ms=3000)

    def _fade_toast(self, win, alpha: float, step: float, hold_ms: int = 3000):
        """浮层淡入 → 停留 → 淡出。用 after() 驱动，不阻塞主循环。"""
        if not win.winfo_exists():
            return
        alpha = round(alpha + step, 2)
        try:
            win.attributes("-alpha", max(0.0, min(1.0, alpha)))
        except Exception:
            return
        if step > 0 and alpha >= 1.0:
            win.after(hold_ms, lambda: self._fade_toast(win, 1.0, -0.08, 0))
        elif step < 0 and alpha <= 0.0:
            try:
                win.destroy()
            except Exception:
                pass
        else:
            win.after(30, lambda: self._fade_toast(win, alpha, step, hold_ms))

    # ══════════════════════════════════════
    #  挑战模式入口
    # ══════════════════════════════════════
    def show_challenge_menu(self):
        self.clear_screen()
        try:
            from core import challenges, runtime
        except Exception:
            messagebox.showerror("错误", "挑战系统不可用。")
            self.show_main_menu()
            return

        prof = runtime.get_profile()
        items = challenges.all_challenges()
        summ = challenges.challenge_summary(prof.data)
        completed = set(summ.get("completed_ids") or [])
        active_id = summ.get("active_id")

        self.make_title_bar(
            self.main_frame, "🎯 挑战模式",
            f"已完成 {summ.get('completed', 0)}/{summ.get('total', 0)}"
            + (f"　·　当前激活：{(challenges.get_challenge(active_id) or {}).get('name', '')}"
               if active_id else "")
        )

        wrapper = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        wrapper.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(wrapper, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scroll = tk.Frame(canvas, bg=COLORS["bg_dark"])
        scroll.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll, anchor="nw", width=900)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        inner = tk.Frame(scroll, bg=COLORS["bg_dark"], padx=24, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        for c in items:
            cid = c.get("id", "")
            is_done = cid in completed
            is_active = cid == active_id
            border = (COLORS["green"] if is_done else
                      COLORS["gold"] if is_active else COLORS["bg_light"])

            card = tk.Frame(inner, bg=COLORS["card_bg"], padx=16, pady=12,
                            highlightbackground=border, highlightthickness=2)
            card.pack(fill=tk.X, pady=6)

            head = tk.Frame(card, bg=COLORS["card_bg"])
            head.pack(fill=tk.X)
            badge = "✔ 已完成" if is_done else ("▶ 进行中" if is_active else "")
            tk.Label(head, text=c.get("name", "?"), font=("Microsoft YaHei", 14, "bold"),
                     fg=COLORS["text"], bg=COLORS["card_bg"]).pack(side=tk.LEFT)
            diff = c.get("difficulty", "")
            tk.Label(head, text=f"  [{DIFFICULTY_LABEL.get(diff, diff)}]",
                     font=("Microsoft YaHei", 10, "bold"),
                     fg=DIFFICULTY_COLORS.get(diff, COLORS["text_dim"]),
                     bg=COLORS["card_bg"]).pack(side=tk.LEFT)
            if badge:
                tk.Label(head, text=f"  {badge}", font=("Microsoft YaHei", 10),
                         fg=COLORS["green"] if is_done else COLORS["gold"],
                         bg=COLORS["card_bg"]).pack(side=tk.LEFT)

            tk.Label(card, text=c.get("description", ""), font=("Microsoft YaHei", 10),
                     fg=COLORS["text_dim"], bg=COLORS["card_bg"], wraplength=800,
                     justify="left").pack(anchor="w", pady=(4, 0))

            win = c.get("win_conditions") or {}
            if win:
                tk.Label(card, text="胜利条件：" + fmt_conditions(win),
                         font=("Microsoft YaHei", 10), fg=COLORS["cyan"],
                         bg=COLORS["card_bg"], wraplength=800,
                         justify="left").pack(anchor="w", pady=(4, 0))

            reward = c.get("reward") or {}
            rparts = []
            if reward.get("unlock_talent"):
                rparts.append(f"天赋 {reward['unlock_talent']}")
            if reward.get("unlock_mode"):
                rparts.append(f"模式 {reward['unlock_mode']}")
            if reward.get("unlock_achievement"):
                rparts.append(f"成就 {reward['unlock_achievement']}")
            if rparts:
                tk.Label(card, text="奖励：" + "、".join(rparts),
                         font=("Microsoft YaHei", 10), fg=COLORS["gold"],
                         bg=COLORS["card_bg"]).pack(anchor="w", pady=(4, 0))

            if c.get("flavor"):
                tk.Label(card, text=f"「{c['flavor']}」", font=("Microsoft YaHei", 10, "italic"),
                         fg=COLORS["highlight"], bg=COLORS["card_bg"], wraplength=800,
                         justify="left").pack(anchor="w", pady=(6, 0))

            btn_row = tk.Frame(card, bg=COLORS["card_bg"])
            btn_row.pack(anchor="e", pady=(8, 0))
            if is_active:
                tk.Button(btn_row, text="取消挑战", font=("Microsoft YaHei", 10),
                          bg=COLORS["red"], fg="white", bd=0, cursor="hand2",
                          width=12, command=self._abandon_challenge).pack(side=tk.RIGHT)
            else:
                tk.Button(btn_row, text="重玩" if is_done else "激活挑战",
                          font=("Microsoft YaHei", 10),
                          bg=COLORS["bg_light"] if is_done else COLORS["accent"],
                          fg="white", bd=0, cursor="hand2", width=12,
                          command=lambda i=cid: self._activate_challenge(i)).pack(side=tk.RIGHT)

        tk.Button(inner, text="返回主菜单", font=("Microsoft YaHei", 12),
                  bg=COLORS["bg_light"], fg=COLORS["text"], width=16, bd=0,
                  cursor="hand2", command=self.show_main_menu).pack(pady=20)

    def _activate_challenge(self, challenge_id: str):
        try:
            from core import challenges, runtime
            prof = runtime.get_profile()
            res = challenges.start_challenge(prof.data, challenge_id)
            runtime.save_profile()
        except Exception as ex:
            messagebox.showerror("错误", f"激活失败：{ex}")
            return
        if res.get("ok"):
            c = challenges.get_challenge(challenge_id) or {}
            ov = res.get("start_override") or {}
            msg = f"已激活挑战「{c.get('name','?')}」\n\n下一局新游戏时生效。"
            if ov:
                msg += f"\n\n开局强制调整：{fmt_override(ov)}"
            messagebox.showinfo("挑战已激活", msg)
        else:
            messagebox.showwarning("无法激活", res.get("message", "未知原因"))
        self.show_challenge_menu()

    def _abandon_challenge(self):
        try:
            from core import challenges, runtime
            prof = runtime.get_profile()
            challenges.abandon_challenge(prof.data)
            runtime.save_profile()
        except Exception:
            pass
        self.show_challenge_menu()

    # ══════════════════════════════════════
    #  家族传承图鉴
    # ══════════════════════════════════════
    def show_lineage_panel(self):
        self.clear_screen()
        try:
            from core import heirlooms, runtime
        except Exception:
            messagebox.showerror("错误", "传承系统不可用。")
            self.show_main_menu()
            return

        prof = runtime.get_profile()
        summary = heirlooms.lineage_summary(prof.data)
        held_ids = set(heirlooms.held_heirloom_ids(prof.data))
        all_items = heirlooms.all_heirlooms()

        self.make_title_bar(
            self.main_frame, "🏺 家族传承",
            f"第 {summary.get('generations', 0)} 代　·　"
            f"持有 {summary.get('heirloom_count', 0)}/{len(all_items)} 件"
        )

        wrapper = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        wrapper.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(wrapper, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scroll = tk.Frame(canvas, bg=COLORS["bg_dark"])
        scroll.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll, anchor="nw", width=900)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        grid = tk.Frame(scroll, bg=COLORS["bg_dark"], padx=24, pady=10)
        grid.pack(fill=tk.BOTH, expand=True)

        for idx, h in enumerate(all_items):
            hid = h.get("id", "")
            owned = hid in held_ids
            rar = h.get("rarity", "common")
            accent = RARITY_COLORS.get(rar, COLORS["text_dim"]) if owned else COLORS["bg_light"]

            card = tk.Frame(grid, bg=COLORS["card_bg"] if owned else COLORS["bg_mid"],
                            padx=16, pady=12, highlightbackground=accent,
                            highlightthickness=2)
            card.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=8, pady=8)
            grid.columnconfigure(idx % 2, weight=1)

            bgc = COLORS["card_bg"] if owned else COLORS["bg_mid"]

            if owned:
                head = tk.Frame(card, bg=bgc)
                head.pack(fill=tk.X)
                tk.Label(head, text=f"● {h.get('name','?')}",
                         font=("Microsoft YaHei", 13, "bold"), fg=accent,
                         bg=bgc).pack(side=tk.LEFT)
                tk.Label(head, text=f"  [{RARITY_LABEL.get(rar, rar)}]",
                         font=("Microsoft YaHei", 9), fg=accent,
                         bg=bgc).pack(side=tk.LEFT)

                try:
                    pct = int(float(h.get("inherit_chance", 0.5)) * 100)
                except (TypeError, ValueError):
                    pct = 50
                tk.Label(card, text=f"传承成功率 {pct}%", font=("Microsoft YaHei", 9),
                         fg=COLORS["cyan"], bg=bgc).pack(anchor="w", pady=(2, 0))
                tk.Label(card, text=h.get("description", ""), font=("Microsoft YaHei", 10),
                         fg=COLORS["text"], bg=bgc, wraplength=380,
                         justify="left").pack(anchor="w", pady=(6, 0))
                eff = h.get("effects") or {}
                if eff:
                    parts = [f"{k}{'+' if isinstance(v, (int, float)) and v >= 0 else ''}{v}"
                             for k, v in eff.items()]
                    tk.Label(card, text="效果：" + "、".join(parts),
                             font=("Microsoft YaHei", 10), fg=COLORS["green"],
                             bg=bgc, wraplength=380,
                             justify="left").pack(anchor="w", pady=(6, 0))
            else:
                tk.Label(card, text="○  ？？？", font=("Microsoft YaHei", 13, "bold"),
                         fg=COLORS["text_dim"], bg=bgc).pack(anchor="w")
                tk.Label(card, text=h.get("unlock_hint") or "尚未解锁",
                         font=("Microsoft YaHei", 10), fg=COLORS["text_dim"],
                         bg=bgc, wraplength=380,
                         justify="left").pack(anchor="w", pady=(8, 0))

        tk.Button(scroll, text="返回主菜单", font=("Microsoft YaHei", 12),
                  bg=COLORS["bg_light"], fg=COLORS["text"], width=16, bd=0,
                  cursor="hand2", command=self.show_main_menu).pack(pady=20)

    # ══════════════════════════════════════
    #  结局图鉴
    # ══════════════════════════════════════
    def show_ending_codex(self):
        self.clear_screen()
        try:
            from core import endings as E, runtime
        except Exception:
            messagebox.showerror("错误", "结局系统不可用。")
            self.show_main_menu()
            return

        prof = runtime.get_profile()
        coll = E.collection_summary(prof.data)
        seen = set(prof.data.get("seen_endings") or [])

        self.make_title_bar(self.main_frame, "📜 结局图鉴",
                            f"已解锁 {coll.get('seen', 0)}/{coll.get('total', 0)}")

        wrapper = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        wrapper.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(wrapper, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scroll = tk.Frame(canvas, bg=COLORS["bg_dark"])
        scroll.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll, anchor="nw", width=900)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        inner = tk.Frame(scroll, bg=COLORS["bg_dark"], padx=24, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        # 分类进度条
        prog_box = tk.Frame(inner, bg=COLORS["card_bg"], padx=16, pady=12)
        prog_box.pack(fill=tk.X, pady=(0, 12))
        for cat, prog in (coll.get("by_category") or {}).items():
            ratio = prog["seen"] / prog["total"] if prog["total"] else 0
            bar = "█" * int(24 * ratio) + "░" * (24 - int(24 * ratio))
            row = tk.Frame(prog_box, bg=COLORS["card_bg"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{CATEGORY_LABEL.get(cat, cat):<10s}",
                     font=("Microsoft YaHei", 10), fg=COLORS["text"],
                     bg=COLORS["card_bg"], width=10, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=bar, font=("Consolas", 10), fg=COLORS["cyan"],
                     bg=COLORS["card_bg"]).pack(side=tk.LEFT)
            tk.Label(row, text=f"  {prog['seen']}/{prog['total']}",
                     font=("Microsoft YaHei", 10), fg=COLORS["text_dim"],
                     bg=COLORS["card_bg"]).pack(side=tk.LEFT)

        # 结局清单
        cur_cat = None
        for e in sorted(E.all_endings(), key=lambda x: (x.category, -x.priority)):
            if e.category != cur_cat:
                cur_cat = e.category
                tk.Label(inner, text=f"【{CATEGORY_LABEL.get(cur_cat, cur_cat)}】",
                         font=("Microsoft YaHei", 13, "bold"), fg=COLORS["gold"],
                         bg=COLORS["bg_dark"]).pack(anchor="w", pady=(12, 4))

            unlocked = e.id in seen
            row = tk.Frame(inner, bg=COLORS["bg_dark"])
            row.pack(fill=tk.X, pady=1)
            if unlocked:
                color = RARITY_COLORS.get(e.rarity, COLORS["text"])
                tk.Label(row, text=f"  ●  {e.name}", font=("Microsoft YaHei", 11),
                         fg=color, bg=COLORS["bg_dark"]).pack(side=tk.LEFT)
                tk.Label(row, text=f"  [{RARITY_LABEL.get(e.rarity, e.rarity)}]",
                         font=("Microsoft YaHei", 9), fg=color,
                         bg=COLORS["bg_dark"]).pack(side=tk.LEFT)
            else:
                tk.Label(row, text="  ○  ？？？？？？", font=("Microsoft YaHei", 11),
                         fg=COLORS["text_dim"], bg=COLORS["bg_dark"]).pack(side=tk.LEFT)

        tk.Button(inner, text="返回主菜单", font=("Microsoft YaHei", 12),
                  bg=COLORS["bg_light"], fg=COLORS["text"], width=16, bd=0,
                  cursor="hand2", command=self.show_main_menu).pack(pady=24)

    # ══════════════════════════════════════
    #  存档系统
    # ══════════════════════════════════════
    def save_and_return(self):
        saves_dir = os.path.join(SCRIPT_DIR, "saves")
        os.makedirs(saves_dir, exist_ok=True)
        if self.player:
            save_name = f"save_{self.player.name}_{self.player.age}"
            save_file = os.path.join(saves_dir, f"{save_name}.json")
            data = self.player.to_dict()
            data['game_mode'] = self.game_mode
            save_json(save_file, data)
        self.show_main_menu()

    def load_game(self):
        saves_dir = os.path.join(SCRIPT_DIR, "saves")
        if not os.path.exists(saves_dir):
            messagebox.showinfo("提示", "没有找到保存文件。")
            return
        save_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
        if not save_files:
            messagebox.showinfo("提示", "没有找到保存文件。")
            return

        # 弹出选择窗口
        load_win = tk.Toplevel(self)
        load_win.title("加载游戏")
        load_win.geometry("400x400")
        load_win.configure(bg=COLORS["bg_dark"])
        load_win.transient(self)
        load_win.grab_set()

        tk.Label(load_win, text="选择存档", font=("Microsoft YaHei", 14, "bold"),
                 fg=COLORS["gold"], bg=COLORS["bg_dark"]).pack(pady=12)

        listbox = tk.Listbox(load_win, font=("Microsoft YaHei", 11),
                             bg=COLORS["card_bg"], fg=COLORS["text"],
                             selectbackground=COLORS["accent"], width=35, height=12)
        listbox.pack(padx=16, pady=8)

        for sf in save_files:
            listbox.insert(tk.END, sf[:-5])

        def do_load():
            sel = listbox.curselection()
            if not sel:
                return
            save_path = os.path.join(saves_dir, save_files[sel[0]])
            try:
                with open(save_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.player = Player.from_dict(data)
                self.game_mode = constants.normalize_mode(data.get('game_mode', 'traditional'))
                self.events_data = self.content.raw
                load_win.destroy()
                # 根据模式恢复（均已归一化为 canonical 值）
                if self.game_mode == "reigns":
                    self.player.init_decision_tree()
                    self.show_reigns_screen()
                elif self.game_mode == "cultivation":
                    self.cultivation_stage = 0
                    self.show_cultivation_event()
                else:  # traditional
                    self.adventure_stage = 0
                    self.show_adventure_event()
            except Exception as e:
                messagebox.showerror("错误", f"加载失败：{e}")

        tk.Button(load_win, text="加载", font=("Microsoft YaHei", 12),
                  bg=COLORS["accent"], fg="white", width=12, bd=0,
                  cursor="hand2", command=do_load).pack(pady=8)
        tk.Button(load_win, text="取消", font=("Microsoft YaHei", 12),
                  bg=COLORS["bg_light"], fg=COLORS["text"], width=12, bd=0,
                  cursor="hand2", command=load_win.destroy).pack(pady=4)


# ══════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════
if __name__ == "__main__":
    app = GameApp()
    app.mainloop()
