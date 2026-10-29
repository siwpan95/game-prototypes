import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import random
import json
import os
import shutil
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    pd = None


# ====================================
# 全局默认参数
# ====================================
DEFAULT_GLOBAL = {
    "alpha_min": 0.03,
    "alpha_max": 0.35,
    "lam_n": 0.04,
    "gamma_c": 0.025,
    "reward_lam_n": 0.04,
    "reward_gamma_c": 0.02,
}


# ====================================
# 强化公式（有界增长，不会无限攀升）
# ====================================
def reinforcement_prob(n, c, g=None):
    """
    n: 总签到次数
    c: 连续签到天数
    g: 全局参数字典（可选，使用默认值）
    
    使用有界指数增长：
    - n 越大 → 趋近 1（新用户防护减弱）
    - c 越大 → 趋近 1（连续签到加成）
    - 概率上限 alpha_max，永远不超过
    """
    g = g or DEFAULT_GLOBAL
    a_min = g.get("alpha_min", 0.03)
    a_max = g.get("alpha_max", 0.35)
    lam = g.get("lam_n", 0.04)
    gam = g.get("gamma_c", 0.025)
    return a_min + (a_max - a_min) * (1 - math.exp(-lam * n)) * (1 - math.exp(-gam * c))


def choose_reward(n, c, rewards, g=None):
    """
    选择奖励（有界权重）
    每项奖励权重 = base * (1 - e^(-gamma * c)) * (1 - e^(-delta * n))
    gamma・delta 越大 → 越容易被连续签到和总次数激活
    """
    g = g or DEFAULT_GLOBAL
    r_lam = g.get("reward_lam_n", 0.04)
    r_gam = g.get("reward_gamma_c", 0.02)

    weights = []
    items = []
    for rw in rewards:
        name = rw["name"]
        base = rw["base"]
        gamma = rw.get("gamma", r_gam)
        delta = rw.get("delta", r_lam)
        # 有界增长：使用 1 - exp(-param * value) 替代线性 1 + param * value
        w = base * (1 - math.exp(-gamma * c)) * (1 - math.exp(-delta * n))
        weights.append(w)
        items.append(name)
    return random.choices(items, weights=weights, k=1)[0]


# ====================================
# 配置文件路径
# ====================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "rewards.json")
EXCEL_PATH = os.path.join(BASE_DIR, "rewards.xlsx")
HISTORY_PATH = os.path.join(BASE_DIR, "qiandao_history.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


# ====================================
# 奖励配置加载（Excel 优先，JSON 兜底）
# ====================================
def load_config():
    """加载完整配置（全局参数 + 奖励列表）"""
    g = dict(DEFAULT_GLOBAL)
    rewards = []

    # 尝试 Excel
    if pd is not None and os.path.exists(EXCEL_PATH):
        try:
            df = pd.read_excel(EXCEL_PATH)
            required = {"name", "base", "gamma", "delta"}
            if required.issubset(set(df.columns)):
                for _, row in df.iterrows():
                    rw = {
                        "name": str(row["name"]),
                        "base": float(row["base"]),
                        "gamma": float(row["gamma"]),
                        "delta": float(row["delta"]),
                        "category": str(row.get("category", "")),
                        "rarity": str(row.get("rarity", "普通")),
                        "description": str(row.get("description", "")),
                    }
                    rewards.append(rw)
                sync_config_to_json(g, rewards)
                return g, rewards
        except Exception:
            pass

    # 回退 JSON
    return load_config_from_json()


def load_config_from_json():
    """从 JSON 加载配置（兼容旧格式 dict 和新格式 list）"""
    g = dict(DEFAULT_GLOBAL)
    rewards = []
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # 新格式: {"global": {...}, "rewards": [...]}
        if "global" in data:
            g.update(data["global"])
        raw = data.get("rewards", [])
        if not raw:
            # 兼容旧格式: {"金币+10": {"base":1.0,...}}
            for name, p in data.items():
                if name == "global":
                    continue
                rewards.append({
                    "name": name,
                    "base": p["base"],
                    "gamma": p.get("gamma", g["reward_gamma_c"]),
                    "delta": p.get("delta", g["reward_lam_n"]),
                    "category": "",
                    "rarity": "普通",
                    "description": "",
                })
            return g, rewards
        # 新格式奖励列表
        for rw in raw:
            rewards.append({
                "name": rw["name"],
                "base": rw["base"],
                "gamma": rw.get("gamma", g["reward_gamma_c"]),
                "delta": rw.get("delta", g["reward_lam_n"]),
                "category": rw.get("category", ""),
                "rarity": rw.get("rarity", "普通"),
                "description": rw.get("description", ""),
            })
    elif isinstance(data, list):
        for rw in data:
            rewards.append({
                "name": rw["name"],
                "base": rw["base"],
                "gamma": rw.get("gamma", g["reward_gamma_c"]),
                "delta": rw.get("delta", g["reward_lam_n"]),
                "category": rw.get("category", ""),
                "rarity": rw.get("rarity", "普通"),
                "description": rw.get("description", ""),
            })

    return g, rewards


def sync_config_to_json(g, rewards):
    """将当前配置同步回 JSON"""
    data = {
        "global": g,
        "rewards": rewards,
    }
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_rewards_to_excel(rewards, path):
    if pd is None:
        raise RuntimeError("pandas 未安装，无法操作 Excel")
    rows = []
    for rw in rewards:
        rows.append({
            "name": rw["name"],
            "category": rw.get("category", ""),
            "rarity": rw.get("rarity", "普通"),
            "base": rw["base"],
            "gamma": rw["gamma"],
            "delta": rw["delta"],
            "description": rw.get("description", ""),
        })
    df = pd.DataFrame(rows, columns=["name", "category", "rarity", "base", "gamma", "delta", "description"])
    df.to_excel(path, index=False)


# ====================================
# 自动初始化
# ====================================
def init_files():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if pd is not None and not os.path.exists(EXCEL_PATH) and os.path.exists(JSON_PATH):
        try:
            _, rewards = load_config_from_json()
            save_rewards_to_excel(rewards, EXCEL_PATH)
            print(f"[init] 已从 rewards.json 生成 {EXCEL_PATH}")
        except Exception as e:
            print(f"[init] 生成 rewards.xlsx 失败: {e}")
    if not os.path.exists(HISTORY_PATH):
        save_history([])
        print(f"[init] 已创建 {HISTORY_PATH}")


# ====================================
# 历史记录管理
# ====================================
def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def backup_excel():
    if not os.path.exists(EXCEL_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"rewards_backup_{timestamp}.xlsx")
    shutil.copy2(EXCEL_PATH, backup_path)
    return backup_path


# ====================================
# Tkinter 应用
# ====================================
class SkinnerGame:
    def __init__(self, root):
        self.root = root
        self.root.title("斯金纳箱 · 强化公式版")
        self.root.geometry("820x640")
        self.root.minsize(720, 520)

        self.g, self.rewards = load_config()
        self.n = 0
        self.c = 0
        self.no_reward_streak = 0  # 连续无奖励次数
        self.last_sign = False
        self.history = load_history()

        self._build_ui()
        self._refresh_history_table()
        self.update_status()

    # ---------- UI ----------
    def _build_ui(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=(10, 0))

        self.canvas = tk.Canvas(top_frame, width=500, height=160, bg="#fafafa")
        self.canvas.pack(pady=5)

        self.text = self.canvas.create_text(
            250, 80,
            text="点击「签到」开始",
            font=("微软雅黑", 16),
            fill="#333"
        )

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)
        self.btn = ttk.Button(btn_frame, text="签 到", command=self.sign)
        self.btn.pack(side="left", padx=5)

        self.status = ttk.Label(self.root, font=("微软雅黑", 10))
        self.status.pack(pady=(0, 5))

        # -- 控制面板 --
        ctrl_frame = ttk.LabelFrame(self.root, text="Excel 管理")
        ctrl_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(ctrl_frame, text="导入 Excel", command=self.import_excel).pack(side="left", padx=5, pady=5)
        ttk.Button(ctrl_frame, text="生成模板", command=self.generate_template).pack(side="left", padx=5, pady=5)
        ttk.Button(ctrl_frame, text="备份 Excel", command=self.do_backup).pack(side="left", padx=5, pady=5)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10)

        # -- 历史记录 --
        hist_label = ttk.Label(self.root, text="签到历史", font=("微软雅黑", 11, "bold"))
        hist_label.pack(anchor="w", padx=10, pady=(5, 0))

        hist_ctrl = ttk.Frame(self.root)
        hist_ctrl.pack(fill="x", padx=10)
        ttk.Button(hist_ctrl, text="清空历史", command=self.clear_history).pack(side="right", padx=5, pady=(0, 5))

        columns = ("time", "nth", "streak_c", "prob", "result", "reward")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=10)
        self.tree.heading("time", text="时间")
        self.tree.heading("nth", text="第N次")
        self.tree.heading("streak_c", text="连续签到")
        self.tree.heading("prob", text="概率")
        self.tree.heading("result", text="结果")
        self.tree.heading("reward", text="奖励")

        self.tree.column("time", width=140)
        self.tree.column("nth", width=60, anchor="center")
        self.tree.column("streak_c", width=70, anchor="center")
        self.tree.column("prob", width=70, anchor="center")
        self.tree.column("result", width=100, anchor="center")
        self.tree.column("reward", width=200, anchor="w")

        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        scrollbar.pack(side="right", fill="y", pady=(0, 10), padx=(0, 10))

        # 绑定选中事件显示详情
        self.tree.bind("<<TreeviewSelect>>", self._on_history_select)
        self._detail_label = ttk.Label(self.root, text="", font=("微软雅黑", 9), foreground="#666")
        self._detail_label.pack(anchor="w", padx=10, pady=(0, 5))

    # ---------- 历史记录 ----------
    def _refresh_history_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for h in reversed(self.history):
            self.tree.insert("", "end", values=(
                h.get("time", ""),
                h.get("n", ""),
                h.get("streak_c", ""),
                h.get("prob", ""),
                h.get("result", ""),
                h.get("reward", ""),
            ))

    def _on_history_select(self, event):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], "values")
            self._detail_label.config(text=f"  详情: {vals[5] if len(vals) > 5 else ''}")
        else:
            self._detail_label.config(text="")

    def _add_history(self, p, reinforced, reward_name):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not reinforced:
            # 无奖励 → 检查上一条是否也是无奖励，是则叠加
            if self.history and not self.history[-1].get("reinforced", True):
                last = self.history[-1]
                last["n_end"] = self.n
                last["time"] = now
                last["prob"] = f"{p:.2%}"
                last["no_streak"] = last.get("no_streak", 1) + 1
                last["result"] = f"连续{last['no_streak']}次无奖励"
                last["reward"] = ""
            else:
                record = {
                    "time": now,
                    "n": self.n,
                    "n_end": self.n,
                    "streak_c": self.c,
                    "prob": f"{p:.2%}",
                    "result": "1次无奖励",
                    "reward": "",
                    "reinforced": False,
                    "no_streak": 1,
                }
                self.history.append(record)
        else:
            # 有奖励 → 正常新增
            record = {
                "time": now,
                "n": self.n,
                "n_end": self.n,
                "streak_c": self.c,
                "prob": f"{p:.2%}",
                "result": "获得奖励",
                "reward": reward_name,
                "reinforced": True,
                "no_streak": 0,
            }
            self.history.append(record)

        save_history(self.history)
        self._refresh_history_table()

    def clear_history(self):
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            self.history = []
            save_history(self.history)
            self._refresh_history_table()

    # ---------- 签到逻辑 ----------
    def sign(self):
        self.n += 1
        if not self.last_sign:
            self.c += 1
        self.last_sign = True

        p = reinforcement_prob(self.n, self.c, self.g)

        if random.random() < p:
            # 有奖励 → 重置无奖励计数器
            self.no_reward_streak = 0
            reward_name = choose_reward(self.n, self.c, self.rewards, self.g)
            rw_info = self._find_reward(reward_name)
            rarity_tag = ""
            if rw_info:
                rarity_tag = f" [{rw_info.get('rarity','')}]"
            result = f"（正强化 ✓）\n获得：{reward_name}{rarity_tag}"
            color = "#d32f2f"
            reinforced = True
        else:
            self.no_reward_streak += 1
            if self.no_reward_streak <= 1:
                result = "（未强化）\n本次无奖励"
            else:
                result = f"（未强化）\n连续 {self.no_reward_streak} 次无奖励"
            color = "#888"
            reinforced = False
            reward_name = None

        self.canvas.itemconfig(
            self.text,
            text=f"第 {self.n} 次签到  概率 {p:.1%}\n{result}",
            fill=color,
        )
        self._add_history(p, reinforced, reward_name)
        self.update_status()

    def _find_reward(self, name):
        for rw in self.rewards:
            if rw["name"] == name:
                return rw
        return None

    def update_status(self):
        p_now = reinforcement_prob(self.n, self.c, self.g)
        excel_ok = pd is not None and os.path.exists(EXCEL_PATH)
        src = "Excel" if excel_ok else "JSON"
        self.status.config(
            text=f"连续签到：{self.c} 天  |  强化概率：{p_now:.2%}  |  数据源：{src}"
        )

    # ---------- Excel 操作 ----------
    def import_excel(self):
        if pd is None:
            messagebox.showerror("错误", "未安装 pandas，请先执行: pip install pandas openpyxl")
            return
        filepath = filedialog.askopenfilename(
            title="选择奖励配置 Excel",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if not filepath:
            return
        try:
            df = pd.read_excel(filepath)
            required = {"name", "base", "gamma", "delta"}
            if not required.issubset(set(df.columns)):
                messagebox.showerror("格式错误", "Excel 必须包含列: name, base, gamma, delta\n可选列: category, rarity, description")
                return
            if os.path.exists(EXCEL_PATH):
                backup_excel()
            df.to_excel(EXCEL_PATH, index=False)
            self.g, self.rewards = load_config()
            self.update_status()
            messagebox.showinfo("成功", f"已导入 {len(self.rewards)} 个奖励配置")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def generate_template(self):
        if pd is None:
            messagebox.showerror("错误", "未安装 pandas，请先执行: pip install pandas openpyxl")
            return
        filepath = filedialog.asksaveasfilename(
            title="保存奖励配置模板",
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx")]
        )
        if not filepath:
            return
        try:
            _, rewards = load_config_from_json()
            save_rewards_to_excel(rewards, filepath)
            messagebox.showinfo("成功", f"模板已生成:\n{filepath}")
        except Exception as e:
            messagebox.showerror("生成失败", str(e))

    def do_backup(self):
        if not os.path.exists(EXCEL_PATH):
            messagebox.showwarning("无文件", "尚未创建 rewards.xlsx，请先导入或运行程序")
            return
        try:
            path = backup_excel()
            if path:
                messagebox.showinfo("备份完成", f"已备份到:\n{path}")
        except Exception as e:
            messagebox.showerror("备份失败", str(e))


if __name__ == "__main__":
    init_files()
    root = tk.Tk()
    SkinnerGame(root)
    root.mainloop()
