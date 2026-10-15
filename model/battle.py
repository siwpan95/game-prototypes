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
        if vehicle is not None and vehicle.is_alive():
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
        """计算敌人攻击伤害"""
        base = attacker.attack + random.randint(-3, 3)
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
        if vehicle is not None and vehicle.is_alive():
            original = vehicle.defense
            vehicle.defense *= 2
            vehicle_was_alive = True
        else:
            original = data.player._base_defense
            data.player._base_defense *= 2
            vehicle_was_alive = False

        dmg = BattleEngine.calculate_enemy_damage(enemy, data.player)
        result.messages.append(
            f"{enemy.name}攻击{BattleEngine._hit_target(data.player)}造成{dmg}点伤害！"
        )

        if vehicle_was_alive:
            vehicle.defense = original
        else:
            data.player._base_defense = original
        break_msg = BattleEngine._vehicle_break_message(data.player, vehicle_was_alive)
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
            # 防御技能：临时大幅加防御（乘战车时加成战车）
            boost = 2 + (int(effect_val) if effect_val.isdigit() else 3)
            vehicle = player.vehicle
            vehicle_was_alive = vehicle is not None and vehicle.is_alive()
            if vehicle_was_alive:
                original = vehicle.defense
                vehicle.defense *= boost
            else:
                original = player._base_defense
                player._base_defense *= boost
            result.messages.append(f"防御力提升{boost}倍！")

            dmg = BattleEngine.calculate_enemy_damage(enemy, player)
            result.messages.append(
                f"{enemy.name}攻击{BattleEngine._hit_target(player)}造成{dmg}点伤害！"
            )
            if vehicle_was_alive:
                vehicle.defense = original
            else:
                player._base_defense = original
            break_msg = BattleEngine._vehicle_break_message(player, vehicle_was_alive)
            if break_msg:
                result.messages.append(break_msg)

        elif skill_type == "special":
            # 特殊技能：回复HP
            heal_amount = int(effect_val) if effect_val.isdigit() else 30
            player.heal(heal_amount)
            result.messages.append(f"恢复了{heal_amount}点HP！")

            # 敌人照常攻击
            vehicle_was_alive = (player.vehicle is not None
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
