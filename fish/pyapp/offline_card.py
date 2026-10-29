"""离线结算卡片（P0-19，子任务 4.10）。

🔴 禁止 `from __future__ import annotations`（E6）。

准则约束（这张卡片是全程**唯一**一次主动弹出，务必克制）：

* **L5**：一键领取，**没有二次确认**，按钮点完即关。
* **L6**：文案只描述"你不在时一切都好"，零 guilt、零 FOMO、零催促。
* **L7**：离线收益为 0 时不显示 0，改走 `empty_states.offline_zero` 空状态文案。
* **L8**：不发系统通知、不发声、不抢焦点（`transient` 但不 `grab_set`）。
"""

import random
import tkinter as tk

from fishtank.economy import format_coins


class OfflineCard(object):
    """一次性的离线结算浮层（Toplevel）。"""

    def __init__(self, root, theme, text, bal):
        self.root = root
        self.theme = theme
        self.text = text
        self.bal = bal
        self.win = None
        self.shown = False

    def should_show(self, report):
        """是否值得弹这张卡。

        只有真的离开过（有内容）才弹；刚存过档、几秒内重启不打扰。
        """
        if report is None:
            return False
        try:
            return bool(report.has_content())
        except AttributeError:
            return False

    def show(self, report, on_claim=None):
        """弹出卡片。

        :param report: :class:`~fishtank.offline.OfflineReport`
        :param on_claim: 点"收下"后的回调（无参）
        :returns: 是否真的弹了
        """
        if self.win is not None or report is None:
            return False

        th = self.theme
        win = tk.Toplevel(self.root)
        self.win = win
        win.title(self.text.get("app.card_title"))
        win.configure(bg=th.card_bg)
        win.resizable(False, False)
        try:
            win.transient(self.root)
            # 🔴 不 grab_set()：不抢焦点、不阻塞其他窗口（准则 L8）
            win.attributes("-topmost", True)
        except tk.TclError:
            pass

        pad = 18
        wrap = 320
        font_title = (th.font_family, 14, "bold")
        font_body = (th.font_family, 10, "normal")
        font_gain = (th.font_family, 16, "bold")
        font_sub = (th.font_family, 9, "normal")

        tk.Label(win, text=self.text.get("offline_card.title"), bg=th.card_bg,
                 fg=th.card_fg, font=font_title).pack(padx=pad, pady=(pad, 6))

        body = self.text.pick("offline_card.variants", random.randrange(1000)) or self.text.get("offline_card.body")
        tk.Label(win, text=body, bg=th.card_bg, fg=th.card_fg, font=font_body,
                 wraplength=wrap, justify="left").pack(padx=pad, pady=(0, 10))

        gained = int(getattr(report, "coins_gained_milli", 0) or 0)
        if gained > 0:
            earned = self.text.get("offline_card.earned").replace(
                "{coins}", format_coins(gained, self.bal))
            tk.Label(win, text=earned, bg=th.card_bg, fg=th.card_accent,
                     font=font_gain).pack(padx=pad, pady=(0, 2))
            tk.Label(win, text=self.text.get("offline_card.sub"), bg=th.card_bg,
                     fg=th.card_fg, font=font_sub).pack(padx=pad, pady=(0, 6))
        else:
            # L7：没有收益就不要显示"0 金币"，那是一种隐性责备
            tk.Label(win, text=self.text.get("empty_states.offline_zero"),
                     bg=th.card_bg, fg=th.card_fg, font=font_body,
                     wraplength=wrap, justify="left").pack(padx=pad, pady=(0, 8))

        hours = 0.0
        try:
            hours = float(report.away_hours())
        except (AttributeError, TypeError, ValueError):
            hours = 0.0
        if hours >= 0.1:
            elapsed = self.text.get("offline_card.elapsed").replace(
                "{hours}", "%.1f" % hours)
            tk.Label(win, text=elapsed, bg=th.card_bg, fg=th.card_fg,
                     font=font_sub).pack(padx=pad, pady=(0, 10))

        btn = tk.Button(win, text=self.text.get("offline_card.button"),
                        bg=th.card_accent, fg=th.card_bg, font=font_body,
                        relief="flat", bd=0, padx=16, pady=5, cursor="hand2",
                        command=lambda: self._claim(on_claim))
        btn.pack(padx=pad, pady=(0, pad))

        win.protocol("WM_DELETE_WINDOW", lambda: self._claim(on_claim))
        self._center(win)
        self.shown = True
        return True

    def _center(self, win):
        """把卡片摆到屏幕中央偏上。"""
        try:
            win.update_idletasks()
            w = win.winfo_width()
            h = win.winfo_height()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            win.geometry("+%d+%d" % (max(0, (sw - w) // 2),
                                     max(0, int(sh * 0.34) - h // 2)))
        except tk.TclError:
            pass

    def _claim(self, on_claim):
        """领取 = 直接关闭。没有第二步确认（准则 L5）。"""
        self.close()
        if on_claim is not None:
            try:
                on_claim()
            except Exception:
                pass

    def close(self):
        """关闭卡片。"""
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
        return True
