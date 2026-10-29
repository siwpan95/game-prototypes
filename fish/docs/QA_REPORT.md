# QA 独立回归测试报告

> **测试人**：严过关（Yan）— QA 工程师
> **测试日期**：2025-07-11
> **测试文件**：`tests/test_qa_offline_contract.py`（78 个用例）
> **被测模块**：`fishtank/offline.py` — 离线结算 `settle_offline()`
> **依据文档**：ARCHITECTURE.md §5.2（离线结算算法）、§11（铁律）、PRD.md L2/L7

---

## 1. 执行结果总览

### 1.1 全量测试套件

```
python -m pytest -p no:cacheprovider --tb=line
```

| 指标 | 数值 |
|------|------|
| 通过 (passed) | 340 |
| 跳过 (skipped) | 1 |
| 预期失败 (xfailed) | 2 |
| **总计** | **343** |
| 耗时 | 99.92s |

### 1.2 QA 独立测试文件（单独执行）

```
python -m pytest tests/test_qa_offline_contract.py -v
```

| 指标 | 数值 |
|------|------|
| 通过 (passed) | 76 |
| 预期失败 (xfailed) | 2 |
| **总计** | **78** |
| 耗时 | 8.68s |

### 1.3 C++ core 层编译验证

```
g++ -c -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -ffp-contract=off \
  -I . data_defs.cpp ft_math.cpp ft_str.cpp json_min.cpp rng.cpp
```

| 指标 | 结果 |
|------|------|
| 退出码 | 0 |
| 警告 | 0 |
| 错误 | 0 |
| 产物 | 5 个 .o |

---

## 2. 测试覆盖矩阵

QA 独立编写的 78 个用例覆盖 8 大契约维度，从 ARCHITECTURE §5.2 与 PRD L2/L7 **重新独立推导**预期值，不复用工程师 `test_offline_golden.py` 的任何断言（"第二套算法"交叉验证）。

| # | 契约维度 | 测试类 | 用例数 | 状态 | 说明 |
|---|---------|--------|--------|------|------|
| A1 | 步长规划（步数总和=离线时长、无步跨 24h/效率边界） | `TestStepPlan` | 4 方法（18 展开用例） | ✅ 通过 | 双层定步长精确性 |
| A2 | 效率分段（边界归属、永不为零/负、单调非增） | `TestEfficiencySegments` | 3 方法（9 展开用例） | ✅ 通过 | 左闭右开区间验证 |
| A3 | L7 黄金数值（1天=17.6h、7天=68h、比值≥3.86） | `TestL7GoldenNumbers` | 4 方法（4 展开用例） | ✅ 通过 | QA 手算交叉验证 |
| A4 | uid 顺序不变性（金币逐厘相同、全状态逐字节相同） | `TestUidOrderInvariance` | 3 方法（3 展开用例） | ✅ 通过 | 浮点累加顺序敏感性 |
| A5 | 取整契约（round_half_up 匹配 C++ floor(x+0.5)） | `TestRoundingContract` | 5 方法（24 展开用例） | ✅ 通过 | 含负半整数完整对照表 |
| A6 | 极端输入（0秒、时钟回拨、空缸、满缸、10年） | `TestExtremeInputs` | 9 方法（13 展开用例） | ✅ 通过 | 不崩/不溢出/不丢币 |
| A7 | 纯度与 carry（不修改输入、链式不丢收益） | `TestPurityAndCarry` | 5 方法（5 展开用例） | ✅ 通过 | 纯函数性 + 锚点精确性 |
| A8 | 禁用 round 铁律（静态守门 + 动态验证） | `TestIronRuleNoBuiltinRound` | 2 方法（2 展开用例） | ⚠️ xfail | **BUG-01** 已标记 |

### 覆盖维度说明

- **A1 步长规划**：验证 S1 分步计划的所有步长之和恰好等于 `away_sec`（一秒不丢/不多），且无任何一步跨越 24h 边界和效率分段边界（8h / 24h）。7 天离线 = 1440 个 60s 细步 + 144 个 3600s 粗步 = 1584 步。
- **A2 效率分段**：边界值归属后一段（左闭右开）；效率永远 > 0（L7 硬指标）；效率随时长单调不增（无套利空间）。
- **A3 L7 黄金数值**：QA 手算 1 天 = 480×1.0 + 960×0.6 = 1056 分 = 17.6h；7 天 = 1056 + 8640×0.35 = 4080 分 = 68.0h；比值 = 3.8636… ≥ 3。离线越久收益单调不减。
- **A4 uid 顺序不变性**：同一鱼群不同插入顺序 → 金币逐厘相同（`==`，非 `approx`）；整份序列化状态逐字节相同。
- **A5 取整契约**：`round_half_up(x)` 必须等于 `int(math.floor(x + 0.5))`；在正偶数+0.5 处与内置 `round` 不同；负半整数完整对照表钉死易错点。
- **A6 极端输入**：0 秒不结算；时钟回拨不动锚点不丢币（L2 端到端验证：回拨→恢复→收益分毫不少）；空缸不崩；24 条满缸不突破容量；10 年离线不溢出/不触保险丝。
- **A7 纯度与 carry**：`settle_offline` 不修改入参 state；同入参 5 次调用结果完全相同；连续 10×60s 结算 == 一次 600s 结算（无取整损耗）；锚点精确到秒。
- **A8 禁用 round 铁律**：AST 静态扫描结算路径源码中不得出现裸 `round(` 调用；动态构造 upkeep 恰好为 x.5 厘的一步验证进位方向。**两个用例均 xfail，对应 BUG-01。**

---

## 3. 发现的问题清单

### BUG-01：`offline.py:272` 使用内置 `round()`（银行家舍入），违反铁律

| 属性 | 详情 |
|------|------|
| **编号** | BUG-01 |
| **严重度** | 中（Medium） |
| **类型** | 双端数值一致性缺陷 |
| **文件** | `fishtank/offline.py` |
| **行号** | 272 |
| **状态** | 已用 `xfail(strict=True)` 标记，待修复 |

#### 问题代码

```python
# fishtank/offline.py:272
out["upkeep_milli"] = int(round(
    feeder_upkeep_rate_milli(state.fish_count(), bal)
    * (step_sec / 60.0) * float(efficiency)))
```

#### 违反的规则

- **ARCHITECTURE.md §11 铁律第 6 条**："取整统一 `floor(x + 0.5)` —— Python 禁用 `round()`（银行家舍入），C++ 禁用 `std::round()`。"
- **ARCHITECTURE.md §10 取整规则**："统一 `floor(x + 0.5)`。Python：`math.floor(x + 0.5)`；C++：`(long long)(x + 0.5)`。"
- **TASKS.md §2.4**："`round_half_up(x) = math.floor(x + 0.5)`（禁用内置 `round()`）。"

#### 根因分析

Python 内置 `round()` 采用**银行家舍入**（IEEE 754 round-half-to-even）：恰好 .5 时向最近偶数靠。而项目铁律要求 **round-half-up**（`floor(x+0.5)`）：恰好 .5 时一律向上。两者在**正偶数+0.5**处产生差异：

| 输入 | `round()`（银行家） | `round_half_up()`（铁律） | 差异 |
|------|---------------------|--------------------------|------|
| 0.5 | 0 | 1 | ❌ |
| 2.5 | 2 | 3 | ❌ |
| 4.5 | 4 | 5 | ❌ |

#### 影响

- `upkeep_milli`（自动投食器维护费）是离线结算报告的上报字段。
- 虽不直接进入金币账（`coins_milli`），但 C++ 端（XJ380）若按铁律用 `floor(x+0.5)` 实现，则**双端 upkeep 数值不一致**，违反 P1-13"双端逐位一致"核心卖点。
- 触发条件：当 `feeder_upkeep_rate_milli × (step_sec/60) × efficiency` 恰好落在 x.5（x 为偶数）时。

#### 修复方案

`fishtank/economy.py` 已定义 `round_half_up(x)` 函数（= `math.floor(x + 0.5)`），但 `offline.py` 未导入它。修复方式二选一：

**方案 A（推荐）**：导入并使用项目规范函数

```python
# 第 47-51 行：在 import 中加入 round_half_up
from fishtank.economy import (
    BonusCache, auto_feed, feeder_upkeep_rate_milli, offline_efficiency,
    rarity_at, rarity_index, round_half_up, stage_of, stage_reached,
    step_gain_milli, step_satiety, step_water,
)

# 第 272 行：改用 round_half_up
out["upkeep_milli"] = int(round_half_up(
    feeder_upkeep_rate_milli(state.fish_count(), bal)
    * (step_sec / 60.0) * float(efficiency)))
```

**方案 B**：直接用 `math.floor`

```python
import math  # 需在文件头部添加

out["upkeep_milli"] = int(math.floor(
    feeder_upkeep_rate_milli(state.fish_count(), bal)
    * (step_sec / 60.0) * float(efficiency) + 0.5))
```

修复后需**删除** `TestIronRuleNoBuiltinRound` 类中两个 `@pytest.mark.xfail` 标记，使其变为永久守门测试。

#### 全项目 `round(` 调用排查结果

| 位置 | 代码 | 是否 Bug | 说明 |
|------|------|----------|------|
| `offline.py:272` | `int(round(feeder_upkeep_rate_milli(...) * ...))` | **是（BUG-01）** | 结算路径，违反铁律 |
| `state.py:77` | `round(float(v), FLOAT_NDIGITS)` | 否 | 鱼坐标序列化的 6 位小数四舍五入，不参与结算数值 |
| `economy.py:31` | 注释中提及 round 的危害 | 否 | 文档性说明，非调用 |

---

## 4. 通过率统计

### 4.1 QA 独立测试文件

```
78 个用例：76 passed, 2 xfailed
通过率（排除 xfail）：76/76 = 100%
通过率（含 xfail 计失败）：76/78 = 97.4%
```

### 4.2 全量测试套件

```
340 passed, 1 skipped, 2 xfailed
通过率（排除 xfail/skip）：340/341 = 99.7%
通过率（含 xfail 计失败）：340/343 = 99.1%
```

### 4.3 C++ core 层

```
编译通过率：100%（零警告零错误）
```

---

## 5. 遗留风险

| # | 风险项 | 严重度 | 状态 | 缓解措施 |
|---|--------|--------|------|----------|
| R1 | BUG-01 未修复：`upkeep_milli` 双端可能不一致 | 中 | 待工程师修复 | xfail 已标记；修复方案已给出；修复后守门测试自动激活 |
| R2 | `state.py:77` 使用 `round(float(v), 6)` 做坐标序列化 | 低 | 已确认为非 Bug | 坐标 6 位小数舍入不参与结算数值，不影响双端一致性；如需彻底消除可后续改为截断 |
| R3 | C++ 端（XJ380）离线结算尚未实现对偶测试 | 中 | 待后续阶段 | 当前仅验证 core 层编译通过；双端对偶测试待 C++ offline.cpp 实现后补充 |
| R4 | 1 个 skipped 测试原因未追踪 | 低 | 待确认 | 不影响核心路径，建议后续确认 skip 原因 |

---

## 6. 智能路由判定

### 判定逻辑

| 条件 | 判定 | 本案 |
|------|------|------|
| 所有测试通过 | → NoOne（无需路由） | ❌ |
| 测试断言正确但源码输出错误 | → Engineer（源码 Bug） | ✅ |
| 测试断言本身错误 | → QA（自修复测试） | ❌ |

### 判定结论

QA 独立测试中 2 个 xfail 用例（`TestIronRuleNoBuiltinRound`）的断言是**正确的**——它们验证的是铁律要求的正确行为（`round_half_up`），而源码 `offline.py:272` 的实现是**错误的**（用了内置 `round`）。测试无误，源码有 Bug。

```
ROUTE: Engineer
```

**路由目标**：Python 工程师（Alex）
**路由内容**：修复 `fishtank/offline.py:272` 的内置 `round()` 调用，改为 `round_half_up()`（方案 A）或 `math.floor(x + 0.5)`（方案 B），修复后删除 `tests/test_qa_offline_contract.py` 中 `TestIronRuleNoBuiltinRound` 类的两个 `@pytest.mark.xfail` 标记。
**预期结果**：修复后 78 个用例全部通过（0 xfail），全量套件变为 342 passed / 1 skipped / 0 xfailed。

---

## 7. 测试方法学说明

### 7.1 独立交叉验证策略

本测试文件**不复用**工程师 `test_offline_golden.py` 的任何断言，而是：
- 从 ARCHITECTURE §5.2 伪代码和 PRD L2/L7 准则**重新独立推导**预期值
- 用 QA 自写的"第二套算法"（`qa_reference_equiv_minutes`、`qa_expected_step_plan`）交叉验证实现
- 文档里写死的数（17.6 / 68.0 / 3.86）全部**自己重算一遍**，不直接抄

### 7.2 测试设计亮点

- **参数化覆盖**：边界值（0/1/59/60/61/3599/3600/DAY±1）、极端值（10 年/hard_cap+100天）、舍入表（12 正数 + 5 鉴别 + 4 负半整数）
- **端到端场景**：时钟回拨→恢复→收益分毫不少（L2 关键路径）
- **静态守门**：AST 扫描源码中裸 `round(` 调用，修复后成为永久防线
- **纯函数性验证**：`settle_offline` 不修改入参、确定性可重复、锚点精确到秒
- **浮点顺序敏感性**：不同插入顺序 → 金币逐厘相同（`==`），全状态逐字节相同

### 7.3 QA 自查记录

测试编写过程中发现并修正的问题（已记录在测试注释中）：
- 负半整数 `-0.5` / `-2.5` 在 `round_half_up` 与 `round` 下**恰好相同**，无鉴别力；差异只出现在**正偶数+0.5**上，故收敛鉴别样本到 `[0.5, 2.5, 4.5, 6.5, 100.5]`。
- 完整负半整数对照表（`test_negative_half_rounding_table`）钉死此易错点，避免后人重蹈。

---

*报告结束*
