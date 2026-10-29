# -*- coding: utf-8 -*-
"""仓库标签页 Mixin — 背包/消耗品/装备管理"""

import tkinter as tk
from tkinter import ttk, messagebox

from core.config import (
    C_CONTENT_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT, C_SECTION_TITLE,
    C_ROW_EVEN, C_ROW_ODD, C_SEPARATOR,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT, C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_ACCENT_TEAL, C_ACCENT_RED,
    FONT_LABEL, FONT_SMALL, FONT_TINY,
    MAX_PARTY_SIZE,
)
from data.loader import get_loader


class WarehouseTabMixin:
    """仓库标签页：背包查看、消耗品、装备管理"""

    def _build_warehouse_tab(self):
        frame = tk.Frame(self.content_frame, bg=C_CONTENT_BG)
        self._tab_content["仓库"] = frame

        tk.Label(frame, text="📦 背包", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W, padx=16, pady=(12, 4))

        inv_container = tk.Frame(frame, bg=C_CONTENT_BG)
        inv_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 4))

        # 背包：可交互列表（带装备按钮）
        self._inv_list_frame = tk.Frame(inv_container, bg=C_ROW_EVEN)
        self._inv_list_frame.pack(fill=tk.BOTH, expand=True)

        # 旧 Text 组件保留作为 fallback（空背包时）
        self.inv_text = tk.Text(inv_container, font=FONT_SMALL, wrap=tk.WORD,
                                 bg=C_ROW_EVEN, fg=C_TEXT, relief=tk.FLAT,
                                 padx=10, pady=6, state=tk.DISABLED, height=5,
                                 borderwidth=1, highlightbackground=C_SEPARATOR)
        self.inv_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="🧪 消耗品（点击「使用」选择目标）", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W, padx=16, pady=(4, 2))

        self._consume_frame = tk.Frame(frame, bg=C_CONTENT_BG)
        self._consume_frame.pack(fill=tk.X, padx=16, pady=(2, 4))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=4)

        tk.Label(frame, text="⚙ 装备管理", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W, padx=16, pady=(4, 2))

        self._wh_char_frames = []
        equip_frame = tk.Frame(frame, bg=C_CONTENT_BG)
        equip_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 10))
        for i in range(MAX_PARTY_SIZE):
            cf = tk.Frame(equip_frame, bg=C_ROW_EVEN if i % 2 == 0 else C_ROW_ODD)
            cf.pack(fill=tk.X, pady=1)
            self._wh_char_frames.append(cf)

    def _refresh_warehouse(self):
        loader = get_loader()

        # ---- 背包区：可交互列表 ----
        for w in self._inv_list_frame.winfo_children():
            w.destroy()
        self.inv_text.pack_forget()  # 隐藏旧 Text

        if not self.engine.inventory:
            self.inv_text.pack(fill=tk.BOTH, expand=True)
            self.inv_text.configure(state=tk.NORMAL)
            self.inv_text.delete("1.0", tk.END)
            self.inv_text.insert(tk.END, "  (空)\n")
            self.inv_text.configure(state=tk.DISABLED)
        else:
            for item_name in self.engine.inventory:
                eq = loader.equipment.get(item_name)
                row_bg = C_ROW_EVEN if self.engine.inventory.index(item_name) % 2 == 0 else C_ROW_ODD
                row = tk.Frame(self._inv_list_frame, bg=row_bg)
                row.pack(fill=tk.X, pady=1)

                slot_emoji = {"weapon": "⚔", "armor": "🛡", "shield": "🔰", "accessory": "💍"}
                emoji = slot_emoji.get(eq.slot, "📦") if eq else "❓"
                info = f"{emoji} {item_name}"
                bonus = f"  —  {eq.bonus_text()}" if eq else ""
                slot_tag = f"  [{eq.slot}]" if eq else ""

                tk.Label(row, text=f"{info}{bonus}{slot_tag}", font=FONT_SMALL,
                         bg=row_bg, fg=C_TEXT).pack(side=tk.LEFT, padx=10, pady=3)

                if eq:
                    # 找出可以装备的角色（优先空槽位，其次可替换）
                    for ci, a in enumerate(self.engine.party):
                        if not a.is_alive():
                            continue
                        current_eq = a.equipment.get(eq.slot)
                        job = loader.jobs.get(a.job_key, None)
                        if not current_eq:
                            # 空槽位 → 直接装备
                            btn_text = f"→{a.name}"
                            btn_bg = C_BTN_PRIMARY
                            btn_hover = "#238B7E"
                        else:
                            # 已有装备 → 替换
                            btn_text = f"换{a.name}"
                            btn_bg = C_ACCENT_TEAL
                            btn_hover = "#238B7E"
                        equip_btn = tk.Label(row, text=btn_text,
                                              font=FONT_TINY,
                                              bg=btn_bg, fg=C_BTN_PRIMARY_TEXT,
                                              padx=5, cursor="hand2", relief=tk.FLAT)
                        equip_btn.pack(side=tk.RIGHT, padx=1, pady=3)
                        equip_btn.bind("<Button-1>",
                            lambda e, idx=ci, it=item_name: self._do_equip(idx, it))
                        self._bind_hover(equip_btn, btn_bg, btn_hover)

        # 消耗品区（带使用按钮）
        for w in self._consume_frame.winfo_children():
            w.destroy()
        if self.engine.consumables:
            for name, qty in sorted(self.engine.consumables.items()):
                c = loader.consumables.get(name)
                row = tk.Frame(self._consume_frame, bg=C_CONTENT_BG)
                row.pack(fill=tk.X, pady=1)
                info = f"  {c.emoji} {name} x{qty}  —  {c.desc}" if c else f"  {name} x{qty}"
                tk.Label(row, text=info, font=FONT_SMALL, bg=C_CONTENT_BG,
                         fg=C_TEXT).pack(side=tk.LEFT)
                use_btn = tk.Label(row, text="使用", font=FONT_TINY,
                                    bg=C_ACCENT_TEAL, fg="white",
                                    padx=8, pady=2, cursor="hand2", relief=tk.FLAT)
                use_btn.pack(side=tk.RIGHT, padx=(4, 8))
                use_btn.bind("<Button-1>",
                    lambda e, n=name, ct=c.item_type if c else "heal": self._do_use_consumable(n, ct))
                self._bind_hover(use_btn, C_ACCENT_TEAL, "#238B7E")
        else:
            tk.Label(self._consume_frame, text="  (空)", font=FONT_SMALL,
                     bg=C_CONTENT_BG, fg=C_TEXT_HINT).pack(anchor=tk.W, pady=2)

        for i, f in enumerate(self._wh_char_frames):
            for w in f.winfo_children():
                w.destroy()
            if i >= len(self.engine.party):
                continue

            a = self.engine.party[i]
            job = loader.jobs.get(a.job_key)
            row_bg = C_ROW_EVEN if i % 2 == 0 else C_ROW_ODD
            f.configure(bg=row_bg)

            header = tk.Frame(f, bg=row_bg)
            header.pack(fill=tk.X, padx=8, pady=(4, 2))
            tk.Label(header, text=f"{job.emoji if job else '?'} {a.name}",
                     font=FONT_SMALL, bg=row_bg,
                     fg=job.color if job else C_TEXT).pack(side=tk.LEFT)

            for slot, slot_label in [("weapon", "武器"), ("armor", "防具"), ("shield", "盾牌"), ("accessory", "饰品")]:
                slot_row = tk.Frame(f, bg=row_bg)
                slot_row.pack(fill=tk.X, padx=16, pady=1)
                eq_name = a.equipment.get(slot)
                if eq_name:
                    tk.Label(slot_row, text=f"{slot_label}: {eq_name}",
                             font=FONT_TINY, bg=row_bg, fg=C_TEXT).pack(side=tk.LEFT)
                    unequip_btn = tk.Label(slot_row, text="卸下", font=FONT_TINY,
                                            bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
                                            padx=6, cursor="hand2", relief=tk.FLAT)
                    unequip_btn.pack(side=tk.RIGHT, padx=(4, 2))
                    unequip_btn.bind("<Button-1>",
                        lambda e, idx=i, s=slot: self._do_unequip(idx, s))
                    self._bind_hover(unequip_btn, C_BTN_DANGER, "#D65A3F")
                else:
                    tk.Label(slot_row, text=f"{slot_label}: (空)", font=FONT_TINY,
                             bg=row_bg, fg=C_TEXT_HINT).pack(side=tk.LEFT)
                    for inv_item in self.engine.inventory:
                        eq = loader.equipment.get(inv_item)
                        if eq and eq.slot == slot:
                            equip_btn = tk.Label(slot_row, text=f"装备 {inv_item}",
                                                  font=FONT_TINY,
                                                  bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                                                  padx=6, cursor="hand2", relief=tk.FLAT)
                            equip_btn.pack(side=tk.RIGHT, padx=2)
                            equip_btn.bind("<Button-1>",
                                lambda e, idx=i, it=inv_item: self._do_equip(idx, it))
                            self._bind_hover(equip_btn, C_BTN_PRIMARY, "#238B7E")
                            break

    def _do_use_consumable(self, name, item_type):
        """使用消耗品。需要目标（heal/mp_restore/revive）时弹出角色选择"""
        # buff / cleanse 不需要目标
        no_target_types = {"buff", "cleanse"}
        if item_type in no_target_types:
            success, msg = self.engine.use_consumable(name)
            if success:
                self._set_narrative(msg)
                self._log(f"🧪 {msg}")
            else:
                messagebox.showwarning("提示", msg)
            self._refresh_warehouse()
            self._refresh_all()
            return

        # 需要选目标：弹出简易角色选择
        alive = [(i, a) for i, a in enumerate(self.engine.party) if a.is_alive()]
        # revive 可选中阵亡角色
        if item_type == "revive":
            all_chars = [(i, a) for i, a in enumerate(self.engine.party)]
        else:
            all_chars = alive

        if not all_chars:
            messagebox.showwarning("提示", "没有可用的目标角色！")
            return

        # 创建简易弹出窗口
        popup = tk.Toplevel(self.content_frame)
        popup.title(f"使用 {name} — 选择目标")
        popup.geometry("240x200")
        popup.configure(bg=C_CONTENT_BG)
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        # 居中
        popup.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - 240) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - 200) // 2
        popup.geometry(f"+{x}+{y}")

        tk.Label(popup, text=f"选择使用 {name} 的目标：",
                 font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT).pack(pady=(12, 8))

        for idx, a in all_chars:
            job = get_loader().jobs.get(a.job_key)
            tag = ""
            if a.dead or a.hp <= 0:
                tag = "💀"
            elif not a.is_alive():
                tag = ""
            label_text = f"  {job.emoji if job else '?'} {a.name}  {tag}"
            btn = tk.Label(popup, text=label_text, font=FONT_SMALL,
                           bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                           padx=12, pady=4, cursor="hand2", relief=tk.FLAT)
            btn.pack(fill=tk.X, padx=20, pady=3)
            btn.bind("<Button-1>", lambda e, i=idx, p=popup: self._apply_consumable(name, i, p))
            self._bind_hover(btn, C_BTN_PRIMARY, "#238B7E")

    def _apply_consumable(self, name, target_idx, popup):
        popup.destroy()
        success, msg = self.engine.use_consumable(name, target_idx)
        if success:
            self._set_narrative(msg)
            self._log(f"🧪 {msg}")
        else:
            messagebox.showwarning("提示", msg)
        self._refresh_warehouse()
        self._refresh_all()

    def _do_equip(self, char_idx, item_name):
        if self.engine.equip(char_idx, item_name):
            self._set_narrative(f"装备了 {item_name}！")
            self._refresh_warehouse()
            self._refresh_all()

    def _do_unequip(self, char_idx, slot):
        if self.engine.unequip(char_idx, slot):
            self._refresh_warehouse()
            self._refresh_all()
