# -*- coding: utf-8 -*-
"""郊外标签页 Mixin — 冒险设置 + 探索流程 + 楼层间决策（从 app.py 拆分）"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import random

from core.config import (
    WIN_W, C_CONTENT_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT, C_GOLD,
    C_ACCENT_TEAL, C_ACCENT_RED, C_ACCENT_GREEN, C_ROW_EVEN, C_SEPARATOR,
    C_SECTION_TITLE, C_TIMESTAMP,
    C_BTN_NORMAL, C_BTN_HOVER, C_BTN_TEXT, C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT,
    FONT_LABEL, FONT_SMALL, FONT_TINY, FONT_LOG,
    BATTLE_DELAY_MS, EQUIP_DROP_CHANCE,
)
from core.battle import BattleSystem
from core.models import Monster, Dungeon
from data.loader import get_loader


class WildernessTabMixin:
    """郊外标签页：冒险设置、探索流程、楼层间决策

    依赖宿主类 (ExplorationApp) 提供:
    - self.engine, self.root, self.content_frame, self._tab_content
    - self._after_ids, self._floor_choice_visible
    - self._log(), self._set_narrative(), self._switch_tab()
    - self._refresh_all(), self._bind_hover()
    - self._disable_widget(), self._enable_widget()
    """

    # ================================================================
    #  标签页 UI 构建
    # ================================================================
    def _build_outskirts_tab(self):
        frame = tk.Frame(self.content_frame, bg=C_CONTENT_BG)
        self._tab_content["郊外"] = frame

        # 冒险设置区
        setup_frame = tk.Frame(frame, bg=C_CONTENT_BG)
        setup_frame.pack(fill=tk.X, padx=16, pady=(12, 6))

        tk.Label(setup_frame, text="冒险设置", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W)

        ctrl_row = tk.Frame(setup_frame, bg=C_CONTENT_BG)
        ctrl_row.pack(fill=tk.X, pady=(6, 2))

        tk.Label(ctrl_row, text="目的地:", font=FONT_SMALL,
                 bg=C_CONTENT_BG, fg=C_TEXT).pack(side=tk.LEFT, padx=(0, 4))

        self.dungeon_var = tk.StringVar()
        self.dungeon_combo = ttk.Combobox(ctrl_row, textvariable=self.dungeon_var,
                                           state="readonly", font=FONT_SMALL, width=22)
        self.dungeon_combo.pack(side=tk.LEFT, padx=(0, 12))

        self.floor_progress_var = tk.StringVar(value="")
        tk.Label(ctrl_row, textvariable=self.floor_progress_var, font=FONT_SMALL,
                 bg=C_CONTENT_BG, fg=C_ACCENT_TEAL).pack(side=tk.LEFT)

        btn_row = tk.Frame(setup_frame, bg=C_CONTENT_BG)
        btn_row.pack(fill=tk.X, pady=(6, 2))

        # 速度控制按钮
        speed_frame = tk.Frame(btn_row, bg=C_CONTENT_BG)
        speed_frame.pack(side=tk.RIGHT)

        self._speed_btns = {}
        for label, mult in [("1×", 1.0), ("2×", 2.0), ("5×", 5.0)]:
            b = tk.Label(speed_frame, text=label, font=("Consolas", 9, "bold"),
                         bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
                         padx=6, pady=2, cursor="hand2", relief=tk.FLAT)
            b.pack(side=tk.LEFT, padx=(2, 0))
            b.bind("<Button-1>", lambda e, m=mult: self._set_game_speed(m))
            self._bind_hover(b, C_BTN_NORMAL, C_BTN_HOVER)
            self._speed_btns[mult] = b

        self.explore_btn = tk.Label(btn_row, text="  前往冒险  ",
                                     font=("Microsoft YaHei", 12, "bold"),
                                     bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                                     padx=24, pady=8, cursor="hand2", relief=tk.FLAT)
        self.explore_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.explore_btn.bind("<Button-1>", lambda e: self._start_explore())
        self._bind_hover(self.explore_btn, C_BTN_PRIMARY, "#238B7E")

        # 楼层间决策区
        self.floor_choice_frame = tk.Frame(setup_frame, bg=C_CONTENT_BG)

        self.continue_btn = tk.Label(self.floor_choice_frame, text="  继续探索下一层  ",
                                      font=("Microsoft YaHei", 11, "bold"),
                                      bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                                      padx=16, pady=6, cursor="hand2", relief=tk.FLAT)
        self.continue_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.continue_btn.bind("<Button-1>", lambda e: self._continue_explore())
        self._bind_hover(self.continue_btn, C_BTN_PRIMARY, "#238B7E")

        self.retreat_btn = tk.Label(self.floor_choice_frame, text="  撤退回城  ",
                                     font=("Microsoft YaHei", 11, "bold"),
                                     bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
                                     padx=16, pady=6, cursor="hand2", relief=tk.FLAT)
        self.retreat_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.retreat_btn.bind("<Button-1>", lambda e: self._return_to_town())
        self._bind_hover(self.retreat_btn, C_BTN_DANGER, "#D65A3F")

        self.camp_btn = tk.Label(self.floor_choice_frame, text="  扎营休整  ",
                                  font=("Microsoft YaHei", 11, "bold"),
                                  bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
                                  padx=16, pady=6, cursor="hand2", relief=tk.FLAT)
        self.camp_btn.pack(side=tk.LEFT)
        self.camp_btn.bind("<Button-1>", lambda e: self._do_camp())
        self._bind_hover(self.camp_btn, C_BTN_NORMAL, C_BTN_HOVER)

        self.floor_choice_label = tk.Label(self.floor_choice_frame,
                                            text="", font=FONT_SMALL,
                                            bg=C_CONTENT_BG, fg=C_TEXT_LIGHT)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=4)

        # 冒险日志区
        log_header = tk.Frame(frame, bg=C_CONTENT_BG)
        log_header.pack(fill=tk.X, padx=16, pady=(4, 2))
        tk.Label(log_header, text="冒险日志", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(side=tk.LEFT)

        self.clear_log_btn = tk.Label(log_header, text="清空", font=FONT_TINY,
                                       bg=C_CONTENT_BG, fg=C_TEXT_HINT, cursor="hand2")
        self.clear_log_btn.pack(side=tk.RIGHT)
        self.clear_log_btn.bind("<Button-1>", lambda e: self._clear_log())

        log_container = tk.Frame(frame, bg=C_CONTENT_BG)
        log_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 10))

        self.log_text = tk.Text(log_container, font=FONT_LOG, wrap=tk.WORD,
                                 bg=C_ROW_EVEN, fg=C_TEXT, relief=tk.FLAT,
                                 padx=10, pady=8, state=tk.DISABLED,
                                 borderwidth=1, highlightbackground=C_SEPARATOR)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_container, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 日志标签
        for tag, color, extra in [
            ("timestamp", C_TIMESTAMP, {}),
            ("battle_win", C_ACCENT_GREEN, {"font": ("Consolas", 10, "bold")}),
            ("battle_lose", C_ACCENT_RED, {}),
            ("item", C_GOLD, {}),
            ("levelup", "#7B2D8E", {"font": ("Consolas", 10, "bold")}),
            ("boss", C_ACCENT_RED, {"font": ("Consolas", 11, "bold")}),
            ("header", C_SECTION_TITLE, {"font": ("Consolas", 10, "bold")}),
            ("event", "#7B2D8E", {}),
            ("floor_info", C_ACCENT_TEAL, {}),
        ]:
            self.log_text.tag_configure(tag, foreground=color, **extra)

    # ================================================================
    #  游戏速度控制 (Tick 驱动相关)
    # ================================================================
    def _set_game_speed(self, multiplier: float):
        """设置游戏速度倍率"""
        if hasattr(self, 'game_loop') and self.game_loop:
            self.game_loop.set_speed(multiplier)
        # 更新按钮样式
        for m, btn in self._speed_btns.items():
            if m == multiplier:
                btn.configure(bg=C_ACCENT_TEAL, fg="white")
            else:
                btn.configure(bg=C_BTN_NORMAL, fg=C_BTN_TEXT)
        self._set_narrative(f"⚡ 游戏速度: {multiplier:.0f}×")

    # ================================================================
    #  日志工具
    # ================================================================
    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ================================================================
    #  楼层间决策 UI
    # ================================================================
    def _show_floor_choice(self, text: str = ""):
        if not self._floor_choice_visible:
            self.floor_choice_frame.pack(fill=tk.X, pady=(6, 2))
            self._floor_choice_visible = True
        if text:
            self.floor_choice_label.pack(anchor=tk.W, pady=(0, 4))
            self.floor_choice_label.configure(text=text)
        else:
            self.floor_choice_label.pack_forget()

    def _hide_floor_choice(self):
        if self._floor_choice_visible:
            self.floor_choice_frame.pack_forget()
            self._floor_choice_visible = False

    # ================================================================
    #  探索流程
    # ================================================================
    def _start_explore(self):
        if self.engine.exploring:
            return
        if not self.engine.party:
            messagebox.showwarning("提示", "请先去酒馆招募冒险者！")
            self._switch_tab("酒馆")
            return

        alive = [a for a in self.engine.party if a.is_alive()]
        if not alive:
            messagebox.showwarning("提示", "所有冒险者都已阵亡！请去旅店休息。")
            return

        idx = self.dungeon_combo.current()
        if idx < 0:
            messagebox.showwarning("提示", "请选择目的地！")
            return

        loader = get_loader()
        dungeons = loader.dungeons
        if idx >= len(dungeons):
            idx = 0
        dungeon = dungeons[idx]

        self.engine.current_dungeon = dungeon
        self.engine.current_floor = 1
        self.engine.exploring = True
        self.engine.between_floors = False
        self.engine.battle_log = []
        self.engine.clear_floor_buffs()

        self._switch_tab("郊外")
        self._hide_floor_choice()
        self._disable_widget(self.explore_btn)
        self.dungeon_combo.configure(state=tk.DISABLED)
        self.floor_progress_var.set(f"第 1/{dungeon.floors} 层")

        self._log(f"⚔ 队伍出发！目的地: {dungeon.name} (共 {dungeon.floors} 层)", "header")
        self._log(f"👥 队伍: {' · '.join(a.name for a in self.engine.party if a.is_alive())}",
                  "floor_info")
        self._set_narrative(f"队伍出发前往 {dungeon.name}，共 {dungeon.floors} 层……")

        self._enter_floor()

    def _return_to_town(self):
        self.engine.exploring = False
        self.engine.between_floors = False
        self.engine.clear_floor_buffs()

        # 使用 GameLoop 统一取消所有定时任务
        if hasattr(self, 'game_loop') and self.game_loop:
            self.game_loop.cancel_all()
        else:
            for aid in self._after_ids:
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
            self._after_ids.clear()

        self._enable_widget(self.explore_btn)
        self._hide_floor_choice()
        self.dungeon_combo.configure(state="readonly")
        self.floor_progress_var.set("")

        self._log("🏠 队伍返回城镇！", "header")
        if self.engine.current_dungeon:
            self._log(f"本次探索: {self.engine.current_dungeon.name} — "
                      f"到达第 {self.engine.current_floor - 1} 层")
        self._set_narrative("队伍返回了城镇，疲惫但活着。")

        self._refresh_all()

    def _enter_floor(self):
        if not self.engine.exploring:
            return

        engine = self.engine
        dungeon = engine.current_dungeon

        if engine.current_floor > dungeon.floors:
            self._log(f"🎉 地下城「{dungeon.name}」探索完成！", "header")
            engine.exploring = False
            engine.between_floors = False
            loader = get_loader()
            for ii, d in enumerate(loader.dungeons):
                if d.name == dungeon.name and ii + 1 < len(loader.dungeons):
                    engine.unlocked_dungeons = max(engine.unlocked_dungeons, ii + 2)
                    self._log(f"🔓 解锁新地下城: {loader.dungeons[ii + 1].name}！", "levelup")
            self._set_narrative(f"{dungeon.name} 探索完成！")
            self._return_to_town()
            return

        self.floor_progress_var.set(f"第 {engine.current_floor}/{dungeon.floors} 层")

        # 随机探索事件
        event_result = engine.trigger_event()
        if event_result:
            event, desc = event_result
            self._switch_tab("郊外")
            self._log(f"🔮 发现事件: {event.name}", "event")
            self._log(f"   {desc}", "event")
            self._set_narrative(f"发现事件: {event.name} — {desc}")
            self._show_event_choices(event)
            return

        # 刷怪战斗
        is_boss = engine.current_floor == dungeon.floors
        monster = self._spawn_monster(dungeon, is_boss)
        floor_type = "👑 BOSS" if is_boss else "⚔ 遭遇战"

        self._log(f"{floor_type} — 第 {engine.current_floor} 层: "
                  f"{monster.emoji} {monster.name} 出现了！",
                  "boss" if is_boss else None)
        self._set_narrative(f"第 {engine.current_floor} 层: {monster.name} 出现了！")
        engine.current_monster_emoji = monster.emoji
        engine.between_floors = False

        self._schedule_battle(monster, is_boss)

    def _schedule_battle(self, monster: Monster, is_boss: bool):
        """通过 GameLoop 或 root.after 安排战斗"""
        delay = BATTLE_DELAY_MS + random.randint(0, 400)
        if hasattr(self, 'game_loop') and self.game_loop:
            self.game_loop.after(delay, lambda m=monster, b=is_boss: self._do_battle(m, b))
        else:
            aid = self.root.after(delay,
                                  lambda m=monster, b=is_boss: self._do_battle(m, b))
            self._after_ids.append(aid)

    def _show_event_choices(self, event):
        self._hide_floor_choice()
        for w in self._tab_content["郊外"].winfo_children():
            if hasattr(w, '_event_chooser'):
                w.destroy()

        event_frame = tk.Frame(self._tab_content["郊外"], bg=C_CONTENT_BG)
        event_frame._event_chooser = True
        event_frame.pack(fill=tk.X, padx=16, pady=(4, 8),
                         before=self.log_text.master.winfo_children()[-1])

        tk.Label(event_frame, text=f"🔮 {event.name} — 做出你的选择:",
                 font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W)

        btn_row = tk.Frame(event_frame, bg=C_CONTENT_BG)
        btn_row.pack(fill=tk.X, pady=(4, 0))

        for i, choice in enumerate(event.choices):
            text = choice["text"]
            success_text = f"({int(choice.get('success_chance', 1.0) * 100)}%)"
            btn = tk.Label(btn_row, text=f"  {text} {success_text}  ",
                            font=FONT_SMALL, bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
                            padx=10, pady=4, cursor="hand2", relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=(0, 6))
            btn.bind("<Button-1>", lambda e, ev=event, ci=i: self._resolve_event(ev, ci))
            self._bind_hover(btn, C_BTN_NORMAL, C_BTN_HOVER)

    def _resolve_event(self, event, choice_idx):
        for w in self._tab_content["郊外"].winfo_children():
            if hasattr(w, '_event_chooser'):
                w.destroy()

        choice = event.choices[choice_idx]
        result = self.engine.resolve_event(event, choice_idx)
        self._log(f"  → {choice['text']}", "event")
        self._log(f"  {result}", "event")
        self._set_narrative(result)

        if all(not a.is_alive() for a in self.engine.party):
            self._log("💀 全队阵亡……冒险结束。", "battle_lose")
            self.engine.exploring = False
            self._return_to_town()
            return

        dungeon = self.engine.current_dungeon
        is_boss = self.engine.current_floor == dungeon.floors
        monster = self._spawn_monster(dungeon, is_boss)
        floor_type = "👑 BOSS" if is_boss else "⚔ 遭遇战"

        self._log(f"{floor_type} — 第 {self.engine.current_floor} 层: "
                  f"{monster.emoji} {monster.name} 出现了！",
                  "boss" if is_boss else None)
        self.engine.current_monster_emoji = monster.emoji

        self._schedule_battle(monster, is_boss)

    @staticmethod
    def _spawn_monster(dungeon: Dungeon, is_boss: bool) -> Monster:
        loader = get_loader()
        name = dungeon.boss_name if is_boss else random.choice(dungeon.monster_names)
        base = loader.monsters.get(name)
        if base is None:
            base = loader.monsters.get("史莱姆")
        scale = 1.0 + dungeon.difficulty * 0.3
        return base.copy_scaled(scale, dungeon.gold_mult, dungeon.exp_mult)

    def _do_battle(self, monster: Monster, is_boss: bool):
        if not self.engine.exploring:
            return

        victory, log, gold_earned, exp_earned = BattleSystem.run(
            self.engine.party, monster, self.engine.floor_buffs
        )

        if victory:
            self.engine.gold += gold_earned
            self.engine.total_monsters_killed += 1
            lvl_msgs = self.engine.grant_exp(exp_earned)
            log.extend(lvl_msgs)
            log.append(f"💰 获得 {gold_earned}G, {exp_earned} EXP")

            if random.random() < EQUIP_DROP_CHANCE:
                loader = get_loader()
                names = list(loader.equipment.keys())
                if names:
                    drop = random.choice(names)
                    self.engine.inventory.append(drop)
                    self.engine.total_treasures_found += 1
                    log.append(f"📦 发现宝物 [{drop}]！")

            if random.random() < 0.15:
                loader = get_loader()
                consume_names = list(loader.consumables.keys())
                if consume_names:
                    drop = random.choice(consume_names)
                    self.engine.add_consumable(drop)
                    log.append(f"🧪 发现 [{drop}]！")

            self.engine.clear_floor_buffs()

        for msg in log:
            tag = None
            if "升级" in msg:
                tag = "levelup"
            elif "击败" in msg or "被击败" in msg or "倒" in msg:
                tag = "battle_win"
            elif "获得" in msg:
                tag = "item"
            elif "阵亡" in msg:
                tag = "battle_lose"
            self._log(msg, tag)

        self._refresh_all()

        if not self.engine.exploring:
            return

        if victory:
            self.engine.current_floor += 1
            dungeon = self.engine.current_dungeon

            if self.engine.current_floor > dungeon.floors:
                self._enter_floor()
            else:
                self._log("")
                self._log(f"—— 到达第 {self.engine.current_floor} 层入口 ——", "floor_info")

                alive_count = sum(1 for a in self.engine.party if a.is_alive())
                injured = sum(1 for a in self.engine.party
                              if a.is_alive() and self.engine.hp_pct(a) < 0.5)
                status_text = f"队伍状态: {alive_count}人生还"
                if injured:
                    status_text += f", {injured}人重伤"

                self._set_narrative(
                    f"到达第 {self.engine.current_floor} 层 — {status_text}。继续探索还是撤退？"
                )
                self._show_floor_choice(status_text)
                self.engine.between_floors = True
        else:
            if all(not a.is_alive() for a in self.engine.party):
                self._log("💀 全队阵亡……冒险结束。", "battle_lose")
                self._set_narrative("全队阵亡……冒险者们的旅程在这里结束了。")
                self.engine.exploring = False
                self._return_to_town()
            else:
                self._log("队伍被击退……", "battle_lose")
                self._set_narrative("队伍被击退了，狼狈地逃回了城镇。")
                self.engine.exploring = False
                self._return_to_town()

    def _continue_explore(self):
        self._hide_floor_choice()
        self.engine.between_floors = False
        self._enter_floor()

    def _do_camp(self):
        if not self.engine.between_floors:
            return

        healed_count = 0
        for a in self.engine.party:
            if a.is_alive():
                heal_hp = int(self.engine._full_hp(a) * 0.2)
                heal_mp = int(a.max_mp * 0.15)
                a.hp = min(self.engine._full_hp(a), a.hp + heal_hp)
                a.mp = min(a.max_mp, a.mp + heal_mp)
                healed_count += 1

        self._log("🏕 队伍扎营休整，恢复部分 HP/MP", "header")
        if healed_count:
            self._log(f"   {healed_count}人获得了恢复", "floor_info")
        self._set_narrative("队伍扎营休整，在篝火旁恢复了些许体力。")

        self._hide_floor_choice()
        self.engine.between_floors = False
        self._enter_floor()
