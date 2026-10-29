"""KeywordHandler - resolves per-keyword card effects."""

from models.dice_engine import DiceEngine


class KeywordHandler:
    """Handles resolution of all card keywords.

    Supported keywords:
        Draw N         - Draw N cards from deck.
        Exhaust N      - Exhaust this card (move to exhaust pile).
        Repeat N       - Repeat the card effect N additional times.
        GainStrength N - Gain N Strength.
        Consume N      - Remove this card from the run entirely.
        Stun N         - Stun the enemy for N turns.
        Lifesteal P    - Heal P% of damage dealt.
        Vulnerable N   - Apply N stacks of Vulnerable to the enemy.
    """

    @staticmethod
    def resolve(
        keyword: str,
        value: int,
        context: dict,
    ) -> dict:
        """Resolve a single keyword effect.

        Args:
            keyword: The keyword name.
            value: The keyword's numeric value.
            context: Dict with keys:
                'player'  - Player object
                'enemy'   - Enemy object (may be None)
                'deck'    - DeckManager object
                'card'    - The Card being played
                'damage_dealt' - Damage dealt so far (for Lifesteal)
                'event_bus'    - EventBus instance

        Returns:
            Dict with results of the keyword resolution, including
            any messages for the battle log.
        """
        handler = {
            "Draw": KeywordHandler._handle_draw,
            "Exhaust": KeywordHandler._handle_exhaust,
            "Repeat": KeywordHandler._handle_repeat,
            "GainStrength": KeywordHandler._handle_gain_strength,
            "Consume": KeywordHandler._handle_consume,
            "Stun": KeywordHandler._handle_stun,
            "Lifesteal": KeywordHandler._handle_lifesteal,
            "Vulnerable": KeywordHandler._handle_vulnerable,
        }.get(keyword)

        if handler is None:
            return {"message": f"未知关键词: {keyword}"}

        return handler(value, context)

    @staticmethod
    def _handle_draw(value: int, context: dict) -> dict:
        """Draw N cards."""
        deck = context.get("deck")
        if deck is None:
            return {"message": "没有可用的牌库"}
        drawn = deck.draw(value)
        return {"message": f"抽了 {len(drawn)} 张牌", "drawn": len(drawn)}

    @staticmethod
    def _handle_exhaust(value: int, context: dict) -> dict:
        """Exhaust this card."""
        deck = context.get("deck")
        card = context.get("card")
        if deck and card:
            deck.exhaust_card(card)
            return {"message": f"{card.name} 已消耗"}
        return {"message": "消耗失败"}

    @staticmethod
    def _handle_repeat(value: int, context: dict) -> dict:
        """Repeat the card effect N additional times."""
        return {"message": f"重复 {value} 次", "repeat_count": value}

    @staticmethod
    def _handle_gain_strength(value: int, context: dict) -> dict:
        """Gain N Strength."""
        player = context.get("player")
        if player:
            player.str += value
            return {"message": f"获得 {value} 点力量"}
        return {"message": "没有目标角色"}

    @staticmethod
    def _handle_consume(value: int, context: dict) -> dict:
        """Consume this card (remove from run)."""
        deck = context.get("deck")
        card = context.get("card")
        if deck and card:
            deck.consume_card(card)
            return {"message": f"{card.name} 已用尽"}
        return {"message": "用尽失败"}

    @staticmethod
    def _handle_stun(value: int, context: dict) -> dict:
        """Stun the enemy for N turns."""
        enemy = context.get("enemy")
        if enemy:
            enemy.apply_stun(value)
            return {"message": f"敌人眩晕 {value} 回合"}
        return {"message": "没有可眩晕的目标"}

    @staticmethod
    def _handle_lifesteal(value: int, context: dict) -> dict:
        """Heal P% of damage dealt."""
        player = context.get("player")
        damage_dealt = context.get("damage_dealt", 0)
        if player and damage_dealt > 0:
            heal_amount = max(1, int(damage_dealt * value / 100))
            actual = player.heal(heal_amount)
            return {"message": f"吸血回复 {actual} 生命", "healed": actual}
        return {"message": "吸血: 没有可吸取的伤害"}

    @staticmethod
    def _handle_vulnerable(value: int, context: dict) -> dict:
        """Apply N stacks of Vulnerable to the enemy."""
        enemy = context.get("enemy")
        if enemy:
            enemy.apply_vulnerable(value)
            return {"message": f"施加 {value} 层易伤"}
        return {"message": "没有易伤目标"}
