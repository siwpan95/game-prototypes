# Mod / DLC 清单 Schema（mod.json）

`ModManager` 扫描 `mods/<mod_dir>/mod.json`（以及 `base_data_dir/base_mod.json`）加载 Mod 清单。
本文件描述 `mod.json` 的字段约定，供 Mod 作者与下游消费代码参考。

> 路径安全：所有相对路径（如 `map_file` / `objects_file`）在加载时会经过路径穿越校验，
> 仅允许指向 Mod 根目录 **内部** 的文件，越界（如 `../etc/passwd` 或绝对路径）将被拒绝。

---

## 顶层结构

```json
{
  "mod_id": "my_mod",
  "name": "我的 Mod",
  "version": "1.0",
  "description": "可选的描述文本",
  "dependencies": ["base"],
  "maps": [ { ...MapDef... } ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mod_id` | string | ✅ | Mod 唯一标识，用作查询键 |
| `name` | string | ❌ | 显示名称，缺省回退为 `mod_id` |
| `version` | string | ❌ | 版本号，缺省 `"1.0"` |
| `description` | string | ❌ | 描述 |
| `dependencies` | list[string] | ❌ | 依赖的 Mod ID 列表 |
| `maps` | list[MapDef] | ❌ | 地图定义列表 |

---

## MapDef（单张地图）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `map_id` | string | ✅ | 地图唯一 ID（同 Mod 内唯一） |
| `name` | string | ❌ | 显示名称，缺省回退为 `map_id` |
| `map_file` | string | ❌ | 地图数据文件，相对 Mod 根目录 |
| `player_start` | {`col`,`row`} | ❌ | 玩家出生点，缺省 `(0,0)` |
| `objects_file` | string | ❌ | 可交互物件 JSON，相对 Mod 根目录 |
| `portals` | list[PortalDef] | ❌ | 传送门列表 |
| `mechanisms` | list[MechanismDef] | ❌ | 数据驱动机关列表 |
| `metadata` | dict | ❌ | 扩展数据，原样透传 |

### 示例

```json
{
  "map_id": "town",
  "name": "小镇",
  "map_file": "maps/town.txt",
  "player_start": { "col": 1, "row": 1 },
  "objects_file": "data/town_objects.json",
  "portals": [ { ...PortalDef... } ],
  "mechanisms": [ { ...MechanismDef... } ]
}
```

---

## PortalDef（传送门）

玩家走到该位置时触发地图切换。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `col`,`row` | int | ✅ | 触发位置 |
| `char` | string | ❌ | 地图上显示的字符，缺省 `"▣"` |
| `target_mod` | string\|null | ❌ | 目标 Mod ID，`null` = 基础游戏 |
| `target_map` | string | ✅ | 目标地图 ID |
| `target_col`,`target_row` | int | ❌ | 传送后玩家位置，缺省 `0,0` |

```json
{ "col": 5, "row": 3, "target_mod": "dungeon_mod", "target_map": "level_1", "target_col": 0, "target_row": 0 }
```

---

## MechanismDef（数据驱动机关）

由触发器激活后执行一组动作。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 机关唯一 ID |
| `trigger_type` | string | ❌ | 触发条件：`ITEM_USED`/`EVENT_FIRED`/`POSITION_REACHED`/`TURN_PASSED`，缺省 `EVENT_FIRED` |
| `trigger_id` | string | ❌ | 触发器标识，缺省 `""` |
| `desc` | string | ❌ | 描述 |
| `actions` | list[MechanismAction] | ❌ | 动作列表 |

### MechanismAction

```json
{ "type": "GIVE_ITEM", "item_id": "key", "count": 1 }
```

`type` 为动作类型，`params` 为其余键值对（自动从原始 dict 剔除 `type` 后作为动作参数）。
