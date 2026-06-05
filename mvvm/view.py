"""
MVVM — View 层（Tkinter UI）
View 绑定 ViewModel 命令和属性变更通知，不直接操作 Model。
功能：装备栏交互 | 技能按钮 | 商人弹窗 | 装备详情/卸下 | 词缀显示
"""

import json
import tkinter as tk
from tkinter import font, messagebox
from typing import Any, Dict, List, Optional

from .viewmodel import GameViewModel
from common.fonts import cn_font


class GameView:
    """Tkinter 主界面"""

    def __init__(self, root: tk.Tk, vm: GameViewModel,
                 task_view: Optional[Any] = None,
                 on_skill_use: Optional[callable] = None) -> None:
        self.root = root
        self.vm: GameViewModel = vm
        self.task_view = task_view
        self.on_skill_use = on_skill_use  # (skill_id, target_idx) -> None
        self.monster_btns: List[tk.Button] = []
        self.skill_btns: Dict[str, tk.Button] = {}
        self._selected_target: Optional[int] = None
        self._seen_events: set = set()  # 防重复弹窗

        f = cn_font(12)

        # ── 状态栏 ──────────────────────────────
        status_frame = tk.Frame(root)
        status_frame.pack(anchor="w", padx=10, pady=5, fill="x")

        self.status = tk.Label(status_frame, font=f, justify="left")
        self.status.pack(side="left")

        # ── 顶部操作区 ────────────────────────────
        top_frame = tk.Frame(root)
        top_frame.pack(pady=3)

        rest_cost = self.vm.get_player_state().get("rest_cost", 5)
        self.rest_btn = tk.Button(
            top_frame,
            text=f"💤 休息恢复  (-{rest_cost} 池经验)",
            font=cn_font(10),
            command=self.vm.cmd_rest,
        )
        self.rest_btn.pack(side="left", padx=5)

        # 装备按钮 — 装备管理入口
        self.equip_btn = tk.Button(
            top_frame,
            text="⚔ 装备",
            font=cn_font(10),
            command=self._show_equip_popup,
        )
        self.equip_btn.pack(side="left", padx=5)

        # 背包按钮 — 仓库换装
        self.pack_btn = tk.Button(
            top_frame,
            text="📦 背包",
            font=cn_font(10),
            command=self._show_backpack_popup,
        )
        self.pack_btn.pack(side="left", padx=5)

        # ── 怪物按钮区 ────────────────────────────
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=5)

        for i in range(len(self.vm.get_monster_states())):
            self._create_monster_btn(i)

        # ── 技能按钮区 ────────────────────────────
        self.skill_frame = tk.LabelFrame(root, text="⚡ 技能",
                                         font=cn_font(11))
        self.skill_frame.pack(fill="x", padx=10, pady=3)
        self.skill_btn_container = tk.Frame(self.skill_frame)
        self.skill_btn_container.pack(pady=3)
        self._render_skill_buttons()

        # ── 日志框 ──────────────────────────────
        self.log_box = tk.Text(root, height=8, state="disabled", font=f)
        self.log_box.pack(fill="both", expand=True, padx=10)

        # ── 订阅 ViewModel ────────────────────
        self.vm.subscribe("player_state", self._update_status)
        self.vm.subscribe("monster_states", self._update_monsters)
        self.vm.subscribe("log", self._update_log)
        self.vm.subscribe("skills", self._render_skill_buttons)

        self._update_status()
        self._update_monsters()
        self._update_log()
        self._start_tick()

    # ── 怪物按钮 ──────────────────────────────────

    def _create_monster_btn(self, idx: int) -> tk.Button:
        btn = tk.Button(
            self.btn_frame,
            font=cn_font(11),
            command=lambda i=idx: self._on_attack(i),
        )
        btn.pack(pady=2, fill="x", padx=10)
        # 右键显示词缀详情
        btn.bind("<Button-3>", lambda e, i=idx: self._show_affix_tooltip(i))
        self.monster_btns.append(btn)
        return btn

    def _on_attack(self, idx: int) -> None:
        if self._selected_target is not None:
            for sk_id, _ in self.skill_btns.items():
                pass
        self.vm.cmd_attack(idx)

    # ── 技能按钮 ──────────────────────────────────

    def _render_skill_buttons(self) -> None:
        """渲染/刷新技能按钮"""
        for child in self.skill_btn_container.winfo_children():
            child.destroy()
        self.skill_btns.clear()

        from skills.skill_components import SkillSlotComponent
        from skills.skill_defs import SKILL_DEFS
        from ecs.components import ExpComponent, EquipmentComponent
        world = self.vm._model.world
        player_eid = self.vm._model.player_eid

        slot = world.get_component(player_eid, SkillSlotComponent)
        exp_c = world.get_component(player_eid, ExpComponent)
        eq_c = world.get_component(player_eid, EquipmentComponent)
        if slot is None:
            # 技能系统未初始化，显示提示
            lbl = tk.Label(self.skill_btn_container,
                           text="(技能系统未加载)", font=cn_font(9), fg="gray")
            lbl.pack(pady=2)
            return
        if exp_c is None:
            return

        row = tk.Frame(self.skill_btn_container)
        row.pack(pady=2)

        for i, sk_id in enumerate(slot.skill_ids):
            def_ = SKILL_DEFS.get(sk_id)
            if def_ is None:
                continue
            cd = slot.cooldowns.get(sk_id, 0)
            cd_reduced = cd
            if eq_c:
                cd_bonus = int(eq_c.total_bonus("cd_reduction"))
                cd_reduced = max(1, cd + cd_bonus)
            ready = cd <= 0
            cost = def_.get("cost_exp_pool", 0)
            can_afford = exp_c.exp_pool >= cost
            text = f"{def_['name']}"
            if not ready:
                text += f" CD:{cd}s"
            elif cost > 0:
                text += f" -{cost}"
            fg_color = "green" if (ready and can_afford) else "gray"

            btn = tk.Button(
                row,
                text=text,
                font=cn_font(9),
                fg=fg_color,
                command=lambda sid=sk_id: self._on_skill(sid),
            )
            if not ready:
                btn.config(state="disabled")
            btn.pack(side="left", padx=3)
            self.skill_btns[sk_id] = btn

    def _on_skill(self, skill_id: str) -> None:
        """使用技能，弹窗选择目标"""
        states = self.vm.get_monster_states()
        alive_targets = [(i, ms) for i, ms in enumerate(states) if ms["alive"]]
        if not alive_targets:
            return

        if self.on_skill_use:
            self.on_skill_use(skill_id, alive_targets[0][0])

    # ── UI 刷新 ──────────────────────────────────

    def _update_status(self) -> None:
        s = self.vm.get_player_state()
        if not s:
            return
        txt = (
            f"👤 Lv.{s['level']}  "
            f"ATK:{s['atk']}  "
            f"HP:{s['hp']}/{s['max_hp']}  "
            f"EXP:{s['exp']}/{s['exp_threshold']}  "
            f"池:{s['exp_pool']}  "
            f"暴击:{int(s['crit_chance']*100)}%  "
            f"闪避:{int(s['dodge_chance']*100)}%"
        )
        self.status.config(text=txt)
        # 装备按钮：显示已装备数量
        eq_list = s.get("equipment", [])
        count = len(eq_list)
        self.equip_btn.config(text=f"⚔ 装备 ({count}/4)")

    def _update_monsters(self) -> None:
        states = self.vm.get_monster_states()
        # 确保按钮数量足够
        while len(self.monster_btns) < len(states):
            self._create_monster_btn(len(self.monster_btns))
        while len(self.monster_btns) > len(states):
            self.monster_btns.pop().destroy()

        for btn, ms in zip(self.monster_btns, states):
            if ms["alive"]:
                boss_tag = "👑 " if ms.get("is_boss") else ""
                btn.config(
                    text=f"{boss_tag}{ms['name']}  HP {ms['hp']}/{ms['max_hp']}  |  EXP +{ms['exp_reward']}",
                    fg="red",
                    state="normal",
                )
            else:
                btn.config(
                    text=f"{ms['name']}  复活中… {ms['respawn_timer']}s",
                    fg="gray",
                    state="disabled",
                )

    def _update_log(self) -> None:
        raw_text = self.vm.get_log_text()
        lines = raw_text.split("\n")
        display_lines: list[str] = []

        for line in lines:
            if line.startswith("__EVENT__"):
                # 解析事件 JSON，触发弹窗
                json_str = line[len("__EVENT__"):]
                event_hash = hash(json_str)
                if event_hash not in self._seen_events:
                    self._seen_events.add(event_hash)
                    try:
                        data = json.loads(json_str)
                        if data.get("event") == "merchant":
                            equip = data.get("equip", {})
                            self.root.after(100, lambda e=equip: self._show_merchant_popup(e))
                    except json.JSONDecodeError:
                        pass
                # __EVENT__ 不显示在日志中
            else:
                display_lines.append(line)

        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("end", "\n".join(display_lines) + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ── 商人弹窗 ──────────────────────────────────

    def _show_merchant_popup(self, equip: dict) -> None:
        """神秘商人弹窗：展示装备，玩家可选择购买或放弃"""
        price = equip.get("price", 10)
        win = tk.Toplevel(self.root)
        win.title("🧙 神秘商人")
        win.geometry("360x240")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        # 居中
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 360) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 240) // 2
        win.geometry(f"+{x}+{y}")

        tk.Label(win, text="🧙 神秘商人掏出了一件物品…",
                 font=cn_font(13)).pack(pady=10)

        icon = equip.get("icon", "?")
        name = equip.get("name", "???")
        desc = equip.get("desc", "")
        bonuses = equip.get("bonuses", {})

        # 装备详情
        detail = f"{icon} {name}\n{desc}"
        if bonuses:
            bonus_texts = []
            for k, v in bonuses.items():
                if k == "atk_base":
                    bonus_texts.append(f"ATK +{int(v)}")
                elif k == "crit_chance":
                    bonus_texts.append(f"暴击 +{int(v*100)}%")
                elif k == "dodge_chance":
                    bonus_texts.append(f"闪避 +{int(v*100)}%")
                elif k == "max_hp":
                    bonus_texts.append(f"HP上限 +{int(v)}")
                elif k == "lifesteal":
                    bonus_texts.append(f"吸血 +{int(v*100)}%")
                elif k == "exp_bonus":
                    bonus_texts.append(f"EXP +{int(v*100)}%")
                elif k == "cd_reduction":
                    bonus_texts.append(f"冷却 -{abs(int(v))}s")
            if bonus_texts:
                detail += "\n" + " | ".join(bonus_texts)
        tk.Label(win, text=detail, font=cn_font(11),
                 justify="left", wraplength=320).pack(pady=5)

        # 价格和按钮
        exp_pool = self.vm.get_player_state().get("exp_pool", 0)
        can_afford = exp_pool >= price
        price_color = "green" if can_afford else "red"
        tk.Label(win, text=f"💰 价格：{price} 经验池（你当前：{exp_pool}）",
                 font=cn_font(10), fg=price_color).pack(pady=5)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)

        def _buy() -> None:
            ok = self.vm.cmd_buy_equipment(equip)
            if ok:
                win.destroy()
            else:
                messagebox.showwarning("购买失败", "经验池不足或背包已满！", parent=win)

        tk.Button(btn_frame, text=f"💰 购买 (-{price})", font=cn_font(11),
                  bg="goldenrod", fg="black",
                  command=_buy,
                  state="normal" if can_afford else "disabled").pack(side="left", padx=10)

        tk.Button(btn_frame, text="🚫 放弃", font=cn_font(11),
                  bg="gray", fg="white",
                  command=win.destroy).pack(side="left", padx=10)

    # ── 装备详情弹窗 ─────────────────────────────

    def _show_equip_popup(self) -> None:
        """点击装备栏：展示已装备物品，支持卸下"""
        equipped = self.vm.get_equipped()
        if not equipped:
            messagebox.showinfo("装备栏", "当前没有装备任何物品。\n\n击杀怪物有 35% 概率掉落装备！", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("🎒 装备管理")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="🎒 已装备物品（点击卸下）",
                 font=cn_font(12)).pack(pady=8)

        content = tk.Frame(win)
        content.pack(padx=15, pady=5, fill="both", expand=True)

        for i, eq in enumerate(equipped):
            row = tk.Frame(content)
            row.pack(fill="x", pady=3)

            bonuses = eq.get("bonuses", {})
            bonus_strs = []
            if bonuses.get("atk_base"):
                bonus_strs.append(f"ATK+{int(bonuses['atk_base'])}")
            if bonuses.get("crit_chance"):
                bonus_strs.append(f"暴击+{int(bonuses['crit_chance']*100)}%")
            if bonuses.get("dodge_chance"):
                bonus_strs.append(f"闪避+{int(bonuses['dodge_chance']*100)}%")
            if bonuses.get("max_hp"):
                bonus_strs.append(f"HP+{int(bonuses['max_hp'])}")
            if bonuses.get("lifesteal"):
                bonus_strs.append(f"吸血+{int(bonuses['lifesteal']*100)}%")
            bonus_text = " | ".join(bonus_strs) if bonus_strs else eq.get("desc", "")

            label_text = f"  {eq['icon']} {eq['name']} — {bonus_text}"
            tk.Label(row, text=label_text, font=cn_font(10),
                     anchor="w", fg="darkorange").pack(side="left")

            tk.Button(row, text="🗑 卸下", font=cn_font(9),
                      bg="#d55", fg="white",
                      command=lambda idx=i: self._do_unequip(idx, win)).pack(side="right", padx=5)

        # 底部
        tk.Label(win, text=f"装备槽：{len(equipped)}/4", font=cn_font(9),
                 fg="gray").pack(pady=5)

        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        win.geometry(f"+{x}+{y}")

    def _do_unequip(self, idx: int, win: tk.Toplevel) -> None:
        """卸下装备并刷新弹窗"""
        self.vm.cmd_unequip(idx)
        win.destroy()
        self.root.after(50, self._show_equip_popup)

    # ── 背包弹窗（自由换装）──────────────────────

    @staticmethod
    def _format_bonus(eq: dict) -> str:
        """格式化装备加成文本"""
        bonuses = eq.get("bonuses", {})
        parts = []
        if bonuses.get("atk_base"):
            parts.append(f"ATK+{int(bonuses['atk_base'])}")
        if bonuses.get("crit_chance"):
            parts.append(f"暴击+{int(bonuses['crit_chance']*100)}%")
        if bonuses.get("dodge_chance"):
            parts.append(f"闪避+{int(bonuses['dodge_chance']*100)}%")
        if bonuses.get("max_hp"):
            parts.append(f"HP+{int(bonuses['max_hp'])}")
        if bonuses.get("lifesteal"):
            parts.append(f"吸血+{int(bonuses['lifesteal']*100)}%")
        if bonuses.get("exp_bonus"):
            parts.append(f"EXP+{int(bonuses['exp_bonus']*100)}%")
        if bonuses.get("cd_reduction"):
            parts.append(f"CD-{abs(int(bonuses['cd_reduction']))}s")
        return " | ".join(parts) if parts else eq.get("desc", "")

    def _show_backpack_popup(self) -> None:
        """背包弹窗：装备栏 + 背包仓库，自由拖动换装"""
        win = tk.Toplevel(self.root)
        win.title("📦 背包")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        equipped = self.vm.get_equipped()
        backpack = self.vm.get_backpack()

        # ── 装备栏区域 ────────────────────────
        eq_frame = tk.LabelFrame(win, text="⚔ 装备栏（身上）", font=cn_font(11))
        eq_frame.pack(fill="x", padx=10, pady=(8, 3))

        if equipped:
            for i, eq in enumerate(equipped):
                row = tk.Frame(eq_frame)
                row.pack(fill="x", pady=2, padx=5)
                bonus_text = self._format_bonus(eq)
                tk.Label(row, text=f"  {eq['icon']} {eq['name']}",
                         font=cn_font(10), anchor="w", fg="darkorange").pack(side="left")
                tk.Label(row, text=f"  {bonus_text}",
                         font=cn_font(9), anchor="w", fg="#555").pack(side="left")
                tk.Button(row, text="卸下→背包", font=cn_font(9),
                          bg="#d55", fg="white",
                          command=lambda idx=i: self._bp_unequip(idx, win)).pack(
                          side="right", padx=3)
        else:
            tk.Label(eq_frame, text="  (空)", font=cn_font(9), fg="#aaa").pack(
                anchor="w", padx=5, pady=3)

        # 显示空槽位
        empty = 4 - len(equipped)
        if empty > 0:
            tk.Label(eq_frame, text=f"  空槽位 ×{empty}",
                     font=cn_font(9), fg="#aaa").pack(anchor="w", padx=5)

        # ── 背包仓库区域 ──────────────────────
        bp_label = f"🎒 背包仓库（{len(backpack)}/12）"
        bp_frame = tk.LabelFrame(win, text=bp_label, font=cn_font(11))
        bp_frame.pack(fill="x", padx=10, pady=3)

        if backpack:
            slots_full = len(equipped) >= 4
            for i, item in enumerate(backpack):
                row = tk.Frame(bp_frame)
                row.pack(fill="x", pady=2, padx=5)
                bonus_text = self._format_bonus(item)
                tk.Label(row, text=f"  {item['icon']} {item['name']}",
                         font=cn_font(10), anchor="w", fg="#4a90d9").pack(side="left")
                tk.Label(row, text=f"  {bonus_text}",
                         font=cn_font(9), anchor="w", fg="#555").pack(side="left")

                if slots_full:
                    # 装备栏满了 → "替换"按钮
                    tk.Button(row, text="替换", font=cn_font(9),
                              bg="#4a90d9", fg="white",
                              command=lambda idx=i: self._bp_swap_ask(idx, win)).pack(
                              side="right", padx=3)
                else:
                    # 有空位 → "装备"按钮
                    tk.Button(row, text="装备", font=cn_font(9),
                              bg="#3a8", fg="white",
                              command=lambda idx=i: self._bp_equip(idx, win)).pack(
                              side="right", padx=3)
        else:
            tk.Label(bp_frame, text="  背包空空如也", font=cn_font(9),
                     fg="#aaa").pack(anchor="w", padx=5, pady=5)

        x = self.root.winfo_x() + (self.root.winfo_width() - 420) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        win.geometry(f"+{x}+{y}")

    def _bp_unequip(self, equip_idx: int, win: tk.Toplevel) -> None:
        """卸下装备 → 背包"""
        ok = self.vm.cmd_move_equip_to_backpack(equip_idx)
        if ok:
            win.destroy()
            self.root.after(50, self._show_backpack_popup)
        else:
            messagebox.showwarning("操作失败", "背包已满，无法卸下装备！", parent=win)

    def _bp_equip(self, bp_idx: int, win: tk.Toplevel) -> None:
        """从背包装备到身上"""
        ok = self.vm.cmd_equip_from_backpack(bp_idx)
        if ok:
            win.destroy()
            self.root.after(50, self._show_backpack_popup)
        else:
            messagebox.showwarning("操作失败", "装备失败！", parent=win)

    def _bp_swap_ask(self, bp_idx: int, win: tk.Toplevel) -> None:
        """装备栏满了，弹窗询问替换哪一件"""
        equipped = self.vm.get_equipped()
        if not equipped:
            return

        sub = tk.Toplevel(win)
        sub.title("🔄 替换哪件装备？")
        sub.resizable(False, False)
        sub.transient(win)
        sub.grab_set()

        tk.Label(sub, text="选择要换下来的装备：", font=cn_font(11)).pack(pady=8)

        for i, eq in enumerate(equipped):
            btn_frame = tk.Frame(sub)
            btn_frame.pack(fill="x", padx=15, pady=2)
            bonus_text = self._format_bonus(eq)
            tk.Label(btn_frame, text=f"{eq['icon']} {eq['name']}  —  {bonus_text}",
                     font=cn_font(10), anchor="w", fg="darkorange").pack(side="left")
            tk.Button(btn_frame, text="换下这件", font=cn_font(9),
                      bg="#c90", fg="white",
                      command=lambda eq_i=i: self._bp_do_swap(eq_i, bp_idx, sub, win)
                      ).pack(side="right")

        x = win.winfo_x() + (win.winfo_width() - 350) // 2
        y = win.winfo_y() + (win.winfo_height() - 150) // 2
        sub.geometry(f"+{x}+{y}")

    def _bp_do_swap(self, equip_idx: int, bp_idx: int,
                     sub: tk.Toplevel, win: tk.Toplevel) -> None:
        """执行装备 ↔ 背包互换"""
        ok = self.vm.cmd_swap_equip_from_backpack(equip_idx, bp_idx)
        sub.destroy()
        win.destroy()
        self.root.after(50, self._show_backpack_popup)

    # ── 词缀提示 ──────────────────────────────────

    def _show_affix_tooltip(self, idx: int) -> None:
        """右键怪物按钮：显示词缀详情"""
        states = self.vm.get_monster_states()
        if idx >= len(states):
            return
        ms = states[idx]
        name = ms.get("name", "???")
        if not ms.get("alive"):
            return

        # 从 ECS world 获取词缀
        from ecs.components import MonsterComponent
        world = self.vm._model.world
        all_ids = (self.vm._model.monster_eids +
                   ([self.vm._model.boss_eid] if self.vm._model.boss_eid else []))
        if idx >= len(all_ids):
            return
        mon_c = world.get_component(all_ids[idx], MonsterComponent)
        affix_id = mon_c.affix if mon_c else None
        if affix_id is None:
            messagebox.showinfo("词缀", f"「{name}」\n无特殊词缀", parent=self.root)
            return

        from ecs.monster_affixes import get_affix_data
        af = get_affix_data(affix_id)
        if af is None:
            return

        lines = [f"怪物：{name}", f"词缀：{af['icon']}{af['label']}"]
        if af.get("hp_mult", 1.0) != 1.0:
            lines.append(f"HP倍率：×{af['hp_mult']}")
        if af.get("exp_mult", 1.0) != 1.0:
            lines.append(f"EXP倍率：×{af['exp_mult']}")
        if af.get("dodge_bonus", 0) > 0:
            lines.append(f"闪避：+{int(af['dodge_bonus']*100)}%")
        if af.get("damage_reduction", 0) > 0:
            lines.append(f"减伤：{af['damage_reduction']}")
        if af.get("on_attack"):
            lines.append(f"效果：攻击附带{af['on_attack']}")

        messagebox.showinfo(f"词缀 — {af['icon']}{af['label']}",
                            "\n".join(lines), parent=self.root)

    # ── 定时器 ──────────────────────────────────

    def _start_tick(self) -> None:
        self.vm.tick(1.0)
        self.root.after(1000, self._start_tick)
