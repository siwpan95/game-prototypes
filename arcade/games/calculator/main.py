"""
main.py — 程序入口（MVVM Bootstrap）

职责：
  1. 创建 Model / ViewModel / View 并完成装配。
  2. 向 ViewModel 注册副作用处理器：
       quit         → sys.exit
       shuffle      → view.shuffle
       achievement  → 弹窗显示成就
  3. 启动 tkinter 主循环。

main.py 是唯一知道所有三层的地方。
"""

import sys
import tkinter as tk
from tkinter import messagebox

from model     import CalculatorModel
from viewmodel import CalculatorViewModel
from view      import CalculatorView, COLORS

# 成就 id → 中文显示名
ACHIEVEMENT_NAMES = {
    "first_blood":   "初窥门径",
    "golden_mean":   "黄金均值",
    "babel_tongue":  "巴别塔之舌",
    "transmutation": "点石成金",
    "stargazer":     "观星者",
    "hermetic":      "赫尔墨斯",
    "sieve_master":  "筛法大师",
    "cartographer":  "幻岛制图师",
    "final_key":     "终钥持有者",
    "completionist": "炼金术大师",
}

ACHIEVEMENT_DESC = {
    "first_blood":   "第一次进入 Alchemia 模式",
    "golden_mean":   "解开第 4 面 ABSCONDITA EST INSIGNE",
    "babel_tongue":  "解开第 5 面 LINGVA MATER",
    "transmutation": "解开第 6 面 CHYMISTRY",
    "stargazer":     "解开第 7 面 SVPER STELLAE",
    "hermetic":      "解开第 8 面 HISTORIA (As above, so below)",
    "sieve_master":  "解开第 9 面 NVMERO SANCTVM",
    "cartographer":  "解开第 10 面 MAPPVS MUNDI",
    "final_key":     "输入最终密钥 PADEILSYMIELGEDIELVSIEL",
    "completionist": "解开所有 7 页谜题并输入终钥",
}


def main():
    root = tk.Tk()
    root.title("Calculator  ∞  Alchemia 解密终端")
    root.resizable(False, False)
    root.configure(bg=COLORS["bg"])

    # ── 装配三层 ─────────────────────────────────────────────────
    model     = CalculatorModel()
    viewmodel = CalculatorViewModel(model)
    view      = CalculatorView(root, viewmodel)
    view.pack(padx=10, pady=10, fill="both", expand=True)

    # ── 注册副作用处理器 ─────────────────────────────────────────
    # quit: 销毁窗口并退出进程
    def on_quit():
        root.destroy()
        sys.exit(0)

    # shuffle: 通知 View 重排按钮
    def on_shuffle():
        view.shuffle()

    # achievement: 弹窗显示成就
    def on_achievement():
        ach_id = viewmodel.achievement.value
        if not ach_id:
            return
        name = ACHIEVEMENT_NAMES.get(ach_id, ach_id)
        desc = ACHIEVEMENT_DESC.get(ach_id, "")
        title = f"★ 成就解锁：{name} ★"
        msg = f"{desc}\n\n(成就 id: {ach_id})"
        # 异步弹窗，避免阻塞 notify 链
        root.after(10, lambda: messagebox.showinfo(title, msg))

    viewmodel.add_side_effect_handler("quit",         on_quit)
    viewmodel.add_side_effect_handler("shuffle",      on_shuffle)
    viewmodel.add_side_effect_handler("achievement",  on_achievement)

    # ── 居中窗口 ─────────────────────────────────────────────────
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    # ── 启动时 shuffle ───────────────────────────────────────────
    view.shuffle()

    root.mainloop()


if __name__ == "__main__":
    main()
