# -*- coding: utf-8 -*-
"""商店标签页 Mixin — 装备/消耗品购买"""

import tkinter as tk
from tkinter import ttk
import random

from core.config import (
    C_CONTENT_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT, C_SECTION_TITLE,
    C_ROW_EVEN, C_ROW_ODD, C_GOLD,
    C_BTN_NORMAL, C_BTN_HOVER, C_BTN_TEXT,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT,
    C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_ACCENT_RED, C_ACCENT_GREEN, C_ACCENT_TEAL,
    FONT_LABEL, FONT_SMALL, FONT_TINY,
    WIN_W,
)
from data.loader import get_loader


class ShopTabMixin:
    """商店标签页：装备/消耗品购买"""

    def _build_shop_tab(self):
        frame = tk.Frame(self.content_frame, bg=C_CONTENT_BG)
        self._tab_content["商店"] = frame

        header = tk.Frame(frame, bg=C_CONTENT_BG)
        header.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Label(header, text="🛒 商店", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(side=tk.LEFT)
        tk.Label(header, text="每次进入自动刷新商品", font=FONT_TINY,
                 bg=C_CONTENT_BG, fg=C_TEXT_HINT).pack(side=tk.LEFT, padx=12)

        self.shop_refresh_btn = tk.Label(header, text="🔄 刷新商品 (10G)",
                                          font=FONT_TINY, bg=C_BTN_NORMAL,
                                          fg=C_BTN_TEXT, padx=8, pady=2,
                                          cursor="hand2", relief=tk.FLAT)
        self.shop_refresh_btn.pack(side=tk.RIGHT)
        self.shop_refresh_btn.bind("<Button-1>", lambda e: self._do_shop_refresh())
        self._bind_hover(self.shop_refresh_btn, C_BTN_NORMAL, C_BTN_HOVER)

        shop_container = tk.Frame(frame, bg=C_CONTENT_BG)
        shop_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 10))

        self.shop_canvas = tk.Canvas(shop_container, bg=C_CONTENT_BG,
                                      highlightthickness=0, bd=0)
        self.shop_scrollbar = tk.Scrollbar(shop_container, orient=tk.VERTICAL,
                                            command=self.shop_canvas.yview)
        self.shop_items_frame = tk.Frame(self.shop_canvas, bg=C_CONTENT_BG)

        self.shop_win_id = self.shop_canvas.create_window(
            (0, 0), window=self.shop_items_frame, anchor="nw",
            width=WIN_W - 60)

        self.shop_items_frame.bind("<Configure>", self._on_shop_configure)
        self.shop_canvas.bind("<Configure>", self._on_canvas_configure)
        self.shop_canvas.configure(yscrollcommand=self.shop_scrollbar.set)
        self.shop_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.shop_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.shop_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.shop_canvas))
        self.shop_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel(self.shop_canvas))
        self._refresh_shop()

    def _on_shop_configure(self, event):
        self.shop_canvas.configure(scrollregion=self.shop_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.shop_canvas.itemconfig(self.shop_win_id, width=event.width)

    def _refresh_shop(self):
        for w in self.shop_items_frame.winfo_children():
            w.destroy()

        # 刷新市场波动
        market_msg = self.engine.refresh_market()
        loader = get_loader()

        # ---- 市场状态横幅 ----
        status_bar = tk.Frame(self.shop_items_frame, bg=C_CONTENT_BG)
        status_bar.pack(fill=tk.X, pady=(0, 6))
        if self.engine.market_multiplier > 1.15:
            status_color = C_ACCENT_RED
        elif self.engine.market_multiplier > 1.05 or self.engine.market_multiplier < 0.85:
            status_color = "#E9C46A"
        elif self.engine.market_multiplier < 0.95:
            status_color = C_ACCENT_GREEN
        else:
            status_color = C_TEXT_HINT
        tk.Label(status_bar, text=f"{market_msg}  (系数: {self.engine.market_multiplier:.2f})",
                 font=FONT_TINY, bg=C_CONTENT_BG, fg=status_color).pack(side=tk.LEFT)

        all_items = list(loader.equipment.items())
        shop_items = random.sample(all_items, min(8, len(all_items)))

        if not shop_items:
            tk.Label(self.shop_items_frame, text="暂无商品", font=FONT_SMALL,
                     bg=C_CONTENT_BG, fg=C_TEXT_HINT).pack(pady=20)
        else:
            for idx, (name, eq) in enumerate(shop_items):
                row_bg = C_ROW_EVEN if idx % 2 == 0 else C_ROW_ODD
                row = tk.Frame(self.shop_items_frame, bg=row_bg, height=44)
                row.pack(fill=tk.X)
                row.pack_propagate(False)

                buy_price = self.engine.get_buy_price(eq)
                slot_emoji = {"weapon": "⚔", "armor": "🛡", "shield": "🔰", "accessory": "💍"}.get(eq.slot, "📦")
                tier_mark = {1: "", 2: "✦", 3: "✦✦", 4: "✦✦✦"}.get(eq.tier, "")

                tk.Label(row, text=f"{slot_emoji}  {name} {tier_mark}",
                         font=FONT_SMALL, bg=row_bg, fg=C_TEXT,
                         width=14, anchor=tk.W).pack(side=tk.LEFT, padx=10)
                tk.Label(row, text=eq.bonus_text(), font=FONT_SMALL,
                         bg=row_bg, fg=C_TEXT_LIGHT, width=18,
                         anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=f"{buy_price} G", font=FONT_SMALL,
                         bg=row_bg, fg=C_GOLD, width=8,
                         anchor=tk.E).pack(side=tk.LEFT)

                btn = tk.Label(row, text=" 购买 ", font=FONT_SMALL,
                                bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                                padx=10, cursor="hand2", relief=tk.FLAT)
                btn.pack(side=tk.RIGHT, padx=(0, 10))
                btn.bind("<Button-1>", lambda e, n=name, p=buy_price: self._do_buy(n, p))
                self._bind_hover(btn, C_BTN_PRIMARY, "#238B7E")

            # 消耗品区
            ttk.Separator(self.shop_items_frame, orient=tk.HORIZONTAL).pack(
                fill=tk.X, padx=8, pady=(6, 4))
            tk.Label(self.shop_items_frame, text="— 消耗品 —", font=FONT_SMALL,
                     bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack()

            consume_items = list(loader.consumables.items())
            shop_consumes = [c for c in consume_items if c[1].item_type != "revive"]
            shop_consumes = random.sample(shop_consumes, min(6, len(shop_consumes)))
            for idx, (name, c) in enumerate(shop_consumes):
                row_bg = C_ROW_EVEN if idx % 2 == 0 else C_ROW_ODD
                row = tk.Frame(self.shop_items_frame, bg=row_bg, height=36)
                row.pack(fill=tk.X)
                row.pack_propagate(False)

                buy_price = self.engine.get_buy_price(c)

                tk.Label(row, text=f"{c.emoji}  {name}", font=FONT_SMALL,
                         bg=row_bg, fg=C_TEXT, width=16,
                         anchor=tk.W).pack(side=tk.LEFT, padx=10)
                tk.Label(row, text=c.desc, font=FONT_TINY,
                         bg=row_bg, fg=C_TEXT_LIGHT, width=16,
                         anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=f"{buy_price} G", font=FONT_SMALL,
                         bg=row_bg, fg=C_GOLD, width=8,
                         anchor=tk.E).pack(side=tk.LEFT)

                btn = tk.Label(row, text=" 购买 ", font=FONT_SMALL,
                                bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                                padx=10, cursor="hand2", relief=tk.FLAT)
                btn.pack(side=tk.RIGHT, padx=(0, 10))
                btn.bind("<Button-1>",
                         lambda e, n=name, p=buy_price: self._do_buy_consumable(n, p))
                self._bind_hover(btn, C_BTN_PRIMARY, "#238B7E")

        # ---- 卖出区 ----
        ttk.Separator(self.shop_items_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(self.shop_items_frame, text=f"— 卖出物品 (买入价的60%) —", font=FONT_SMALL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack()

        # 卖出背包装备
        inv_items = [(n, loader.equipment.get(n)) for n in self.engine.inventory]
        inv_items = [(n, eq) for n, eq in inv_items if eq is not None]

        if not inv_items and not any(self.engine.consumables.values()):
            tk.Label(self.shop_items_frame, text="  无可卖物品", font=FONT_TINY,
                     bg=C_CONTENT_BG, fg=C_TEXT_HINT).pack(pady=4)
        else:
            for idx, (name, eq) in enumerate(inv_items):
                row_bg = C_ROW_EVEN if idx % 2 == 0 else C_ROW_ODD
                row = tk.Frame(self.shop_items_frame, bg=row_bg, height=36)
                row.pack(fill=tk.X)
                row.pack_propagate(False)

                sell_price = self.engine.get_sell_price(eq)
                slot_emoji = {"weapon": "⚔", "armor": "🛡", "shield": "🔰", "accessory": "💍"}.get(eq.slot, "📦")

                tk.Label(row, text=f"{slot_emoji} {name}", font=FONT_SMALL,
                         bg=row_bg, fg=C_TEXT, width=18, anchor=tk.W).pack(side=tk.LEFT, padx=10)
                tk.Label(row, text=f"→ {sell_price} G", font=FONT_TINY,
                         bg=row_bg, fg=C_GOLD, width=8, anchor=tk.E).pack(side=tk.LEFT)

                btn = tk.Label(row, text=" 卖出 ", font=FONT_SMALL,
                                bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
                                padx=10, cursor="hand2", relief=tk.FLAT)
                btn.pack(side=tk.RIGHT, padx=(0, 10))
                btn.bind("<Button-1>", lambda e, n=name, p=sell_price: self._do_sell_equip(n, p))
                self._bind_hover(btn, C_BTN_DANGER, "#D65A3F")

            # 卖出消耗品
            sell_start_idx = len(inv_items)
            for ci, (name, qty) in enumerate(sorted(self.engine.consumables.items())):
                c = loader.consumables.get(name)
                if not c:
                    continue
                idx = sell_start_idx + ci
                row_bg = C_ROW_EVEN if idx % 2 == 0 else C_ROW_ODD
                row = tk.Frame(self.shop_items_frame, bg=row_bg, height=36)
                row.pack(fill=tk.X)
                row.pack_propagate(False)

                sell_price = self.engine.get_sell_price(c)

                tk.Label(row, text=f"{c.emoji} {name} x{qty}", font=FONT_SMALL,
                         bg=row_bg, fg=C_TEXT, width=18, anchor=tk.W).pack(side=tk.LEFT, padx=10)
                tk.Label(row, text=f"→ {sell_price} G", font=FONT_TINY,
                         bg=row_bg, fg=C_GOLD, width=8, anchor=tk.E).pack(side=tk.LEFT)

                btn = tk.Label(row, text=" 卖出 ", font=FONT_SMALL,
                                bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
                                padx=10, cursor="hand2", relief=tk.FLAT)
                btn.pack(side=tk.RIGHT, padx=(0, 10))
                btn.bind("<Button-1>", lambda e, n=name, p=sell_price: self._do_sell_consumable(n, p))
                self._bind_hover(btn, C_BTN_DANGER, "#D65A3F")

        self.shop_canvas.configure(scrollregion=self.shop_canvas.bbox("all"))

    def _do_shop_refresh(self):
        if self.engine.gold < 10:
            self._log("金币不足！刷新需要 10G")
            return
        self.engine.gold -= 10
        self._refresh_shop()
        market_msg = self.engine.get_market_status()
        self._log(f"🔄 商店商品已刷新（花费 10G）")
        self._log(f"   {market_msg}")
        self._set_narrative("商队带来了新货物，商店商品已更新！")

    def _do_buy(self, item_name, price):
        if self.engine.exploring:
            return
        if self.engine.gold < price:
            self._log(f"金币不足！需要 {price}G")
            return
        self.engine.gold -= price
        self.engine.inventory.append(item_name)
        self._log(f"🛒 购买了 {item_name}，花费 {price}G")
        self._set_narrative(f"购买了 {item_name}，金币 -{price}G")
        self._refresh_shop()
        self._refresh_all()

    def _do_buy_consumable(self, item_name, price):
        if self.engine.exploring:
            return
        if self.engine.gold < price:
            self._log(f"金币不足！需要 {price}G")
            return
        self.engine.gold -= price
        self.engine.add_consumable(item_name)
        self._log(f"🛒 购买了 {item_name}，花费 {price}G")
        self._set_narrative(f"购买了 {item_name}，金币 -{price}G")
        self._refresh_shop()
        self._refresh_all()

    def _do_sell_equip(self, item_name, price):
        if self.engine.exploring:
            return
        if item_name not in self.engine.inventory:
            self._log("物品不在背包中")
            return
        self.engine.inventory.remove(item_name)
        self.engine.gold += price
        self._log(f"💰 卖出了 {item_name}，获得 {price}G")
        self._set_narrative(f"卖出了 {item_name}，金币 +{price}G")
        self._refresh_shop()
        self._refresh_all()

    def _do_sell_consumable(self, item_name, price):
        if self.engine.exploring:
            return
        if self.engine.consumables.get(item_name, 0) <= 0:
            self._log("没有该消耗品可卖出")
            return
        self.engine.consumables[item_name] -= 1
        if self.engine.consumables[item_name] <= 0:
            del self.engine.consumables[item_name]
        self.engine.gold += price
        self._log(f"💰 卖出了 {item_name}，获得 {price}G")
        self._set_narrative(f"卖出了 {item_name}，金币 +{price}G")
        self._refresh_shop()
        self._refresh_all()
