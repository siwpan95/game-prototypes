# Mod/DLC 制作指南

卡瑞玛拉使用目录式 Mod 系统，每个 Mod 是一个独立子目录，包含地图、物件、卡牌和记忆。

---

## 快速开始

### 使用脚手架工具

```bash
# 交互式创建
python tools/create_mod.py

# 命令行创建（1 张地图，带返回传送门）
python tools/create_mod.py --id my_dungeon --name "我的地牢" --desc "地牢扩展" --maps 1

# 创建多地图 Mod
python tools/create_mod.py --id big_world --name "大世界" --maps 3
```

工具会自动生成完整的目录结构和模板文件。创建后根据提示在 `data/base_mod.json` 添加入口传送门。

---

## Mod 目录结构

```
mods/<mod_id>/
├── mod.json          ← 必须：Mod 清单文件
├── maps/             ← 地图 .txt 文件
├── objects/          ← 物件 .json 文件（可交互物 + 记忆问题）
├── cards/            ← 卡牌 .json 文件
└── memories/         ← 记忆 .json 文件
```

---

## mod.json 清单格式

```json
{
  "mod_id": "dlc_forest",
  "name": "枯林",
  "version": "1.0.0",
  "description": "宅邸外的一片枯木森林...",
  "maps": [
    {
      "map_id": "forest_entrance",
      "name": "枯林入口",
      "map_file": "maps/forest_entrance.txt",
      "player_start": {"col": 1, "row": 15},
      "objects_file": "objects/forest_entrance.json",
      "cards": {
        "forest_spirit_01": [8, 3],
        "withered_oak_01":   [18, 15]
      },
      "portals": [
        {
          "col": 0, "row": 15,
          "char": "←",
          "target_mod": null,
          "target_map": "mansion",
          "target_col": 37, "target_row": 13
        }
      ],
      "mechanisms": [
        {
          "id": "forest_light",
          "trigger_type": "CARD_COLLECTED",
          "trigger_id": "forest_spirit_01",
          "desc": "林中之灵的光芒驱散了迷雾...",
          "actions": [
            {"type": "replace_area", "col_start": 10, "col_end": 20,
             "row_start": 5, "row_end": 10, "target": ["暗"], "replacement": "░"}
          ]
        }
      ]
    }
  ]
}
```

### 清单字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `mod_id` | ✅ | Mod 唯一标识（英文，不含空格） |
| `name` | ✅ | 显示名称（中文） |
| `version` | ✅ | 版本号 |
| `maps[].map_id` | ✅ | 地图唯一 ID |
| `maps[].map_file` | ✅ | 地图 .txt 相对路径 |
| `maps[].player_start` | ✅ | 玩家出生点 `{col, row}` |
| `maps[].objects_file` | ✅ | 物件 .json 相对路径 |
| `maps[].cards` | - | `{card_id: [col, row]}` 或 `null`（不在本图） |
| `maps[].portals` | - | 传送门列表 |
| `maps[].mechanisms` | - | 数据驱动机关列表 |

---

## 地图文件 (.txt)

地图是纯文本网格，**每个字符占据一个格子**：

```
- 墙：不可行走（墙壁）
- ░：可行走（地板）
- 暗：不可行走（黑暗区域）
- 门：不可行走的门（机关可将其替换为 ░）
- 阁楼卧室书房... 等区域标签（装饰性，可行走）
- →←↑↓▼▲：传送门标记（可行走，由系统自动标注）
```

### 地图规则

1. **第一行和最后一行** 必须全是墙壁字符（上下边界）
2. **每行第一个和最后一个字符** 建议为墙壁（左右边界）
3. 行宽不强制统一，系统自动补齐到 40 列（`COLS`）
4. 行数不强制，系统限制为 32 行（`ROWS`）

### 区域标签

在地图行首放置中文区域名可以在地图上显示区域标签（如"阁楼""地下室"）。标签字符本身视为可行走。

---

## 物件文件 (objects.json)

```json
{
  "interactives": [
    {
      "id": "forest_spirit_01",
      "col": 8, "row": 3,
      "hitbox_w": 1, "hitbox_h": 1
    }
  ],
  "memory_questions": [
    {
      "id": "q_whose_forest",
      "col": 10, "row": 25,
      "text": "这片森林是谁的领域？",
      "answer_card": "forest_spirit_01"
    }
  ]
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `interactives[].id` | 对应 `memories/<id>.json` 的记忆 ID |
| `interactives[].col/row` | 物件在地图上的坐标（0-indexed） |
| `interactives[].hitbox_w/h` | 碰撞体积（单位：格），默认 1 |
| `memory_questions[].text` | 问题文本（支持多行） |
| `memory_questions[].answer_card` | 正确答案的卡牌 ID |

---

## 卡牌文件 (cards/*.json)

```json
{
  "name": "枯萎橡树",
  "glyph": "橡",
  "desc": "一棵被雷电劈成两半的橡树，树皮上刻着无法辨认的文字。"
}
```

| 字段 | 说明 |
|------|------|
| `name` | 卡牌名称（显示在收集面板） |
| `glyph` | 卡牌单字（在背包中显示） |
| `desc` | 卡牌描述文字 |

---

## 记忆文件 (memories/*.json)

```json
{
  "name": "枯萎橡树",
  "sanity_cost": 5,
  "text": "你抚摸着橡树的裂纹。一瞬间，你看到了多年前的雷暴——闪电劈开了树冠，火焰从内部燃烧了整整七天。"
}
```

| 字段 | 说明 |
|------|------|
| `name` | 记忆名称（弹出标题） |
| `sanity_cost` | 触发该记忆消耗的理智值 |
| `text` | 记忆正文（支持多行） |

---

## 传送门

传送门用于连接不同地图。每条传送门是单向的，**需要两条传送门（一来一回）才能实现双向通行**。

### 在 mod.json 中定义

```json
"portals": [
  {
    "col": 0, "row": 15,          // 此 Mod 地图上的入口坐标
    "char": "←",                   // 地图上显示的箭头字符
    "target_mod": null,            // null = base, 否则写 mod_id
    "target_map": "mansion",       // 目标地图 ID
    "target_col": 37,              // 目标地图上的落地坐标
    "target_row": 13
  }
]
```

### 在 base_mod.json 中添加入口

创建新 Mod 后需要在 `data/base_mod.json` 的 `portals` 数组中添加对应入口：

```json
{
  "col": 20, "row": 30,
  "char": "▼",
  "target_mod": "dlc_forest",
  "target_map": "forest_entrance",
  "target_col": 1, "target_row": 15
}
```

---

## 机关系统

机关由事件触发，执行地图替换动作。

### 触发类型

| trigger_type | 说明 |
|--------------|------|
| `CARD_COLLECTED` | 收集到指定卡牌时触发 |
| `MEMORY_TRIGGERED` | 触发指定记忆时触发 |

### 动作类型

| type | 说明 | 参数 |
|------|------|------|
| `replace_at` | 替换单个格子 | `col, row, old, new` |
| `replace_region` | 替换矩形区域 | `col_start, col_end, row_start, row_end, target[], replacement` |
| `replace_area` | 替换区域中匹配的字符 | `col_start, col_end, row_start, row_end, target[], replacement` |

### 示例

```json
{
  "id": "attic_unlock",
  "trigger_type": "CARD_COLLECTED",
  "trigger_id": "key_01",
  "desc": "你举起铜钥匙。阁楼的墙壁发出一阵低沉的回声...",
  "actions": [
    {"type": "replace_at", "col": 18, "row": 3, "old": "门", "new": "░"}
  ]
}
```

---

## 测试

创建 Mod 后运行测试套件验证完整性：

```bash
python tests/test_mod_system.py --verbose
```

测试覆盖：
- Mod 发现与解析
- 地图/物件文件存在性
- 传送门连接有效性
- 传送门坐标边界检查
- 卡牌/记忆 JSON 完整性
- 卡牌引用完整性
- 玩家出生点安全性

---

## 最佳实践

1. **先画地图，再放物件**。在 .txt 文件中设计好地形后，再在 mod.json 中放置物件坐标。
2. **传送门双向配置**。确保 A→B 和 B→A 的传送门都存在。
3. **出生点安全**。`player_start` 必须在 `░`（地板）上，不能是 `墙` 或 `暗`。
4. **卡牌 ID 全局唯一**。不同 Mod 的卡牌 ID 不能重复（建议加 mod 前缀如 `forest_xx`）。
5. **机关触发后测试**。测试机关是否确实揭示了新区域。
6. **记忆费用合理**。`sanity_cost` 建议 3-8，确保玩家有足够理智探索所有记忆。
