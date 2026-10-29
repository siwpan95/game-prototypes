"""
入口模块 — 装配引擎与 UI，启动游戏循环
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, GAME_LOOP_MS, AUTOSAVE_SECONDS, SKILLS
from engine import GameEngine
from ui import GameUI


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("放置英雄")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_BG)

        self.engine = GameEngine()
        self.sound_on = False

        self.ui = GameUI(
            self.root,
            on_buy=self._on_buy,
            on_click=self._on_click,
            on_skill=self._on_skill,
            on_prestige=self._on_prestige_menu,
            on_hero=self._on_hero,
            on_achievements=self._on_achievements,
            on_daily=self._on_daily,
            on_daily_tasks=self._on_daily_tasks,
            on_hero_skill=self._on_hero_skill,
            on_golden_click=self._on_golden_click,
            on_stats=lambda: self.ui.show_stats(self.engine),
            on_save=lambda: self.ui.show_save_dialog(self.engine),
            on_toggle_sound=self._toggle_sound,
            on_import_done=self._full_draw,
        )
        self._full_draw()
        self._show_offline_modal()

        # P2：键盘快捷键（空格=点击，1-5=技能）
        self.root.bind("<space>", lambda e: self._on_click())
        for i, sk in enumerate(SKILLS):
            self.root.bind(str(i + 1), lambda e, k=sk["key"]: self._on_hotkey_skill(k))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._last_tick = time.time()
        self._last_autosave = time.time()
        self._game_loop()

    # ==================== 事件 ====================
    def _on_click(self, ev=None):
        ch = self.engine.get_active_challenge()
        if ch and ch.get("restrict_click"):
            return
        gain = self.engine.click()
        self.ui.spawn_float(f"+{gain}")
        self._beep(660, 40)

    def _on_buy(self, key):
        amt = 10 ** 9 if self.ui.buy_mode == "max" else self.ui.buy_mode
        bought, err = self.engine.buy_multiple(key, amt)
        if err:
            messagebox.showinfo("无法购买", err)
        elif bought:
            self._beep(880, 35)

    def _on_skill(self, key):
        err = self.engine.activate_skill(key)
        if err:
            messagebox.showinfo("技能", err)
        else:
            self._beep(990, 35)

    def _on_hotkey_skill(self, key):
        # 对话框/输入框聚焦时不触发，避免误触
        if any(isinstance(c, tk.Toplevel) for c in self.root.children.values()):
            return
        self._on_skill(key)

    def _on_hero(self, action, hero_key):
        if action == "upgrade":
            hstate = self.engine.get_hero_state(hero_key)
            if hstate["level"] <= 0:
                err = self.engine.unlock_hero(hero_key)
            else:
                err = self.engine.upgrade_hero(hero_key)
            if err:
                messagebox.showinfo("英雄", err)

    def _on_achievements(self):
        self.ui.show_achievements(self.engine)

    def _on_daily(self):
        self.ui.show_daily(self.engine)

    def _on_daily_tasks(self):
        self.ui.show_daily_tasks(self.engine)

    def _on_hero_skill(self, hero_key):
        err = self.engine.activate_hero_skill(hero_key)
        if err:
            messagebox.showinfo("英雄技能", err)

    def _on_golden_click(self):
        self.engine.golden_button_clicked()

    def _show_offline_modal(self):
        s = self.engine.get_offline_summary()
        if s["gold"] > 0 and s["seconds"] >= 60:
            h = int(s["seconds"] // 3600)
            m = int((s["seconds"] % 3600) // 60)
            dur = f"{h}小时{m}分" if h else f"{m}分"
            messagebox.showinfo(
                "欢迎回来",
                f"你离开了约 {dur}，挂机收益：\n"
                f"{self.ui._fmt_gold(s['gold'])} 金币"
            )

    def _on_prestige_menu(self):
        pts = self.engine.state.prestige_points
        f = self.engine.get_prestige_formula()
        choice = simpledialog.askstring("转生",
            f"声望: {pts} | 转生获 {f}\n\n1.转生  2.挑战  3.声望商店  4.装备英雄")
        if not choice:
            return
        if choice == "1":
            if self.ui.show_prestige_dialog(self.engine):
                err = self.engine.prestige()
                if err:
                    messagebox.showinfo("转生", err)
                else:
                    self._full_draw()
                    self._beep(330, 90)
                    messagebox.showinfo("转生", f"获得 {f} 声望")
        elif choice == "2":
            k = self.ui.show_challenge_dialog(self.engine)
            if k:
                err = self.engine.start_challenge(k)
                if err:
                    messagebox.showinfo("挑战", err)
                else:
                    self._full_draw()
        elif choice == "3":
            self.ui.show_prestige_shop(self.engine)
        elif choice == "4":
            self._equip_menu()

    def _equip_menu(self):
        eqs = self.engine.get_equipment()
        if not eqs:
            messagebox.showinfo("装备", "背包为空")
            return
        lines = [f"[{i+1}] {eq['name']} +{eq['bonus']} ({eq['rarity']})"
                 for i, eq in enumerate(eqs[-8:])]
        heroes = self.engine.get_heroes()
        hl = "\n".join(f"{j+1}. {h['name']} {self.engine.get_hero_state(h['key'])['level']}级"
                       for j, h in enumerate(heroes))
        r = simpledialog.askstring("装备英雄",
            "\n".join(lines) + "\n\n" + hl + "\n\n装备编号,英雄编号:")
        if r:
            parts = r.replace(" ", "").split(",")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ei, hi = int(parts[0]) - 1, int(parts[1]) - 1
                if 0 <= hi < len(heroes):
                    err = self.engine.equip_to_hero(ei, heroes[hi]["key"])
                    if err:
                        messagebox.showinfo("装备", err)

    # ==================== 绘制 ====================
    def _full_draw(self):
        self.ui.draw_hud(self.engine.state.gold, self.engine.state.dps)
        self.ui.draw_shop_buttons(self.engine)
        self.ui.update_era_bar(self.engine)
        self.ui.update_skill_buttons(self.engine)
        self.ui.update_hero_panel(self.engine)
        self.ui.update_hero_skill_buttons(self.engine)
        self.ui.update_golden_button(self.engine)
        self.ui.update_event_banner(self.engine)
        self.ui.update_equipment_bar(self.engine)

    def _game_loop(self):
        now = time.time()
        dt = now - self._last_tick
        self.engine.tick(now)

        self.ui.refresh_hud(self.engine.state.gold, self.engine.state.dps)
        self.ui.update_floaters(dt)
        self.ui.update_era_bar(self.engine)
        self.ui.update_skill_buttons(self.engine)
        self.ui.update_hero_panel(self.engine)
        self.ui.update_hero_skill_buttons(self.engine)
        self.ui.update_golden_button(self.engine)
        self.ui.update_event_banner(self.engine)
        self.ui.update_equipment_bar(self.engine)
        self.ui.update_golden_timer(
            self.engine.golden_buff_remaining,
            self.engine.golden_buff_active
        )
        self.ui.refresh_shop_if_needed(self.engine)
        self.ui.refresh_shop_buttons(self.engine)

        # 自动保存（每 AUTOSAVE_SECONDS 秒）
        if now - self._last_autosave >= AUTOSAVE_SECONDS:
            self.engine.save()
            self._last_autosave = now

        # 弹出新解锁的成就提示
        for name in self.engine.consume_pending_achievements():
            self.ui.show_achievement_toast(name)

        self._last_tick = now
        self.root.after(GAME_LOOP_MS, self._game_loop)

    def _on_close(self):
        self.engine.save()
        self.root.destroy()

    # ==================== 音效（P2，标准库 winsound，零依赖） ====================
    def _toggle_sound(self) -> bool:
        self.sound_on = not self.sound_on
        return self.sound_on

    def _beep(self, freq: int, dur: int = 50):
        if not self.sound_on:
            return
        try:
            import winsound
            winsound.Beep(freq, dur)
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
