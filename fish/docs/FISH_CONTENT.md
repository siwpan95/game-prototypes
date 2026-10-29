# 懒人桌面养鱼模拟器 · 鱼种与内容库（FISH_CONTENT）

> **用途**：本文件是「懒人桌面养鱼模拟器」的内容源（content source）。工程师将按文末 Schema 直接灌入 `data/fish_data.json`，由 `allin_engine`（PY 端）与 XJ380 C++ 端共用同一份数据。
> **配套文档**：`PRD.md`（玩法/数值/需求）、`FISH_CONTENT.md`（本文件，内容资产）。
> **关键决策（来自 Q5）**：全部**程序化绘制，零 PNG**。因此「配色方案（HEX）」即美术资产——鱼的模样 = 颜色表 + 体型参数 + 程序绘制函数。XJ380 端按同一 HEX 降级为色块/线条。
> **总量**：鱼 24 种（R1×6 / R2×6 / R3×5 / R4×4 / R5×3）；装饰物 12 件；UI 文案一套（L6 零催促）。

---

## 0. 字段 Schema 与灌库说明

每条鱼在 `fish_data.json` 中的标准结构（示例 = `zebra_danio`）：

```json
{
  "id": "zebra_danio",
  "name_zh": "斑马鱼",
  "name_la": "Danio rerio",
  "rarity": "R1",
  "group": "淡水",
  "color": {
    "body": "#C8D2DC",
    "belly": "#E8EEF2",
    "fin": "#9AA7B2",
    "pattern": "#2B2F36"
  },
  "shape": {
    "length": 1.0,
    "height_ratio": 0.28,
    "tail": "fork"
  },
  "behavior": {
    "speed": "fast",
    "layer": "中",
    "schooling": "高"
  },
  "science": "原产南亚溪流，是经典模式生物，胚胎透明便于观测发育，基因组已全测序。",
  "codex_unlock": "实验室里最著名的小鱼，纵纹如斑马，游动永远风风火火。"
}
```

| 字段 | 类型 | 说明 | 取值约束 |
|---|---|---|---|
| `id` | string | 英文小写+下划线，程序内唯一键 | 见各条目 |
| `name_zh` | string | 中文名 | — |
| `name_la` | string | 学名（拉丁，斜体惯例不写斜体符号） | — |
| `rarity` | string | 稀有度，决定产出概率/数值系数/视觉语言 | `R1`–`R5` |
| `group` | string | 族群标签，用于 P1-09 成套加成 | `淡水`/`热带`/`深海` |
| `color.body` | hex | 主体色 | `#RRGGBB` |
| `color.belly` | hex | 腹部色（程序绘制时叠在身体下半） | `#RRGGBB` |
| `color.fin` | hex | 鳍色 | `#RRGGBB` |
| `color.pattern` | hex | 花纹色（条纹/斑点/光斑） | `#RRGGBB` |
| `shape.length` | float | 相对体长，基准 1.0 = 缸内「标准鱼」长度 | 0.85–2.2 |
| `shape.height_ratio` | float | 体高比（体长:体高 的倒数参考，数值越大越扁高） | 0.22–0.8 |
| `shape.tail` | enum | 尾鳍形状，驱动程序绘制分支 | `fan`/`fork`/`round`/`long` |
| `behavior.speed` | enum | 游动速度，驱动 BT 移动节点频率 | `slow`/`normal`/`fast` |
| `behavior.layer` | string | 常驻水层，`/` 表示跨层 | `底`/`中`/`上` |
| `behavior.schooling` | enum | 群游倾向，影响自然聚团行为强度 | `高`/`中`/`低` |
| `science` | string | 一句真实科普（30–50 字），图鉴展示 | 须可考证 |
| `codex_unlock` | string | 图鉴解锁描述（轻松语气，无说教） | — |

---

## 1. 稀有度视觉语言规范（R1 → R5）

程序化绘制时，按稀有度套用不同「视觉强度」。原则：**越稀有越华丽，但绝不靠闪烁弹窗炫富**——视觉只在缸内安静呈现。

| 稀有度 | 配色 | 渐变 | 描边/光晕 | 尾鳍 | 附加光效 | 出现暗示 |
|---|---|---|---|---|---|---|
| **R1** | 纯单色（body 为主，belly/fin 同色系微差） | 无 | 无 | 普通 `fork` | 无 | 无特殊处理 |
| **R2** | 双色（body + belly 明显区分） | 无 | 无 | `fork` 或 `round` | 无 | 无 |
| **R3** | 三色 + pattern 花纹 | 弱（body→fin 一步过渡） | 无 | 可 `long` | 无 | 解锁时一行轻提示 |
| **R4** | 多色，body→fin 明显渐变 | 中（线性渐变） | 弱发光描边（1px，低亮度） | 特殊 `long` 飘带 | 轻微拖影粒子 | 解锁柔光 1 秒 |
| **R5** | 双色强渐变（body↔fin 双向） | 强（双端渐变） | 发光描边（2px，中亮度）+ 外晕 | 特殊尾鳍 + 额外鳍饰 | 持续柔光粒子（气泡/星点） | 解锁柔光 2 秒 + 图鉴页高亮 |

> XJ380 降级：R4/R5 的渐变与光晕在 XJ380 端退化为「双色块 + 描边加粗」，不实现粒子；见 PRD §6 降级版。

---

## 2. 鱼种内容库（24 种）

### R1（6 种）— 常见邻居，零门槛

**1. zebra_danio 斑马鱼**
- 学名：`Danio rerio`
- 族群：淡水
- 配色：body `#C8D2DC` / belly `#E8EEF2` / fin `#9AA7B2` / pattern `#2B2F36`
- 体型：length `1.0` / height_ratio `0.28` / tail `fork`
- 游动：speed `fast` / layer `中` / schooling `高`
- 科普：原产南亚溪流，是经典模式生物，胚胎透明便于观测发育，基因组已全测序。
- 图鉴：实验室里最著名的小鱼，纵纹如斑马，游动永远风风火火。

**2. white_cloud 白云金丝**
- 学名：`Tanichthys albonubes`
- 族群：淡水
- 配色：body `#B8C4A8` / belly `#E6EADF` / fin `#D98C8C` / pattern `#F2E8C0`
- 体型：length `0.9` / height_ratio `0.30` / tail `fork`
- 游动：speed `normal` / layer `中` / schooling `高`
- 科普：1932年发现于广州白云山，曾被认为野外灭绝，本世纪初在华南多地重新现身。
- 图鉴：体侧一道金丝，中国本土的「唐鱼」，一度消失又归来。

**3. corydoras 鼠鱼**
- 学名：`Corydoras paleatus`
- 族群：淡水
- 配色：body `#A89A78` / belly `#D8CFB8` / fin `#8A7E60` / pattern `#5C5340`
- 体型：length `1.1` / height_ratio `0.35` / tail `fork`
- 游动：speed `slow` / layer `底` / schooling `高`
- 科普：南美甲鲶，可吞空气行肠呼吸，胸鳍具硬棘防御，喜底栖群游清残饵。
- 图鉴：圆头圆脑的底层清洁工，最爱扎堆在缸底巡逻。

**4. guppy 孔雀鱼**
- 学名：`Poecilia reticulata`
- 族群：热带
- 配色：body `#6FB7C9` / belly `#D9F0F2` / fin `#E8A0C0` / pattern `#3A6E8C`
- 体型：length `1.0` / height_ratio `0.32` / tail `fan`
- 游动：speed `normal` / layer `上` / schooling `中`
- 科普：胎生鳉鱼，雄鱼尾鳍斑斓，繁殖力强，是性选择进化研究的经典对象。
- 图鉴：尾巴像孔雀开屏，生出小鱼而非产卵的温柔妈妈。

**5. neon_tetra 红绿灯**
- 学名：`Paracheirodon innesi`
- 族群：热带
- 配色：body `#2E6E8E` / belly `#E34B4B` / fin `#1C4A66` / pattern `#7FD0E0`
- 体型：length `0.85` / height_ratio `0.28` / tail `fork`
- 游动：speed `normal` / layer `中` / schooling `高`
- 科普：亚马逊黑水流域小型灯鱼，体侧蓝绿红三色，群游时如流动的光带。
- 图鉴：一抹电光蓝配血红，成群游动像一串流动的信号灯。

**6. platy 月光鱼**
- 学名：`Xiphophorus maculatus`
- 族群：热带
- 配色：body `#E0B84C` / belly `#F2E2B0` / fin `#D98C3C` / pattern `#B5532C`
- 体型：length `0.95` / height_ratio `0.34` / tail `round`
- 游动：speed `normal` / layer `中` / schooling `中`
- 科普：中美洲胎生鳉鱼，体色多变易杂交，常与剑尾鱼杂交育成众多品种。
- 图鉴：圆润温和的杂色小灯，月光般柔和的好脾气邻居。

### R2（6 种）— 有点性格

**7. goldfish 草金鱼**
- 学名：`Carassius auratus`
- 族群：淡水
- 配色：body `#E8A23C` / belly `#F4C97A` / fin `#D98A2C` / pattern `#B5531C`
- 体型：length `1.2` / height_ratio `0.45` / tail `fork`
- 游动：speed `slow` / layer `中` / schooling `中`
- 科普：由鲫鱼驯化千年的观赏鱼，因视锥变异可呈现金红黑白等多色。
- 图鉴：千年驯化的金色精灵，从池塘游进了全世界的窗台。

**8. koi 锦鲤**
- 学名：`Cyprinus rubrofuscus`
- 族群：淡水
- 配色：body `#F2F2F2` / belly `#FFFFFF` / fin `#E2452C` / pattern `#1C1C1C`
- 体型：length `1.4` / height_ratio `0.42` / tail `fork`
- 游动：speed `normal` / layer `中` / schooling `中`
- 科普：日本百年选育的观赏鲤，红白等品系名贵，单尾拍卖曾超百万人民币。
- 图鉴：池中王者，红白黑交织的水墨画，游姿雍容。

**9. hillstream_loach 吸鳅**
- 学名：`Beaufortia kweichowensis`
- 族群：淡水
- 配色：body `#5A6B5A` / belly `#8A9A82` / fin `#3E4A3E` / pattern `#2A302A`
- 体型：length `1.0` / height_ratio `0.22` / tail `round`
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：山溪急流底栖，腹鳍呈吸盘状贴石防冲走，体扁平适应高氧激流。
- 图鉴：扁平如叶片，吸盘肚子牢牢贴住溪流石头的隐士。

**10. angelfish 神仙鱼**
- 学名：`Pterophyllum scalare`
- 族群：热带
- 配色：body `#C8C2B0` / belly `#EAE6DA` / fin `#3A3548` / pattern `#2A2A2A`
- 体型：length `1.3` / height_ratio `0.75` / tail `fork`
- 游动：speed `normal` / layer `中` / schooling `低`
- 科普：南美亚马逊慈鲷，体侧扁高如帆，亲鱼共同护卵护幼，具领域性。
- 图鉴：高耸如帆的优雅舞者，成对时寸步不离。

**11. betta 斗鱼**
- 学名：`Betta splendens`
- 族群：热带
- 配色：body `#2C5FB0` / belly `#4A7FC8` / fin `#7A2CC0` / pattern `#1A2E6E`
- 体型：length `1.1` / height_ratio `0.50` / tail `fan`
- 游动：speed `normal` / layer `上` / schooling `低`
- 科普：东南亚稻田弱酸静水，具迷鳃可直接呼吸空气，雄鱼争斗激烈色彩盛装。
- 图鉴：孤傲的蓝色武士，鳍如绸缎，宁可独处也不合群。

**12. ram_cichlid 荷兰凤凰**
- 学名：`Mikrogeophagus ramirezi`
- 族群：热带
- 配色：body `#E8C84C` / belly `#F2E2B0` / fin `#4A8CC8` / pattern `#D94C8C`
- 体型：length `1.0` / height_ratio `0.50` / tail `fork`
- 游动：speed `normal` / layer `底` / schooling `中`
- 科普：委内瑞拉奥里诺科河慈鲷，宝蓝镶金红，体型小巧温和适合群养。
- 图鉴：娇小玲珑的彩虹宝石，蓝金红交织的迷你凤凰。

### R3（5 种）— 出彩收藏

**13. african_cichlid 非洲慈鲷（黄王子）**
- 学名：`Labidochromis caeruleus`
- 族群：淡水
- 配色：body `#F2D23C` / belly `#F8E68C` / fin `#E8B82C` / pattern `#C99A1C`
- 体型：length `1.1` / height_ratio `0.45` / tail `fork`
- 游动：speed `fast` / layer `底` / schooling `中`
- 科普：马拉维湖慈鲷由共同祖先快速辐射出数百种，口孵育幼色彩绚丽。
- 图鉴：马拉维湖的黄色闪电，口含鱼卵的温柔父亲。

**14. axolotl 美西螈**
- 学名：`Ambystoma mexicanum`
- 族群：淡水
- 配色：body `#E8D8D0` / belly `#F2E6E0` / fin `#D8C0C0` / pattern `#C8A8A8`
- 体型：length `1.6` / height_ratio `0.40` / tail `long`
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：墨西哥特有蝾螈，幼态持续终生不蜕变，可再生四肢与脊髓，野外已极危。
- 图鉴：永远长不大的「六角恐龙」，笑眯眯地在水里漫步。

**15. discus 七彩神仙**
- 学名：`Symphysodon aequifasciata`
- 族群：热带
- 配色：body `#C85A8C` / belly `#E8A8C0` / fin `#6A4A8C` / pattern `#3A2A5C`
- 体型：length `1.3` / height_ratio `0.80` / tail `round`
- 游动：speed `slow` / layer `中` / schooling `低`
- 科普：亚马逊黑水河圆盘状鱼，亲鱼分泌体表黏液育幼，对水质极为敏感。
- 图鉴：水中圆盘，父母用身上黏液喂养幼儿的温柔巨人。

**16. mandarinfish 麒麟鱼**
- 学名：`Synchiropus splendidus`
- 族群：热带
- 配色：body `#1C6E8C` / belly `#2E9E9E` / fin `#E8A23C` / pattern `#D94C8C`
- 体型：length `0.9` / height_ratio `0.45` / tail `round`
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：西太平洋珊瑚礁鱼，少数具真正蓝色素细胞的脊椎动物，无鳞且分泌毒黏液。
- 图鉴：游动的抽象画，地球上极少真正「蓝」的脊椎动物。

**17. anglerfish 鮟鱇**
- 学名：`Melanocetus johnsonii`
- 族群：深海
- 配色：body `#2A2A38` / belly `#3A3A4A` / fin `#1A1A24` / pattern `#6AE0E0`
- 体型：length `1.2` / height_ratio `0.70` / tail `round`
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：深海雌鱼背鳍特化为发光诱饵，部分种类雄鱼寄生雌体共享血液。
- 图鉴：提着小灯笼的暗黑猎手，深渊里最诡谲的约会方式。

### R4（4 种，P1-06 批次）— 稀客

**18. arowana 龙鱼**
- 学名：`Scleropages formosus`
- 族群：淡水
- 配色：body `#C8A04C` / belly `#E0C078` / fin `#B08838` / pattern `#8A6A28`
- 体型：length `1.8` / height_ratio `0.35` / tail `long`
- 游动：speed `normal` / layer `上` / schooling `低`
- 科普：古老骨舌鱼，口孵育苗，亚洲龙鱼因稀有濒危，被视为风水祥瑞之鱼。
- 图鉴：一身古铜金甲，昂首巡游如水中蛟龙。

**19. seahorse 海马**
- 学名：`Hippocampus kuda`
- 族群：热带
- 配色：body `#C88A4C` / belly `#D8A878` / fin `#3A6E8E` / pattern `#6A4A2C`
- 体型：length `1.0` / height_ratio `0.30` / tail `round`（卷曲，程序绘制为向上勾）
- 游动：speed `slow` / layer `中` / schooling `低`
- 科普：海龙科鱼类，雄性具育儿袋孵卵，直立靠背鳍游动，多种受贸易威胁。
- 图鉴：唯一由爸爸怀孕的鱼，直立着身子害羞地摇曳。

**20. barreleye 管眼鱼**
- 学名：`Macropinna microstoma`
- 族群：深海
- 配色：body `#3A5A6A` / belly `#4A6A78` / fin `#2A4450` / pattern `#8AE8E8`
- 体型：length `1.1` / height_ratio `0.40` / tail `fork`
- 游动：speed `slow` / layer `中` / schooling `低`
- 科普：太平洋深海鱼，头部透明罩住朝天的管状眼，可透过头顶视物极罕见。
- 图鉴：顶着透明头盔的怪客，眼睛永远望着上方的水流。

**21. hatchetfish 斧头鱼**
- 学名：`Argyropelecus aculeatus`
- 族群：深海
- 配色：body `#C8D0D8` / belly `#E8EEF2` / fin `#A8B2BC` / pattern `#6A7A8A`
- 体型：length `0.9` / height_ratio `0.60` / tail `fork`
- 游动：speed `slow` / layer `中` / schooling `中`
- 科普：深海银色小鱼，眼朝天觅食落饵，体侧发光器向下制造反荫蔽伪装。
- 图鉴：薄如刀片的银色飞斧，夜里浮上中层觅食的微光精灵。

### R5（3 种，P1-06 批次）— 传说级

**22. coelacanth 腔棘鱼**
- 学名：`Latimeria chalumnae`
- 族群：深海
- 配色：body `#2E5A8C` / belly `#3E729E` / fin `#1C3E66` / pattern `#C8D0D8`
- 体型：length `2.0` / height_ratio `0.50` / tail `fork`（三叶尾：上下叶+中叶）
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：曾被认为6600万年前灭绝，1938年南非捕获活体，肉鳍近四足类祖先。
- 图鉴：从化石里游出来的活化石，4亿年几乎没变过的深海隐者。

**23. viperfish 毒蛇鱼**
- 学名：`Chauliodus sloani`
- 族群：深海
- 配色：body `#1A2A3A` / belly `#243646` / fin `#0E1822` / pattern `#6AE0E0`
- 体型：length `1.3` / height_ratio `0.40` / tail `fork`
- 游动：speed `normal` / layer `中` / schooling `低`
- 科普：深海鱼，长獠牙状齿配发光诱饵，可大张口吞比己大猎物，胃极富弹性。
- 图鉴：满口钢牙的暗夜猎手，用腹侧灯光诱捕路过的倒霉蛋。

**24. goblin_shark 哥布林鲨**
- 学名：`Mitsukurina owstoni`
- 族群：深海
- 配色：body `#E8A8B0` / belly `#F2C4C8` / fin `#D88890` / pattern `#C86870`
- 体型：length `2.2` / height_ratio `0.35` / tail `fork`（上下不对称）
- 游动：speed `slow` / layer `底` / schooling `低`
- 科普：深海粉红活化石，颌可瞬间弹射前伸捕食，是1.25亿年古老鲨系唯一幸存。
- 图鉴：长鼻粉面的深渊幽灵，弹射下颌的捕食速度堪称一绝。

---

## 3. 族群成套规则（P1-09 参考）

集齐**同一族群全部鱼种**触发一次性的温和加成（非惩罚、非限时）。各群组成员如下：

| 族群 | 成员数 | 鱼种 id |
|---|---|---|
| **淡水** | 9 | `zebra_danio`, `white_cloud`, `corydoras`, `goldfish`, `koi`, `hillstream_loach`, `african_cichlid`, `axolotl`, `arowana` |
| **热带** | 9 | `guppy`, `neon_tetra`, `platy`, `angelfish`, `betta`, `ram_cichlid`, `discus`, `mandarinfish`, `seahorse` |
| **深海** | 6 | `anglerfish`, `barreleye`, `hatchetfish`, `coelacanth`, `viperfish`, `goblin_shark` |

- 加成建议：`+8%` 全局金币（叠加在装饰之上，设总加成上限见 PRD §7）。
- 解锁时仅图鉴页亮起一行「你集齐了【XX】族群」，无任何弹窗轰炸。

---

## 4. 装饰物库（12 件，P1-07）

程序化绘制描述均为「无贴图」实现方案；XJ380 端退化为同色块/线条。

| # | id | 名称 | 程序化绘制描述 | 加成 | 建议价格(金币) |
|---|---|---|---|---|---|
| 1 | `pebble_substrate` | 鹅卵石底砂 | 缸底铺满随机大小/灰褐渐变的椭圆鹅卵石，错落不重叠 | +2% | 80 |
| 2 | `water_plant` | 水草丛 | 3–5 根贝塞尔曲线绿色水草自底生长，缓慢正弦摇曳 | +3% | 120 |
| 3 | `driftwood` | 沉木 | 棕色分形枝状沉木横卧缸底，带年轮纹理线 | +2% | 150 |
| 4 | `bubble_stone` | 气泡石 | 缸底小石 + 连续上升的半透明圆气泡粒子（fx.particle） | +3% | 100 |
| 5 | `mini_bridge` | 红拱小桥 | 缸顶一角红色拱形小桥剪影，朱红描边 | +2% | 200 |
| 6 | `lantern` | 暖光灯笼 | 缸角悬挂发光圆灯笼，暖色径向光晕（PY 端柔光，XJ380 为实心圆+描边） | +4% | 260 |
| 7 | `coral` | 粉紫珊瑚 | 粉紫分形珊瑚枝，顶部细枝随机。XJ380 降级为色块簇 | +4% | 300 |
| 8 | `treasure_chest` | 溢金宝箱 | 金色箱体半开，口部溢出上升金币粒子（低速循环） | +5% | 400 |
| 9 | `castle` | 海底城堡 | 灰蓝卡通城堡剪影立于缸底，带小窗与旗 | +5% | 500 |
| 10 | `glow_jellyfish` | 发光水母 | 半透明钟形伞 + 飘带触手，伞缘柔光呼吸式明灭 | +6% | 600 |
| 11 | `star_sand` | 星砂 | 缸底散布缓慢明灭的星点粒子（深空感），低亮度 | +4% | 350 |
| 12 | `lucky_shrine` | 朱红福龛 | 朱红小神龛 + 金色「福」字，外环柔光。最高加成 | +8% | 900 |

> 加成策略：装饰加成与族群成套加成**可叠加**，但全局总加成设上限（建议 ≤ `+40%`，见 PRD §7），避免数值失控。价格梯度对应稀有度，R5 鱼与福龛为消费终点。

---

## 5. UI 文案表（L6 零催促合规）

> **L6 铁律**：禁止任何 guilt / FOMO / 催促文案。不允许「快来看看你的鱼！」「已经 3 天没上线了」「你的鱼饿坏了」之类。离线卡片基调 = 「欢迎回来，鱼儿们很好」。

### 5.1 按钮
| 场景 | 文案 |
|---|---|
| 主进入 | 进入鱼缸 |
| 一键喂养 | 投喂（自动投喂已开启时显示「鱼儿自己会吃饱」） |
| 图鉴 | 图鉴 |
| 装饰 | 装饰 |
| 设置 | 设置 |
| 一键隐藏窗口 | 隐藏窗口 |
| 托盘恢复 | 显示鱼缸 |
| 关闭确认 | 最小化到托盘（鱼缸继续在后台运行） |

### 5.2 标签页
| 标签 | 文案 |
|---|---|
| 主视图 | 鱼缸 |
| 收集 | 图鉴 |
| 布置 | 装饰 |
| 偏好 | 设置 |

### 5.3 常驻提示（正向、不催促）
| 触发 | 文案 |
|---|---|
| 自动投喂开启 | 自动投喂已开启，鱼儿会自己吃饱。 |
| 新鱼孵化 | 有新朋友加入了鱼缸，去认识一下吧。 |
| 图鉴解锁 | 图鉴又翻开了新的一页。 |
| 水质良好 | 水质清澈，鱼儿状态很放松。 |
| 离线收益结算完成 | 你离开时，鱼缸一切如常。 |

### 5.4 离线结算卡片（核心：欢迎回来，无惩罚）
```
┌─────────────────────────────┐
│        欢 迎 回 来            │
│                             │
│  你离开的这段时间，鱼儿们    │
│  都被照顾得很好。自动投喂    │
│  与水质维护一直在后台运行。  │
│                             │
│  期间共积累  N  枚金币       │
│  （离线收益，无任何惩罚）    │
│                             │
│        [ 收下，谢谢 ]        │
└─────────────────────────────┘
```
- 文案变体（随机，均中性）：「鱼缸一直很安静地运转着。」/「回来得正好，鱼儿们正精神。」/「这段时间一切都好，放心。」
- **绝不出现**：「你的鱼饿坏了」「再不来看看就……」「错过啦」。

### 5.5 空状态
| 场景 | 文案 |
|---|---|
| 图鉴全空 | 你的图鉴还是空白的，去鱼缸里遇见第一条鱼吧。 |
| 无装饰 | 给鱼缸添点装饰，鱼儿会更自在。 |
| 离线收益为 0 | 这段时间缸里很安静，下次多放几条鱼就有收获啦。 |
| 鱼市暂无可买 | 鱼市正在补货，过一阵再来看看。 |

---

## 6. 灌库校验清单（工程师用）

- [ ] 24 条鱼 `id` 唯一，与本文逐字一致
- [ ] 每条 `color.*` 为合法 `#RRGGBB`
- [ ] `shape.tail` ∈ {fan, fork, round, long}
- [ ] `behavior.speed` ∈ {slow, normal, fast}；`layer` ∈ {底,中,上}（可组合）
- [ ] `rarity` 分布：R1×6 / R2×6 / R3×5 / R4×4 / R5×3
- [ ] `group` 分布：淡水 9 / 热带 9 / 深海 6
- [ ] P0 首批量 = R1–R3 共 17 条；P1-06 = R4+R5 共 7 条
- [ ] 每条 `science` 30–50 字且可考证（已逐条核验来源）
- [ ] 12 件装饰 `bonus` 在 2%–8% 区间，总加成上限按 PRD §7
- [ ] UI 文案全表通过 L6 零催促审查（无 guilt/FOMO 词）

> 数据来源核验：白云金丝（seriouslyfish.com / 百度百科）、哥布林鲨（Wikipedia: Goblin shark）、美西螈（IUCN / National Geographic / NHM）、腔棘鱼（NHM / NOAA Fisheries / National Geographic）、斧头鱼（WHOI Twilight Zone / FishBase）、孔雀鱼/红绿灯/斗鱼等通用观赏鱼资料均来自公开可考证来源；麒麟鱼蓝色素细胞（cyanophore）已单独核验（Synchiropus splendidus 为少数具真正蓝色素细胞的脊椎动物）。
