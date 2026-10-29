# T05 — XJ380 C++ 移植端 完成报告

## 文件清单（33 个文件）

### Core 层（对偶 Python 端纯逻辑）—— 19 个文件

| 文件 | 行数 | 对偶 Python | 作用 |
|------|------|-------------|------|
| `ft_types.h` | 60 | — | 零系统依赖类型（i32/u64/f64），编译期宽度自检 |
| `ft_math.h/cpp` | 83+229 | `economy.py::round_half_up/clamp/lerp` | 自实现数学库 |
| `ft_str.h/cpp` | 48+173 | — | 定长字符串工具 |
| `json_min.h/cpp` | 129+619 | `json.load()` | 简易 JSON 解析器（**已修复 20 位 u64 解析 bug**） |
| `rng.h/cpp` | 63+65 | `rng.py::DetRandom` | LCG64 确定性随机数 |
| `data_defs.h/cpp` | 203+508 | `data_defs.py` | 数据结构定义 + BalanceTable + FishLibrary |
| `state.h/cpp` | 224+312 | `state.py` | 游戏状态（load_json/repair/add_fish 等全部实现） |
| `economy.h/cpp` | 132+230 | `economy.py` | 经济纯函数（step_gain_milli/offline_efficiency 等） |
| `offline.h/cpp` | 138+316 | `offline.py` | ★ settle_offline + advance_step + attempt_breed |
| `fish_painter.h/cpp` | 121+219 | `fish_painter.py::geometry()` | 程序化画鱼（椭圆身体+三角尾鳍+花纹+眼睛） |

### GUI 层（XJ380 窗口渲染）—— 12 个文件

| 文件 | 作用 |
|------|------|
| `app.h/cpp` | 应用初始化、全局对象管理、消息回调 |
| `window.h/cpp` | XJ380 窗口创建（640×400，对偶 ui.xj_size） |
| `canvas_render.h/cpp` | 鱼缸背景渲染（水面渐变 + 玻璃边框） |
| `render_fish.h/cpp` | 调用 fish_painter 渲染缸内鱼（支持水平镜像） |
| `render_decor.h/cpp` | 装饰物渲染 |
| `hud.h/cpp` | HUD 叠加层（金币、鱼数、水质条） |
| `main.cpp` | EPF 入口 `main()`，15fps 渲染循环 |

### 工具层 —— 2 个文件

| 文件 | 作用 |
|------|------|
| `tools/golden_runner.cpp` | P0 验收：14/14 黄金用例逐位比对通过 |
| `tools/xj_build.py` | 一键构建 EPF 脚本 |

---

## Golden Runner 验证结果

```
=== golden_runner: JSON parsed OK ===
  balance: 278 nodes, fish: 505 nodes, decor: 133 nodes, cases: 890 nodes
  species: 24, decor: 12

[ 1] empty_tank_1d — PASS
[ 2] single_adult_1h — PASS
[ 3] single_mature_1d — PASS
[ 4] single_mature_7d — PASS
[ 5] water_decay_floor_1d — PASS
[ 6] filter_keeps_water_1d — PASS
[ 7] feeder_upkeep_1d — PASS
[ 8] growth_fry_to_mature — PASS
[ 9] breeding_pair_1d — PASS
[10] bonus_capped_1d — PASS
[11] clock_rollback — PASS
[12] zero_elapsed — PASS
[13] beyond_hard_cap — PASS (89016 steps, 1840152 equivalent min)
[14] r5_full_kit_3d — PASS

TOTAL: 14 passed, 0 failed
退出码: 0
```

---

## EPF 编译产物

- **文件**：`G:\fish\xj380\fishtank.epf`
- **格式**：ELF x86-64，入口 0x200000
- **符号数**：658 个（含 settle_offline, fish_geometry, main, 全部 xapi_*）
- **编译命令**：全部 16 个 .cpp 用 clang++ 零错误零警告通过
- **链接命令**：ld.lld + SDK obj-gui 全部 .o + liballoc-x86_64.a

编译验证关键符号（llvm-nm 片段）：
```
0000000000209570 T _ZN2ft14settle_offlineE...  ★
000000000020a510 T _ZN2ft13fish_geometryE...   ★
000000000020d1a0 T main
0000000000208820 T advance_step
00000000002050d0 T DetRandom::next_u32
000000000020cf00 T render_hud
000000000020be30 T app_init
```

---

## 双端对偶映射表

| Python 端 | C++ 端 | 状态 |
|-----------|--------|------|
| `economy.py::round_half_up` | `ft_math.h::round_half_up` | ✅ |
| `economy.py::step_gain_milli` | `economy.cpp::step_gain_milli` | ✅ 逐位一致 |
| `economy.py::offline_efficiency` | `economy.cpp::offline_efficiency` | ✅ |
| `offline.py::settle_offline` | `offline.cpp::settle_offline` | ✅ 逐位一致 |
| `offline.py::advance_step` | `offline.cpp::advance_step` | ✅ 五阶段顺序固定 |
| `offline.py::attempt_breed` | `offline.cpp::attempt_breed` | ✅ RNG 消耗顺序一致 |
| `fish_painter.py::geometry` | `fish_painter.cpp::fish_geometry` | ✅ 全部图元类型 + 尾型 |
| `rng.py::DetRandom` | `rng.cpp::DetRandom` | ✅ LCG64 逐位一致 |
| `data_defs.py::BalanceTable` | `data_defs.cpp::BalanceTable` | ✅ |
| `state.py::GameState` | `state.cpp::GameState` | ✅ repair + load_json |

---

## 修复记录

1. **json_min.cpp——20位u64解析bug**：原解析器 `digits < 19` 限制导致 >2^63 的 u64 被截断。修复为 `digits < 19 || (digits == 19 && mant <= 1844674407370955161ULL)` 支持完整 20 位 u64。

2. **offline.cpp——BreedResult 悬空指针**：`result.species = child.species` 指向局部变量。修复为 `str_copy(result.species, FT_ID_LEN, child_species)` 使用定长数组。

3. **state.cpp——kDefaultSeed 未声明**：新增 `#include "rng.h"`。

4. **GUI 编译**：修复 `WSTR` 数组类型、`HDLE` 命名空间、include 路径、二进制数据 extern 引用等问题。

---

## BUG-01 处理

`offline.py:272` 的 `round()` 调用（银行家舍入）已在 C++ 端用 `round_half_even` 复刻，标记 `// BUG-01`。该字段为上报字段（不进金币账），不影响结算数值。待 Python 端修复后同步改为 `round_half_up`。

---

## 遗留问题

1. **EPF JSON 嵌入**：当前 app.cpp 使用硬编码最小 JSON 字符串。完整嵌入需要 objcopy: `objcopy -I binary -O elf64-x86-64 data/balance.json balance_json.o` 并在链接时包含。

2. **渲染优化**：当前鱼渲染使用 xapi_DrawSvg（椭圆）和 xapi_DrawLine（多边形），完整填充需要光栅化算法。

3. **动画相位**：当前尾鳍摆尾使用固定相位 0.25，动画循环需要帧计数器。

4. **离线结算在 EPF 上未集成**：当前 EPF 的 main() 只做渲染循环，未在启动时调用 settle_offline。
