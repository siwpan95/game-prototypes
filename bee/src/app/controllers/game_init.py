# -*- coding: utf-8 -*-
"""
游戏初始化 Mixin — 角色创建界面（UI）

以 Mixin 方式注入 GameController。注意：世界生成 / 队友招募 / 重开等模拟逻辑
已迁入 src.sim_core.engine.SimCore（_init_game / _load_affix_pool / _restart_game）。
本文件仅保留纯 UI 的角色创建窗口。
"""

import random
import tkinter as tk

from src.app.models.character import Character, Race, CharClass, CharacterStats


class GameInitMixin:
    """初始化 Mixin — 角色创建界面"""

    def _show_character_creation(self):
        """角色创建界面"""
        win = tk.Toplevel(self.root)
        win.title("创建角色")
        win.geometry("420x520")
        win.configure(bg="#161b22")
        win.transient(self.root)
        win.grab_set()
        win.focus_set()

        result = [None, None, ""]

        frame = tk.Frame(win, bg="#161b22")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        tk.Label(frame, text="创建你的冒险者", font=("Consolas", 14, "bold"),
                 fg="#c9d1d9", bg="#161b22").pack(pady=(0, 10))

        # 名字输入
        tk.Label(frame, text="名字:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        name_entry = tk.Entry(frame, bg="#0d1117", fg="#c9d1d9",
                              insertbackground="#c9d1d9", relief=tk.FLAT)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        name_entry.insert(0, "冒险者")

        # 种族选择
        tk.Label(frame, text="种族:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        race_var = tk.StringVar(value=list(Race)[0].value[0])
        race_frame = tk.Frame(frame, bg="#161b22")
        race_frame.pack(fill=tk.X, pady=(0, 10))
        for r in Race:
            rb = tk.Radiobutton(race_frame, text=r.value[0], variable=race_var,
                                value=r.value[0], fg="#c9d1d9", bg="#161b22",
                                selectcolor="#21262d", activebackground="#161b22",
                                activeforeground="#c9d1d9")
            rb.pack(side=tk.LEFT, padx=3)

        # 职业选择
        tk.Label(frame, text="职业:", fg="#8b949e", bg="#161b22",
                 anchor="w").pack(fill=tk.X)
        class_var = tk.StringVar(value=list(CharClass)[0].value[0])
        class_frame = tk.Frame(frame, bg="#161b22")
        class_frame.pack(fill=tk.X, pady=(0, 10))
        for c in CharClass:
            rb = tk.Radiobutton(class_frame, text=c.value[0], variable=class_var,
                                value=c.value[0], fg="#c9d1d9", bg="#161b22",
                                selectcolor="#21262d", activebackground="#161b22",
                                activeforeground="#c9d1d9")
            rb.pack(side=tk.LEFT, padx=3)

        # 属性预览
        preview_label = tk.Label(frame, text="", fg="#58a6ff", bg="#161b22",
                                  justify=tk.LEFT, anchor="nw")
        preview_label.pack(fill=tk.BOTH, expand=True)

        def _find_race(name):
            return next(r for r in Race if r.value[0] == name)

        def _find_class(name):
            return next(c for c in CharClass if c.value[0] == name)

        def update_preview():
            try:
                race_obj = _find_race(race_var.get())
                cls_obj = _find_class(class_var.get())
                name = name_entry.get().strip() or "冒险者"
                stats = CharacterStats.generate_for_class_race(cls_obj, race_obj)
                preview_label.config(text=(
                    f"预览: {name} ({race_obj.value[0]} {cls_obj.value[0]})\n\n"
                    f"  力量: {stats.strength}  敏捷: {stats.dexterity}\n"
                    f"  体质: {stats.constitution}  智力: {stats.intelligence}\n"
                    f"  感知: {stats.wisdom}  魅力: {stats.charisma}\n\n"
                    f"  HP: {Character.calc_max_hp(stats.constitution, cls_obj.base_hp)}\n"
                    f"  基础攻击力: {cls_obj.base_attack}"
                ))
            except Exception:
                pass

        def on_confirm():
            try:
                race_obj = _find_race(race_var.get())
                cls_obj = _find_class(class_var.get())
                name = name_entry.get().strip() or "冒险者"
                result[0] = race_obj
                result[1] = cls_obj
                result[2] = name
                # D4 接线：让角色创建对话框生效 —— 用所选 race/class/name 启动新游戏
                seed = random.randint(1, 2 ** 31 - 1)
                self.sim._init_new_game(
                    race=race_obj, char_class=cls_obj, name=name, seed=seed,
                )
                win.destroy()
            except StopIteration:
                return

        def random_create():
            race_obj = random.choice(list(Race))
            cls_obj = random.choice(list(CharClass))
            race_var.set(race_obj.value[0])
            class_var.set(cls_obj.value[0])
            update_preview()

        # 绑定事件
        name_entry.bind("<KeyRelease>", lambda e: update_preview())
        race_var.trace_add("write", lambda *a: update_preview())
        class_var.trace_add("write", lambda *a: update_preview())

        # 按钮
        btn_frame = tk.Frame(frame, bg="#161b22")
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="随机", command=random_create,
                  bg="#21262d", fg="#c9d1d9", relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="确定", command=on_confirm,
                  bg="#238636", fg="white", relief=tk.FLAT).pack(side=tk.RIGHT, padx=2)

        update_preview()
        win.wait_window()
        return tuple(result)
