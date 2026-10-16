"""战斗引擎（纯业务逻辑，零UI依赖）— 支持技能、战车、敌人描述"""
import random
from .character import Character, Enemy


class BattleResult:
    """战斗回合结果"""

    def __init__(self):
        self.messages = []  # 战斗文本
        self.player_dead = False
        self.enemy_dead = False
        self.escaped = False
        self.exp_gained = 0
        self.gold_gained = 0
        self.leveled_up = False
        self.item_dropped = None  # Item


class BattleEngine:
    """战斗引擎：处理所有战斗计算逻辑"""

    @staticmethod
    def _hit_target(player: Character) -> str:
        """描述受击对象：乘战车且存活 → 战车，否则 → 角色名"""
        vehicle = player.vehicle
        if (not player.combat_on_foot and vehicle is not None
                and vehicle.is_alive()):
            return f"战车{vehicle.name}"
        return player.name

    @staticmethod
    def _vehicle_break_message(player: Character, was_alive: bool) -> str:
        """战车在本回合刚被击毁时的提示（未毁返回空串）"""
        vehicle = player.vehicle
        if (was_alive and vehicle is not None and not vehicle.is_alive()):
            return f"战车{vehicle.name}被击毁了！"
        return ""

    @staticmethod
    def calculate_damage(attacker: Character, defender: Character) -> int:
        """计算攻击伤害"""
        base = attacker.attack + random.randint(-5, 5)
        return defender.take_damage(max(1, base))

    @staticmethod
    def calculate_enemy_damage(attacker: Character, defender: Character) -> int:
        """计算敌人攻击伤害（含烟幕弹等一次性减伤）"""
        mult = getattr(attacker, "next_attack_mult", 1.0)
        if isinstance(attacker, Enemy):
            attacker.next_attack_mult = 1.0  # 一次性生效
        base = int(attacker.attack * mult) + random.randint(-3, 3)
        return defender.take_damage(max(1, base))

    # ── 普通攻击 ──

    @staticmethod
    def player_attack(data: "GameData") -> BattleResult:
        """玩家攻击"""
        result = BattleResult()
        enemy = data.current_enemy
        if not enemy:
            return result

        dmg = BattleEngine.calculate_damage(data.player, enemy)
        result.messages.append(f"{data.player.name}攻击造成{dmg}点伤害！")

        if not enemy.is_alive():
            result.enemy_dead = True
            return result

        # 敌人反击
        vehicle_was_alive = (data.player.vehicle is not None
                             and data.player.vehicle.is_alive())
        dmg2 = BattleEngine.calculate_enemy_damage(enemy, data.player)
        result.messages.append(
            f"{enemy.name}攻击{BattleEngine._hit_target(data.player)}造成{dmg2}点伤害！"
        )
        break_msg = BattleEngine._vehicle_break_message(data.player, vehicle_was_alive)
        if break_msg:
            result.messages.append(break_msg)

        if not data.player.is_alive():
            result.player_dead = True

        return result

    # ── 防御 ──

    @staticmethod
    def player_defend(data: "GameData") -> BattleResult:
        """玩家防御（乘战车时翻倍战车防御，否则翻倍自身防御）"""
        result = BattleResult()
        enemy = data.current_enemy
        if not enemy:
            return result

        result.messages.append(f"{data.player.name}采取了防御姿态！")
        vehicle = data.player.vehicle
        use_vehicle = (vehicle is not None and not data.player.combat_on_foot
                       and vehicle.is_alive())
        if use_vehicle:
            original = vehicle.defense_multiplier
            vehicle.defense_multiplier = 2.0
        else:
            original = data.player._base_defense
            data.player._base_defense *= 2

        dmg = BattleEngine.calculate_enemy_damage(enemy, data.player)
        result.messages.append(
            f"{enemy.name}攻击{BattleEngine._hit_target(data.player)}造成{dmg}点伤害！"
        )

        if use_vehicle:
            vehicle.defense_multiplier = original
        else:
            data.player._base_defense = original
        break_msg = BattleEngine._vehicle_break_message(data.player, use_vehicle)
        if break_msg:
            result.messages.append(break_msg)

        if not data.player.is_alive():
            result.player_dead = True

        return result

    # ── 技能 ──

    @staticmethod
    def player_use_skill(data: "GameData", skill_index: int) -> BattleResult:
        """玩家使用技能"""
        result = BattleResult()
        enemy = data.current_enemy
        player = data.player
        if not enemy:
            return result

        if skill_index < 0 or skill_index >= len(player.skills):
            result.messages.append("无效的技能！")
            return result

        skill = player.skills[skill_index]

        # 检查消耗（攻击技能消耗 HP 的 cost%）
        cost_hp = max(1, player.max_hp * skill.cost // 100)
        if player.hp <= cost_hp:
            result.messages.append(f"HP不足，无法使用{skill.name}！（需要{cost_hp}HP）")
            return result

        player.hp -= cost_hp
        result.messages.append(f"{player.name}使用了{skill.name}！（消耗{cost_hp}HP）")

        skill_type = skill.type
        effect_val = skill.effect

        if skill_type == "attack":
            # 攻击技能：基于 effect 值放大伤害
            multiplier = 1.5 + int(effect_val) / 100 if effect_val.isdigit() else 1.5
            dmg = int((player.attack + random.randint(-3, 5)) * multiplier)
            actual = enemy.take_damage(dmg)
            result.messages.append(f"造成{actual}点技能伤害！")

        elif skill_type == "defense":
            # 防御技能：临时大幅加防御（乘车时加成战车）
            boost = 2 + (int(effect_val) if effect_val.isdigit() else 3)
            vehicle = player.vehicle
            use_vehicle = (vehicle is not None and not player.combat_on_foot
                           and vehicle.is_alive())
            if use_vehicle:
                original = vehicle.defense_multiplier
                vehicle.defense_multiplier = float(boost)
            else:
                original = player._base_defense
                player._base_defense *= boost
            result.messages.append(f"防御力提升{boost}倍！")

            dmg = BattleEngine.calculate_enemy_damage(enemy, player)
            result.messages.append(
                f"{enemy.name}攻击{BattleEngine._hit_target(player)}造成{dmg}点伤害！"
            )
            if use_vehicle:
                vehicle.defense_multiplier = original
            else:
                player._base_defense = original
            break_msg = BattleEngine._vehicle_break_message(player, use_vehicle)
            if break_msg:
                result.messages.append(break_msg)

        elif skill_type == "special":
            # 特殊技能：回复HP
            heal_amount = int(effect_val) if effect_val.isdigit() else 30
            player.heal(heal_amount)
            result.messages.append(f"恢复了{heal_amount}点HP！")

            # 敌人照常攻击
            vehicle_was_alive = (player.vehicle is not None
                                 and not player.combat_on_foot
                                 and player.vehicle.is_alive())
            dmg = BattleEngine.calculate_enemy_damage(enemy, player)
            result.messages.append(
                f"{enemy.name}攻击{BattleEngine._hit_target(player)}造成{dmg}点伤害！"
            )
            break_msg = BattleEngine._vehicle_break_message(player, vehicle_was_alive)
            if break_msg:
                result.messages.append(break_msg)

        elif skill_type == "evade":
            # 回避技能：概率完全闪避
            dodge_chance = int(effect_val) / 100 if effect_val.isdigit() else 0.7
            if random.random() < dodge_chance:
                result.messages.append("完全闪避了攻击！")
            else:
                vehicle_was_alive = (player.vehicle is not None
                                     and not player.combat_on_foot
                                     and player.vehicle.is_alive())
                dmg = BattleEngine.calculate_enemy_damage(enemy, player)
                result.messages.append(
                    f"{enemy.name}攻击{BattleEngine._hit_target(player)}造成{dmg}点伤害！"
                )
                break_msg = BattleEngine._vehicle_break_message(player, vehicle_was_alive)
                if break_msg:
                    result.messages.append(break_msg)

        # 检查击杀
        if not enemy.is_alive():
            result.enemy_dead = True
            return result

        if not player.is_alive():
            result.player_dead = True

        return result

    # ── 道具（战斗中） ──

    # 伤害类道具的系别映射与未命中系别的保底伤害
    _DAMAGE_EFFECTS = {
        "damage_bio": ("生物",),
        "damage_mech": ("机械",),
    }
    _DAMAGE_FALLBACK = 20

    @staticmethod
    def player_use_item(data: "GameData", index: int) -> BattleResult:
        """战斗中使用道具（含夺命三宝与特殊炮弹）

        按物品的 使用场景/效果类型 分流；回合结束后敌人照常反击。
        """
        result = BattleResult()
        player = data.player
        enemy = data.current_enemy
        if not enemy:
            return result
        if index < 0 or index >= len(data.inventory):
            result.messages.append("无效的物品！")
            return result

        item = data.inventory[index]
        item_data = item.data
        scene = getattr(item_data, "use_scene", "人")
        effect = getattr(item_data, "effect_type", "")
        value = item.effect_value

        if scene == "探索":
            result.messages.append(f"{item.name}不能在战斗中使用！")
            return result

        # ── 场景校验（不通过则不消耗） ──
        if scene == "车" and (player.combat_on_foot
                              or player.vehicle is None
                              or not player.vehicle.is_alive()):
            result.messages.append(f"{item.name}需要乘坐战车时使用！")
            return result

        consumed = True
        if effect == "heal":
            player.heal(value)
            result.messages.append(f"使用了{item.name}，恢复了{value}点HP！")
        elif effect == "revive":
            player.heal(player.max_hp)
            result.messages.append(f"使用了{item.name}，HP完全恢复！")
        elif effect == "fuel":
            if player.vehicle is not None:
                player.vehicle.refuel(value)
                result.messages.append(f"使用了{item.name}，恢复了{value}点燃料！")
            else:
                result.messages.append("没有战车可以使用燃料！")
                consumed = False
        elif effect == "buff_atkdef":
            # 军号：攻防大幅提升；20% 几率损坏（仍生效）
            player.battle_atk_mult += value / 100
            player.battle_def_mult += value / 100
            result.messages.append(
                f"{player.name}吹响了{item.name}！攻击与防御大幅提升！"
            )
            if random.random() < 0.2:
                result.messages.append("军号吹破了……")
        elif effect == "debuff_enemy":
            # 烟幕弹：本回合敌人伤害减半
            enemy.next_attack_mult = max(0.1, 1.0 - value / 100)
            result.messages.append(f"投出了{item.name}，敌人被烟幕笼罩！")
        elif effect == "buff_vehicle_atk":
            # 雷达：本场战车攻击提升
            player.vehicle.battle_atk_mult += value / 100
            result.messages.append(f"雷达锁定目标，战车攻击提升！")
        elif effect in BattleEngine._DAMAGE_EFFECTS:
            # 特殊炮弹/药液：按系别克制
            target_categories = BattleEngine._DAMAGE_EFFECTS[effect]
            if enemy.category in target_categories:
                damage = value
                result.messages.append(
                    f"{item.name}命中{enemy.name}，造成{damage}点伤害！"
                )
            else:
                damage = BattleEngine._DAMAGE_FALLBACK
                result.messages.append(
                    f"{item.name}对{enemy.name}效果不佳，仅造成{damage}点伤害。"
                )
            enemy.take_damage(damage)
            if not enemy.is_alive():
                result.enemy_dead = True
                if consumed:
                    data.inventory.pop(index)
                return result
        else:
            # 旧版 heal/fuel 直通的兼容路径
            if item.type == "heal":
                player.heal(value)
                result.messages.append(f"使用了{item.name}，恢复了{value}点HP！")
            elif item.type == "fuel" and player.vehicle is not None:
                player.vehicle.refuel(value)
                result.messages.append(f"使用了{item.name}，恢复了{value}点燃料！")
            else:
                result.messages.append(f"{item.name}现在不能使用。")
                consumed = False

        if consumed:
            data.inventory.pop(index)

        # 敌人反击
        dmg = BattleEngine.calculate_enemy_damage(enemy, player)
        result.messages.append(
            f"{enemy.name}攻击{BattleEngine._hit_target(player)}造成{dmg}点伤害！"
        )
        break_msg = BattleEngine._vehicle_break_message(player, True)
        if break_msg:
            result.messages.append(break_msg)

        if not player.is_alive():
            result.player_dead = True
        return result

    # ── 逃跑 ──

    @staticmethod
    def try_escape(data: "GameData") -> BattleResult:
        """尝试逃跑"""
        result = BattleResult()
        enemy = data.current_enemy
        if not enemy:
            return result

        chance = data.player.speed / (data.player.speed + enemy.speed)
        if random.random() < chance:
            result.escaped = True
            result.messages.append("成功逃跑了！")
            return result

        result.messages.append("逃跑失败！")
        vehicle_was_alive = (data.player.vehicle is not None
                             and data.player.vehicle.is_alive())
        dmg = BattleEngine.calculate_enemy_damage(enemy, data.player)
        result.messages.append(
            f"{enemy.name}攻击{BattleEngine._hit_target(data.player)}造成{dmg}点伤害！"
        )
        break_msg = BattleEngine._vehicle_break_message(data.player, vehicle_was_alive)
        if break_msg:
            result.messages.append(break_msg)

        if not data.player.is_alive():
            result.player_dead = True

        return result

    # ── 结算 ──

    @staticmethod
    def resolve_victory(data: "GameData", items_map: dict) -> BattleResult:
        """结算胜利"""
        result = BattleResult()
        enemy = data.current_enemy
        if not enemy:
            return result

        result.exp_gained = enemy.exp_reward
        result.gold_gained = enemy.gold_reward
        result.enemy_dead = True

        result.leveled_up = data.player.gain_exp(result.exp_gained)
        data.gold += result.gold_gained

        result.messages.append(
            f"胜利！获得{result.exp_gained}经验和{result.gold_gained}金币！"
        )
        data.add_log(f"击败了{enemy.name}，获得{result.exp_gained}经验值！")
        # 敌人描述
        desc = enemy.data.description.strip() if enemy.data.description else ""
        if desc:
            result.messages.append(f"[{enemy.name}]: {desc}")

        if result.leveled_up:
            result.messages.append(f"升级了！现在等级 {data.player.level}！")

        # 按敌人配置掉落（替换原来的全物品随机）
        drop_item_id = getattr(enemy.data, "drop_item_id", 0)
        drop_rate = getattr(enemy.data, "drop_rate", 0.0)
        if drop_item_id > 0 and drop_rate > 0 and random.random() < drop_rate and items_map:
            from .item import Item
            item_data = items_map.get(drop_item_id)
            if item_data is not None:
                dropped = Item(item_data)
                data.inventory.append(dropped)
                result.item_dropped = dropped
                result.messages.append(f"获得了{dropped.name}！")

        # 任务进度追踪
        from .game_state import QuestManager
        QuestManager.track_kill(data, enemy.data.id)

        return result

    @staticmethod
    def end_battle(data: "GameData"):
        """结束战斗，清理状态"""
        data.state = data.state.__class__.WORLD
        data.current_enemy = None
