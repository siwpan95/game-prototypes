## 二、核心改动清单

### Phase 1：数据层 — PQ 原始数据迁移

| 模块 | 内容 | 说明 |
|------|------|------|
| `pq_races.py` | 21 种族，格式 `"Half Orc" → {"HP Max": +3}` | 每个种族 1-2 项属性获得 +3 起始加成 |
| `pq_classes.py` | 18 职业，格式 `"Ur-Paladin" → {"WIS": +2, "CON": +2}` | 同上 |
| `pq_spells.py` | 47 法术名 + 随机类型 | 保留伤害/治疗/增益/减益分类，自动分配威力和MP消耗 |
| `pq_monsters.py` | 180+ 怪物 `{name, level, loot}` + 16 个变体修饰 | 修饰如 `fœtal`(-4级)、`giant`(+4级)、`Battle-`(+2级) |
| `pq_equipment.py` | 39武器 + 16盾牌 + 20护甲 + 11正面词缀 + 9负面词缀 + 9防御正面 + 14防御负面 + 52 "之XX"后缀 | `generate_weapon_name()` / `generate_shield_name()` / `generate_armor_name()` 三个生成函数 |
| `pq_specials.py` | 37 特殊宝物 + 33 形容词 + 52 "之XX"后缀 | 任务奖励用 |
| `pq_acts.py` | 剧情章节列表（纯进度标记） | 不再限制怪物/任务池，改为等级区间标记 |
| `pq_names.py` | 音节表 + `generate_name()` 函数 | 生成 `Nebib` 之类的随机名 |

---

### Phase 2：游戏引擎重写 `game_engine.py`

#### 2.1 Player 属性调整

```python
# 6 Prime Stats（对齐 D&D）
strength: int      # 力量 → 攻击力
constitution: int  # 体质 → HP
dexterity: int     # 敏捷 → 闪避/先手
intelligence: int  # 智力 → MP/法术伤害
wisdom: int        # 智慧 → 法术防御/经验获取（新增！）
charisma: int      # 魅力 → 商店折扣/特殊事件

# 移除 race/job 改为随机生成，新增：
race: str          # 从 21 种族随机
klass: str         # 从 18 职业随机
title: str         # 头衔（等级达到后获得）

# 装备槽对齐 PQ（11 槽）
equipment_slots = [
    "武器",      # Weapon
    "盾牌",      # Shield
    "头盔",      # Helm
    "胸甲",      # Hauberk
    "肩甲",      # Brassairts
    "臂甲",      # Vambraces
    "手套",      # Gauntlets
    "内甲",      # Gambeson
    "裤甲",      # Cuisses
    "腿甲",      # Greaves
    "足甲",      # Sollerets
]
```

#### 2.2 升级曲线改为指数增长

```python
# PQ公式：exp_to_next = 1000 × 1.15^level
# 1级→20分钟，2级→23分钟，10级→80分钟，50级→108小时
@property
def xp_to_next(self) -> int:
    return int(1000 * (1.15 ** self.level))
```

#### 2.3 全自动角色创建

```python
@classmethod
def auto_create(cls, seed=None):
    """完全自动：随机名字 + 随机种族职业 + Roll属性"""
    name = generate_name(seed)
    race, race_bonus = random_race()
    klass, class_bonus = random_class()
    stats = roll_stats()  # 6 × 3d6
    stats = apply_bonuses(stats, race_bonus, class_bonus)
    return cls(name=name, race=race, klass=klass, ...)
```

#### 2.4 装备随机命名系统

```python
def generate_weapon(atk_base: int) -> EquipmentItem:
    name = f"{random_offense_attrib()} {random_weapon()} of {random_item_of()}"
    # 例："Vorpal Bastard Sword of Chaos"
    atk = atk_base + attrib_bonus + random.randint(-2, 2)
    return EquipmentItem(name, atk=atk, def_=0)

def generate_armor(def_base: int) -> EquipmentItem:
    name = f"{random_defense_attrib()} {random_armor()} of {random_item_of()}"
    def_ = def_base + attrib_bonus
    return EquipmentItem(name, atk=0, def_=def_)
```

#### 2.5 怪物变体系统

```python
def spawn_monster(base_name: str, player_level: int) -> Monster:
    base = MONSTER_DB[base_name]
    modifier = random_monster_mod()  # 如 "giant" (+4级)
    final_name = modifier.format(base_name)  # "giant Kobold"
    final_level = max(1, base.level + modifier.level_delta)
    final_hp = base.hp * (1 + final_level * 0.15)
    final_atk = base.attack * (1 + final_level * 0.1)
    ...
```

#### 2.6 特殊宝物系统

```python
@dataclass
class SpecialItem:
    """任务奖励的特殊宝物，带随机属性"""
    name: str           # "Golden Diadem of Fortune"
    base_name: str      # "Diadem"
    attribute: str      # "Golden"
    of_name: str        # "Fortune"
    value: int          # 卖价
```

#### 2.7 死亡机制强化

```python
def die_and_revive(self):
    """死亡不掉级，但损失当前经验进度 + 随机装备耐久下降"""
    self.hp = self.max_hp // 2
    self.mp = self.max_mp // 2
    self.xp = max(0, self.xp - self.xp_to_next // 4)
    self.combat_log.append("💀 不幸战死，经验损失25%...")
```

---

### Phase 3：主循环更新 `main.pyw`

```python
def run_game(stop_event, update_interval=5):
    config = load_tuning_config()   # 仅可调参数
    player = load_or_auto_create()  # 读档 或 全自动创角
    
    current_monster = spawn_monster_for_level(player.level)
    prev_level = player.level
    
    while not stop_event.is_set():
        # 3 次战斗
        for _ in range(3):
            player.combat_tick(current_monster)
            if current_monster.hp <= 0:
                current_monster = spawn_monster_for_level(player.level)
        
        # 升级事件
        if player.level > prev_level:
            player.learn_spell(random_pq_spell())
            player.check_title_upgrade()
            prev_level = player.level
        
        # 任务流（自动填充到 5 个）
        fill_quests_auto(player)
        
        # 回城
        if player.inv_count >= player.max_encumbrance:
            player.visit_town()
        
        # 输出
        write_game_to_excel(player)
        save_player(player)
        
        if stop_event.wait(update_interval):
            break
```

**不再需要**：
- `_try_advance_act()` — 章节改为纯标记
- `pick_monster_from_act()` — 改为按等级匹配
- `config.xlsx` 的角色/怪物/任务 Sheet — 数据移入 `data/` 模块

---

### Phase 4：Excel 输出更新 `excel_writer.py`

| Sheet | 变化 |
|-------|------|
| 角色面板 | 添加 WIS 属性行，显示 种族+职业+头衔，6属性齐全 |
| 装备 | 新增 肩甲 列，共 11 槽，装备名变为随机生成风格 |
| 背包 | 新增 "特殊宝物" 分类区域 |
| 任务 | 保持不变 |
| 法术书 | 使用 PQ 47 法术名，威力/MP随机分配 |
| 战斗日志 | 保持不变 |
| 城镇商店 | 改为显示"上次回城收益"，商店目录用 PQ 装备生成器动态显示 |
| **新增：特殊宝物** | 列出持有的特殊宝物（名称/形容词/之XX/价值） |

---

## 四、PQ 原始数据参考

### 21 种族（Races）

| 种族 | 加成属性 |
|------|----------|
| Half Orc | HP Max |
| Half Man | CHA |
| Half Halfling | DEX |
| Double Hobbit | STR |
| Hob-Hobbit | DEX, CON |
| Low Elf | CON |
| Dung Elf | WIS |
| Talking Pony | MP Max, INT |
| Gyrognome | DEX |
| Lesser Dwarf | CON |
| Crested Dwarf | CHA |
| Eel Man | DEX |
| Panda Man | CON, STR |
| Trans-Kobold | WIS |
| Enchanted Motorcycle | MP Max |
| Will o' the Wisp | WIS |
| Battle-Finch | DEX, INT |
| Double Wookiee | STR |
| Skraeling | WIS |
| Demicanadian | CON |
| Land Squid | STR, HP Max |

### 18 职业（Classes）

| 职业 | 加成属性 |
|------|----------|
| Ur-Paladin | WIS, CON |
| Voodoo Princess | INT, CHA |
| Robot Monk | STR |
| Mu-Fu Monk | DEX |
| Mage Illusioner | INT, MP Max |
| Shiv-Knight | DEX |
| Inner Mason | CON |
| Fighter/Organist | CHA, STR |
| Puma Burgular | DEX |
| Runeloremaster | WIS |
| Hunter Strangler | DEX, INT |
| Battle-Felon | STR |
| Tickle-Mimic | WIS, INT |
| Slow Poisoner | CON |
| Bastard Lunatic | CON |
| Lowling | WIS |
| Birdrider | WIS |
| Vermineer | INT |

### 47 法术（Spells）

Slime Finger, Rabbit Punch, Hastiness, Good Move, Sadness, Seasick, Shoelaces, Innoculate, Cone of Annoyance, Magnetic Orb, Invisible Hands, Revolting Cloud, Aqueous Humor, Spectral Miasma, Clever Fellow, Lockjaw, History Lesson, Hydrophobia, Big Sister, Cone of Paste, Mulligan, Nestor's Bright Idea, Holy Batpole, Tumor (Benign), Braingate, Summon a Bitch, Nonplus, Animate Nightstand, Eye of the Troglodyte, Curse Name, Dropsy, Vitreous Humor, Roger's Grand Illusion, Covet, Black Idaho, Astral Miasma, Spectral Oyster, Acrid Hands, Angioplasty, Grognor's Big Day Off, Tumor (Malignant), Animate Tunic, Ursine Armor, Holy Roller, Tonsilectomy, Curse Family, Infinite Confusion

### 11 装备槽（Equipment Slots）

Weapon, Shield, Helm, Hauberk, Brassairts, Vambraces, Gauntlets, Gambeson, Cuisses, Greaves, Sollerets

### 装备命名系统

**武器基表（39种）**：Stick|0, Broken Bottle|1, Shiv|1, Sprig|1, Oxgoad|1, Eelspear|2, Bowie Knife|2, Claw Hammer|2, Handpeen|2, Andiron|3, Hatchet|3, Tomahawk|3, Hackbarm|3, Crowbar|4, Mace|4, Battleadze|4, Leafmace|5, Shortsword|5, Longiron|5, Poachard|5, Baselard|5, Whinyard|6, Blunderbuss|6, Longsword|6, Crankbow|6, Blibo|7, Broadsword|7, Kreen|7, Warhammer|7, Morning Star|8, Pole-adze|8, Spontoon|8, Bastard Sword|9, Peen-arm|9, Culverin|10, Lance|10, Halberd|11, Poleax|12, Bandyclef|15

**盾牌基表（16种）**：Parasol|0, Pie Plate|1, Garbage Can Lid|2, Buckler|3, Plexiglass|4, Fender|4, Round Shield|5, Carapace|5, Scutum|6, Propugner|6, Kite Shield|7, Pavise|8, Tower Shield|9, Baroque Shield|11, Aegis|12, Magnetic Field|18

**护甲基表（20种）**：Lace|1, Macrame|2, Burlap|3, Canvas|4, Flannel|5, Chamois|6, Pleathers|7, Leathers|8, Bearskin|9, Ringmail|10, Scale Mail|12, Chainmail|14, Splint Mail|15, Platemail|16, ABS|17, Kevlar|18, Titanium|19, Mithril Mail|20, Diamond Mail|25, Plasma|30

**攻击正面词缀（11个）**：Polished|+1, Serrated|+1, Heavy|+1, Pronged|+2, Steely|+2, Vicious|+3, Venomed|+4, Stabbity|+4, Dancing|+5, Invisible|+6, Vorpal|+7

**攻击负面词缀（9个）**：Dull|-2, Tarnished|-1, Rusty|-3, Padded|-5, Bent|-4, Mini|-4, Rubber|-6, Nerf|-7, Unbalanced|-2

**防御正面词缀（9个）**：Studded|+1, Banded|+2, Gilded|+2, Festooned|+3, Holy|+4, Cambric|+1, Fine|+4, Impressive|+5, Custom|+3

**防御负面词缀（14个）**：Holey|-1, Patched|-1, Threadbare|-2, Faded|-1, Rusty|-3, Motheaten|-3, Mildewed|-2, Torn|-3, Dented|-3, Cursed|-5, Plastic|-4, Cracked|-4, Warped|-3, Corroded|-3

**"之XX"后缀（52个）**：Foreboding, Foreshadowing, Nervousness, Happiness, Torpor, Danger, Craft, Silence, Invisibility, Rapidity, Pleasure, Practicality, Hurting, Joy, Petulance, Intrusion, Chaos, Suffering, Extroversion, Frenzy, Sisu, Solitude, Punctuality, Efficiency, Comfort, Patience, Internment, Incarceration, Misapprehension, Loyalty, Envy, Acrimony, Worry, Fear, Awe, Guile, Prurience, Fortune, Perspicacity, Domination, Submission, Fealty, Hunger, Despair, Cruelty, Grob, Dignard, Ra, the Bone, Diamonique, Electrum, Hydragyrum

### 怪物变体修饰（16个）

| 修饰 | 等级变化 | 格式 |
|------|----------|------|
| fœtal | -4 | fœtal {name} |
| dying | -4 | dying {name} |
| crippled | -3 | crippled {name} |
| baby | -3 | baby {name} |
| adolescent | -2 | adolescent {name} |
| very sick | -2 | very sick {name} |
| lesser | -1 | lesser {name} |
| undernourished | -1 | undernourished {name} |
| greater | +1 | greater {name} |
| Elder | +1 | {name} Elder |
| war | +2 | war {name} |
| Battle- | +2 | Battle-{name} |
| Were- | +3 | Were-{name} |
| undead | +3 | undead {name} |
| giant | +4 | giant {name} |
| Rex | +4 | {name} Rex |

### 特殊宝物基名（37个）

Diadem, Festoon, Gemstone, Phial, Tiara, Scabbard, Arrow, Lens, Lamp, Hymnal, Fleece, Laurel, Brooch, Gimlet, Cobble, Albatross, Brazier, Bandolier, Tome, Garnet, Amethyst, Candelabra, Corset, Sphere, Sceptre, Ankh, Talisman, Orb, Gammel, Ornament, Brocade, Galoon, Bijou, Spangle, Gimcrack, Hood, Vulpeculum

### 特殊宝物形容词（33个）

Golden, Gilded, Spectral, Astral, Garlanded, Precious, Crafted, Dual, Filigreed, Cruciate, Arcane, Blessed, Reverential, Lucky, Enchanted, Gleaming, Grandiose, Sacred, Legendary, Mythic, Crystalline, Austere, Ostentatious, One True, Proverbial, Fearsome, Deadly, Benevolent, Unearthly, Magnificent, Iron, Ormolu, Puissant

### 头衔系统

普通头衔（9个）：Mr., Mrs., Sir, Sgt., Ms., Captain, Chief, Admiral, Saint

高级头衔（14个）：King, Queen, Lord, Lady, Viceroy, Mayor, Prince, Princess, Chief, Boss, Archbishop, Chancellor, Baroness, Inquisitor
