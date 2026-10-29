# Progress Quest 官方机制参考

来源：https://progressquest.com/info.php（官方手册）+ 游戏百科

---

## 设计哲学

> "Progress Quest belongs to a new breed of 'fire and forget' RPGs. There is no need to interact with Progress Quest at all; it will make progress with you or without you."

**核心体验**：创建角色 → 看着它自动运行 → 什么也不用做

> "Your character will make no progress except when Progress Quest is running."

---

## 官方确认的核心机制

### 1. 属性系统
- **力量（STR）**：唯一影响游戏性的属性——提高负重容量，间接加快升级速度
- **其他属性**（CON/DX/IN/WI/CH）：装饰性，显示在面板上，不影响实际游戏速度
- **Roll / Unroll**：角色创建时可以用 `Roll` 按钮掷骰子，并用 `Unroll` 回退到之前的掷骰结果（PQ独有功能）

### 2. 战斗与经验
- 击杀怪物获得经验
- 死亡机制：**抽象化处理**——被强力怪物击杀不会真死，只是减少经验获取速度（"reducing the experience accumulated for each successful murder"）

### 3. 战利品与商店
- 每个被杀的生物掉落战利品（trophy）
- **负重条满 → 自动回城出售**
- 出售获得金币后，如果足够，**自动购买更好的装备**（weapon or armor）
- Tip（官方手册明确说明）：STR 提高 → 负重容量提高 → 回城频率降低 → 打怪时间更多 → 升级更快

### 4. 任务系统
完成任务后获得四种奖励之一（随机选择）：
- a) 特殊贵重宝物
- b) 更好的武器或护甲
- c) 属性提升
- d) 新法术（加入法术书）

完成任务后自动分配后续任务。

### 5. 升级系统
- 经验条满 → 升级
- 升级时：**自动获得若干属性提升 + 新法术**
- 法术显示在法术书中，格式：`法术名 I`（罗马数字表示等级）

### 6. 章节 / 剧情系统
- 任务是"整体章节进度"的一部分
- 前一章完成后，新章节加入
- 官方背景故事：Grumdrig 地区，四个王国（Knoram / Expodrine / Oobag / Spoltog）

### 7. 存档系统
- 退出时自动保存
- 升级时自动保存
- 完成任务时自动保存
- 每次保存时创建备份文件
- **存档损坏 / 丢失 = 角色永久丢失，无法恢复**（官方明确说明）

### 8. 在线模式（原版功能，复刻版可选）
- 角色上传到排行榜（Hall of Fame）
- "Council of Roilwachhs" 每15分钟投票更新排名
- 可以和其他角色比较成就

---

## 对 Multiverse 复刻版的启示

### 严格保留的机制
1. **STR 是唯一有效属性**（其他属性装饰性，但可以在面板上显示）
2. **零操作**：游戏完全自动运行
3. **章节系统**：任务推进章节，章节完成后解锁新内容
4. **四种任务奖励**：随机分配，保持惊喜感
5. **死亡抽象化**：不真死，只降速

### 可以现代化的地方
1. **UI**：原版是2002年的Windows桌面程序风格，可以现代化
2. **主题系统**：多元宇宙切换（原版只有一个架空世界）
3. **离线进度**：原版没有，但现代 idle game 标准（可选）
4. **存档可靠性**：原版容易损坏，我们可以做得更可靠

### 不要过度复杂化的地方
1. ❌ 不要让属性真正影响战斗（失去 PQ 灵魂）
2. ❌ 不要添加主动技能（PQ 是零操作）
3. ❌ 不要做复杂的装备系统（原版装备只影响面板显示）
4. ❌ 不要做社交 / 公会系统（除非后期作为可选项）

---

## 原版 PQ 种族与职业（搞笑命名，供参考）

### 种族（16个）
Half Orc（半半兽人）、Half Human（半人）、Half Halfling（半半身人）、
Double Hobbit（大型哈比人）、Low Elf（低等精灵）、Dung Elf（污粪精灵）、
Talking Pony（会说话的小马）、Greater Gnome（大型地精）、
Gyrognome（回转地精）、Lesser Dwarf（小型矮人）、
Crested Dwarf（鸡冠矮人）、Eel Man（鳗鱼人）、
Panda Man（熊猫人）、Trans-Kobold（变形狗头人）、
Enchanted motorcycle（魔法机车）、Will o' the Wisp（鬼火）、
Battle-Finch（战斗雀鸟）、Double Wookie（大型武技族）、
Skraeling（丑人）、DemiCanadian（半加拿大人）、Land Squid（地行乌贼）

### 职业（17个）
Ur-Paladin（呃……圣骑士）、Voodoo Princess（巫毒公主）、
Robot Monk（机器僧侣）、Mu-Fu Monk（幕府僧侣）、
Mage Illusionist（幻影法师）、Shiv-Knight（剃刀骑士）、
Inner Mason（精神马尾松）、Fighter/Organist（战士／风琴手）、
Puma Burglar（美洲狮盗贼）、Runeloremaster（符文专家）、
Tongueblade（操舌剑者）、Hunter Strangler（猎人扼杀者）、
Battle-Felon（战斗恶棍）、Tickle-Mimic（搞笑小丑）、
Slow Poisoner（慢性施毒师）、Bastard Lunatic（杂种狂人）、
Lowling（卑下者）、Birdrider（鸟骑士）

---

## 章节背景故事关键词（可用于 Multiverse 主题剧情）

原版背景是一个搞笑的中世纪奇幻故事，关键名词：
- Vorlak、Crosshutch、Thraeskamp
- Five Skrelkampi、Truebine
- Belnap、Papperboxen、Horbug
- Yallow the Speldrig、Grumdrig、Wainthane Topknox
- Spilwaer Spond、Jordref、Welham
- Roilwachhs、mansefur、manssach、Scrolstamp

Multiverse 版可以用类似风格，为每个游戏主题写搞笑背景故事。

---

*最后更新：2026-06-29*
*来源：progressquest.com 官方手册 + 游戏百科*
