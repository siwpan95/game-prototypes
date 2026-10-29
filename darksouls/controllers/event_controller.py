"""EventController - resolve bonfire, shop, and blacksmith events."""

from __future__ import annotations

from models.player import Player
from models.relic import Relic
from services.data_loader import DataLoader


class EventController:
    """Handles resolution of event encounters (bonfire, shop, blacksmith)."""

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader = data_loader

    def resolve_event_option(self, player: Player, event_data: dict, option_index: int) -> dict:
        options = event_data.get("options", [])
        if option_index < 0 or option_index >= len(options):
            return {"success": False, "message": "无效的选项。"}

        option = options[option_index]
        effect = option.get("effect", {})
        cost = option.get("cost", 0)

        if cost > 0 and not player.spend_souls(cost):
            return {"success": False, "message": f"灵魂不足！需要 {cost} 灵魂。"}

        messages: list[str] = []
        for key, value in effect.items():
            msg = self._apply_effect(player, key, value)
            if msg:
                messages.append(msg)

        result_msg = " ".join(messages) if messages else "什么也没发生。"
        return {"success": True, "message": result_msg}

    def _apply_effect(self, player: Player, effect_key: str, effect_value) -> str | None:
        if effect_key == "HealPercent":
            pct = float(effect_value)
            healed = player.heal_percent(pct)
            return f"恢复了 {healed} 点生命。"

        elif effect_key == "AddStatPoint":
            player.attribute_points += int(effect_value)
            return f"获得 {effect_value} 点属性。"

        elif effect_key == "BuyRelic":
            relic_id = str(effect_value)
            relic = self.data_loader.create_relic(relic_id)
            if relic:
                removed = player.relics.add(relic)
                msg = f"获得 {relic.name}！"
                if removed:
                    msg += f" 替换了 {removed.name}。"
                return msg
            return "遗物未找到。"

        elif effect_key == "AddStat":
            if isinstance(effect_value, dict):
                stat = effect_value.get("stat", "str")
                amount = int(effect_value.get("amount", 1))
                player.add_stat_point(stat, amount)
                stat_names = {"str": "力量", "dex": "敏捷", "vit": "体力", "fcs": "信仰"}
                stat_cn = stat_names.get(stat, stat.upper())
                return f"{stat_cn} +{amount}。"

        elif effect_key == "AddMaxHP":
            player.max_hp += int(effect_value)
            player.hp += int(effect_value)
            return f"最大生命+{effect_value}！"

        elif effect_key == "AddMaxFP":
            player.max_fp += int(effect_value)
            player.fp = player.max_fp
            return f"最大FP+{effect_value}！"

        return None

    def get_available_shop_items(self) -> list[dict]:
        items: list[dict] = []
        for relic_data in self.data_loader.load_relics():
            items.append({
                "id": relic_data["id"],
                "name": relic_data["name"],
                "description": relic_data["description"],
                "cost": 50 + hash(relic_data["id"]) % 80,
            })
        return items
