"""Item models - collectible and usable items."""
from typing import List, Optional

from models.weapon import WeaponMod


class Item:
    """Base class for all items."""

    def __init__(
        self,
        name: str = "Item",
        item_type: str = "misc",
        description: str = "",
        usable: bool = True,
    ) -> None:
        self.name: str = name
        self.item_type: str = item_type
        self.description: str = description
        self.usable: bool = usable

    def use(self, player, **kwargs) -> str:
        """Use the item. Returns result message.

        Extra keyword args (e.g. ``enemies``, ``room``) are accepted so callers
        can forward context without every subclass needing to declare them.
        """
        return f"无法使用{self.name}。"

    def to_dict(self) -> dict:
        """Serialize item to dict."""
        return {
            "name": self.name,
            "item_type": self.item_type,
            "description": self.description,
            "usable": self.usable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Deserialize item from dict. Dispatches to correct subclass."""
        item_type = data.get("item_type", "misc")
        subclass_map = {
            "medkit": MedKit,
            "grenade": Grenade,
            "ammo": AmmoPickup,
            "armor": ArmorPickup,
            "heavy_armor": HeavyArmor,
            "weapon_mod": WeaponModItem,
            "flashbang": Flashbang,
            "breach": BreachingCharge,
            "stim": Stim,
        }
        target_cls = subclass_map.get(item_type, Item)
        if target_cls is Item:
            return cls(
                name=data.get("name", "Item"),
                item_type=item_type,
                description=data.get("description", ""),
                usable=data.get("usable", True),
            )
        return target_cls._from_dict_impl(data)

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Item":
        """Internal from_dict for base Item."""
        return cls(
            name=data.get("name", "Item"),
            item_type=data.get("item_type", "misc"),
            description=data.get("description", ""),
            usable=data.get("usable", True),
        )


class MedKit(Item):
    """Healing item."""

    def __init__(self, name: str = "MedKit", heal_amount: int = 25, description: str = "") -> None:
        desc = description or f"恢复{heal_amount}点生命值。"
        super().__init__(name=name, item_type="medkit", description=desc, usable=True)
        self.heal_amount: int = heal_amount

    def use(self, player, **kwargs) -> str:
        """Heal the player."""
        healed = player.heal(self.heal_amount)
        if healed > 0:
            return f"使用了{self.name}。恢复了{healed}点生命值。(生命: {player.health}/{player.max_health})"
        return f"使用了{self.name}。无需治疗。(生命: {player.health}/{player.max_health})"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["heal_amount"] = self.heal_amount
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "MedKit":
        return cls(
            name=data.get("name", "MedKit"),
            heal_amount=data.get("heal_amount", 25),
            description=data.get("description", ""),
        )


class Grenade(Item):
    """Explosive that damages all enemies in the room."""

    def __init__(self, name: str = "Grenade", damage: int = 30, radius: int = 1, description: str = "") -> None:
        desc = description or f"对范围内所有敌人造成{damage}点伤害。"
        super().__init__(name=name, item_type="grenade", description=desc, usable=True)
        self.damage: int = damage
        self.radius: int = radius

    def use(self, player, enemies: Optional[List] = None, **kwargs) -> str:
        """Deal damage to all enemies in range."""
        if enemies is None or len(enemies) == 0:
            return f"投掷了{self.name}，但没有敌人。"

        total_damage = 0
        hit_count = 0
        for enemy in enemies:
            if enemy.is_alive:
                dealt = enemy.take_damage(self.damage)
                total_damage += dealt
                hit_count += 1

        return f"投掷了{self.name}！命中{hit_count}个敌人，共{total_damage}点伤害。"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["damage"] = self.damage
        d["radius"] = self.radius
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Grenade":
        return cls(
            name=data.get("name", "Grenade"),
            damage=data.get("damage", 30),
            radius=data.get("radius", 1),
            description=data.get("description", ""),
        )


class AmmoPickup(Item):
    """Ammunition pickup for a specific weapon type."""

    def __init__(
        self, name: str = "Pistol Ammo", amount: int = 15,
        weapon_type: str = "pistol", description: str = "",
    ) -> None:
        desc = description or f"为{weapon_type}增加{amount}发弹药。"
        super().__init__(name=name, item_type="ammo", description=desc, usable=True)
        self.amount: int = amount
        self.weapon_type: str = weapon_type

    def use(self, player, **kwargs) -> str:
        """Add ammo to matching weapon."""
        for weapon in player.weapons:
            if weapon.weapon_type == self.weapon_type:
                old = weapon.ammo
                weapon.ammo = min(weapon.effective_max_ammo(), weapon.ammo + self.amount)
                added = weapon.ammo - old
                return f"拾取了{self.name}。{weapon.name}: {old} -> {weapon.ammo}发弹药。"
        return f"拾取了{self.name}，但没有兼容的武器。"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["amount"] = self.amount
        d["weapon_type"] = self.weapon_type
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "AmmoPickup":
        return cls(
            name=data.get("name", "Pistol Ammo"),
            amount=data.get("amount", 15),
            weapon_type=data.get("weapon_type", "pistol"),
            description=data.get("description", ""),
        )


class ArmorPickup(Item):
    """Armor plate pickup."""

    def __init__(self, name: str = "Armor Plate", armor_amount: int = 25, description: str = "") -> None:
        desc = description or f"增加{armor_amount}点护甲。"
        super().__init__(name=name, item_type="armor", description=desc, usable=True)
        self.armor_amount: int = armor_amount

    def use(self, player, **kwargs) -> str:
        """Add armor to the player."""
        added = player.add_armor(self.armor_amount)
        return f"装备了{self.name}。护甲: {player.armor}/{player.max_armor} (+{added})"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["armor_amount"] = self.armor_amount
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "ArmorPickup":
        return cls(
            name=data.get("name", "Armor Plate"),
            armor_amount=data.get("armor_amount", 25),
            description=data.get("description", ""),
        )


class WeaponModItem(Item):
    """A weapon modification that can be picked up and auto-equipped."""

    def __init__(self, name: str = "Silencer", mod: Optional[WeaponMod] = None, description: str = "") -> None:
        if mod is None:
            mod = WeaponMod(name=name, mod_type="silencer")
        desc = description or f"武器改装件: {mod.name} ({mod.mod_type})"
        super().__init__(name=name, item_type="weapon_mod", description=desc, usable=True)
        self.mod: WeaponMod = mod

    def use(self, player, **kwargs) -> str:
        """Auto-equip mod to current weapon."""
        weapon = player.current_weapon()
        if weapon is None:
            return f"找到了{self.name}，但没有武器可以安装。"

        if weapon.add_mod(self.mod):
            return f"已将{self.name}安装到{weapon.name}！"
        return f"无法将{self.name}安装到{weapon.name}——改装槽已满。"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["mod"] = self.mod.to_dict()
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "WeaponModItem":
        mod_data = data.get("mod", {})
        mod = WeaponMod.from_dict(mod_data)
        return cls(
            name=data.get("name", mod.name),
            mod=mod,
            description=data.get("description", ""),
        )


class Flashbang(Item):
    """Blinds/pins enemies: applies heavy suppression for several turns."""

    def __init__(self, name: str = "闪光弹", duration: int = 2, description: str = "") -> None:
        desc = description or f"致盲范围内所有敌人，使其被压制{duration}个回合。"
        super().__init__(name=name, item_type="flashbang", description=desc, usable=True)
        self.duration: int = duration

    def use(self, player, enemies: Optional[List] = None, **kwargs) -> str:
        if enemies is None or len(enemies) == 0:
            return f"投掷了{self.name}，但没有敌人。"
        hit = 0
        for e in enemies:
            if e.is_alive:
                e.status_effects["suppressed"] = max(
                    e.status_effects.get("suppressed", 0), self.duration
                )
                hit += 1
        return f"投掷了{self.name}！闪光致盲{hit}名敌人，他们被压制{self.duration}回合！"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["duration"] = self.duration
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Flashbang":
        return cls(
            name=data.get("name", "闪光弹"),
            duration=data.get("duration", 2),
            description=data.get("description", ""),
        )


class BreachingCharge(Item):
    """High-yield charge: heavy area damage + destroys one destructible cover."""

    def __init__(self, name: str = "破门炸药", damage: int = 45, description: str = "") -> None:
        desc = description or f"对范围内敌人造成{damage}点伤害，并可摧毁一处可破坏掩体。"
        super().__init__(name=name, item_type="breach", description=desc, usable=True)
        self.damage: int = damage

    def use(self, player, enemies: Optional[List] = None, room=None, **kwargs) -> str:
        if enemies is None or len(enemies) == 0:
            return f"安放了{self.name}，但没有敌人。"
        total = 0
        hit = 0
        killed: List[str] = []
        for e in enemies:
            if e.is_alive:
                dealt = e.take_damage(self.damage)
                total += dealt
                hit += 1
                if not e.is_alive:
                    killed.append(e.name)
        msg = f"引爆了{self.name}！命中{hit}名敌人，共{total}点伤害。"
        if killed:
            msg += f" 击杀: {', '.join(killed)}！"
        if room is not None and getattr(room, "destructibles", None):
            removed = room.destructibles.pop(0)
            msg += f" 摧毁了掩体：{removed}。"
        return msg

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["damage"] = self.damage
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "BreachingCharge":
        return cls(
            name=data.get("name", "破门炸药"),
            damage=data.get("damage", 45),
            description=data.get("description", ""),
        )


class Stim(Item):
    """Combat stimulant: immediate heal + temporary accuracy/damage buff."""

    def __init__(
        self, name: str = "兴奋剂", heal_amount: int = 25, buff_turns: int = 3,
        acc_bonus: float = 0.10, dmg_mult: float = 1.20, description: str = "",
    ) -> None:
        desc = description or f"立即回复{heal_amount}生命，并在{buff_turns}回合内提升命中与伤害。"
        super().__init__(name=name, item_type="stim", description=desc, usable=True)
        self.heal_amount: int = heal_amount
        self.buff_turns: int = buff_turns
        self.acc_bonus: float = acc_bonus
        self.dmg_mult: float = dmg_mult

    def use(self, player, **kwargs) -> str:
        healed = player.heal(self.heal_amount)
        player.buffs["stim_acc"] = self.acc_bonus
        player.buffs["stim_dmg"] = self.dmg_mult
        player.buffs["stim_turns"] = self.buff_turns
        return f"使用了{self.name}。恢复{healed}生命，进入兴奋状态{self.buff_turns}回合！"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["heal_amount"] = self.heal_amount
        d["buff_turns"] = self.buff_turns
        d["acc_bonus"] = self.acc_bonus
        d["dmg_mult"] = self.dmg_mult
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Stim":
        return cls(
            name=data.get("name", "兴奋剂"),
            heal_amount=data.get("heal_amount", 25),
            buff_turns=data.get("buff_turns", 3),
            acc_bonus=data.get("acc_bonus", 0.10),
            dmg_mult=data.get("dmg_mult", 1.20),
            description=data.get("description", ""),
        )


class HeavyArmor(ArmorPickup):
    """Larger armor plate (serialized under its own item type)."""

    def __init__(self, name: str = "重甲板", armor_amount: int = 50, description: str = "") -> None:
        super().__init__(name=name, armor_amount=armor_amount, description=description)
        self.item_type = "heavy_armor"

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "HeavyArmor":
        return cls(
            name=data.get("name", "重甲板"),
            armor_amount=data.get("armor_amount", 50),
            description=data.get("description", ""),
        )
