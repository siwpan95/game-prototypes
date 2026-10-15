"""红石信号引擎：**布局决定信号**（与 Phase 2-A 的光照同构）。

## 一、信号强度为什么**不进存档**

红石线不存在 16 个 id，强度由**布局**算出来（`PowerGrid.power`）。这与光照同口径：

* 存档只存"玩家放了什么方块"（拉杆开/关、门开/关这类**状态是方块 id**，自然进档）；
* 信号是**派生状态** —— 读档后按布局重算，一定与放置时一致；
* 所以**老档不用升级**（v3 不变），也不会出现"存档里写了强度 12 但布局其实不通电"。

## 二、元件（id 见 `blocks`）

| 角色 | 方块 | 行为 |
| --- | --- | --- |
| 电源 | `LEVER_ON` / `BUTTON_ON` / `REDSTONE_TORCH` | 自身格 = 15 |
| 传输 | `REDSTONE_WIRE` | 每走一格 −1（降到 0 就断） |
| 传输 | `REPEATER_ON` | **续满 15**（红石线 15 格就衰减到 0，长线路靠它） |
| 输出 | `LAMP_ON` | 亮 ⇒ 同时是光源（`emissive=1.0`，走 Phase 2-A 光照） |
| 输出 | `DOOR_OPEN_*` | 能穿过去（`solid=False`） |
| 输出 | `PISTON_*_ON` | 伸出臂 + 推方块 |

## 三、传播规则（三条，都能穷举测试）

1. **只有红石线继续传导**（每格 −1）；中继器 ON 是**新的 15 级源**，所以它能续接。
2. **输出的输入 = 六邻格里最大的信号**（≥1 就触发）。灯/门/活塞**不导电**
   —— 它们不会把信号传下去（MC 同款）。
3. 中继器 ON 的判据也是"六邻有电"⇒ 中继器 → 线 → 中继器 → 线 的链会**逐轮点亮**，
   所以重算要**迭代到固定点**（下面 §四）。

## 四、重算：按**网络**，不是按空间盒子

光照引擎用"空间盒子 + halo"（因为光会往各个方向衰减）。红石不一样：
它只在**连通的元件网络**上走。所以这里的口径是：

```
从变化点出发，找连通的"元件格"（红石线 / 中继器 / 电源 / 输出）
→ 重算这批格 + 它们的邻居
```

好处是**精确**：长线路（几十格、带中继器）也能一次算对，不会像"半径 16 的盒子"
那样在中继器处被截断。代价是网络可能很大 ⇒ 有 `NETWORK_CAP` 护栏，
超了**响亮抛错**（同 `LightOverflow` 的思路：绝不静默截断）。

迭代到固定点：每轮"清空 → 传播 → 切输出"，输出有变化就再来一轮。
状态是有限的（每个元件只有开/关），所以必然收敛；`MAX_ITER` 只是护栏。

## 五、元件 tick 队列：把"延迟"从迭代里挪到时间轴上（Phase 3-B）

初版所有元件都是**瞬时**的：一次 `recompute_from` 内迭代到固定点，输出立刻变。
于是**做不出任何带时间的东西** —— 最短的脉冲也被拉平，更别说时钟。

现在多了一层**元件 tick 队列**（`PowerGrid.events`，最小堆）：

* 中继器**不再立刻翻转**：输入与输出不一致时 `_schedule(cell, delay)` 排一个事件，
  `delay` 由**档位**决定（`blocks.REPEATER_DELAYS` = 0.1/0.2/0.3/0.4 秒，MC 的四档）；
* `step(dt)` 推进 `self.now`，把到期事件**逐个触发**；
* 于是"固定点迭代"只需处理**瞬时**元件（灯/门/活塞/火把），中继器的翻转发生在**时间轴**上。

### 触发时**重新读世界**，而不是把结果存进队列

队列里只存 `(到期时刻, 格子)`，**不存"该变成什么"**。触发时按**当前**输入重新判断：

```python
want = 背面有电吗       # 现在读
if want != 当前状态: 翻转
```

为什么：延迟期间输入可能已经变回去（短脉冲）。存"目标状态"的话，队列会忠实执行一个
**现实中不存在的脉冲**（"按下又松开，0.4 秒后灯还是闪了一下"）。惰性求值天然把这种
短脉冲吃掉 —— 这正是"脉冲整形"的物理来源。

### 性能护栏

环形结构（时钟）会**源源不断**产生事件 ⇒ `TICK_EVENTS_CAP` 限制一次 `step` 内触发的事件数，
超了抛 `RedstoneOverflow`（同光照/网络的思路：**绝不静默截断**）。
另外"同刻事件按**入队序号**处理"（堆元素带自增序号）⇒ 不依赖 dict 迭代顺序，可重放。

## 六、红石火把是**反相器**（Phase 3-B）

初版火把只是个"常亮电源"。真实的 MC 火把是**反相器**：脚下那块被强充能时自己熄灭
（`redstone_torch` ↔ `redstone_torch_off` 两个状态 id）。

**什么算"强充能"**（`strongly_powered`）：只有**元件**能强充能，红石线不行：

* 六邻里有 `LEVER_ON` / `BUTTON_ON` ⇒ 本格被强充能；
* 六邻里有 `REPEATER_ON` 且**本格就是它的正面那一格** ⇒ 被强充能。

⚠ **火把自己不强充能任何东西** —— 这一条是反相器不会自锁的全部原因：

```
错误做法（会自锁）：火把"六邻有电就熄灭"
  火把亮 → 自己邻居的线有电 → 判定"有电" → 熄灭 → 没电 → 亮 → …（固定点迭代永不收敛）

现在的做法：火把只看**脚下**是否被元件强充能
  火把的输出只能进红石线（弱充能）⇒ 永远改不动自己的睡眠条件 ⇒ 不会自锁
```

**于是时钟才成立**：反相器（瞬时）+ 中继器（延迟）= 环形振荡器。
`t_clock` 就是"中继器 → 前方实心块 → 块上的火把 → 线绕回中继器背面"的环，
周期 = `2 × 档位延迟`（0.1s 档 ⇒ 5Hz），灯一闪一闪。

## 七、状态切换走 `set_generated`（不记存档增量）

红石驱动的变化（灯亮、门开、活塞推）是**派生状态**，不写进存档增量：

* 存档里存的是"玩家放的 `lamp_off` / `door_lower`"；
* 读档后按同一套布局重算 ⇒ 得到同样的亮/开/推结果（单测钉住）。

⚠ 一个必须写明的后果：**被活塞推走的方块不在存档里**（它的新位置是算出来的）。
读档后活塞若仍通电，会**再推一次**得到同样结果；若玩家把活塞拆了，
被推的方块会"回到"存档记录的位置（因为它根本没被记录移动过）。
这与"改结构规则老档会变"是同一性质，见设计稿。
"""

from __future__ import annotations

import heapq

from . import blocks as B

__all__ = ['MAX_POWER', 'NETWORK_CAP', 'MAX_ITER', 'PUSH_LIMIT', 'BUTTON_TTL',
           'TICK_EVENTS_CAP',
           'PowerGrid', 'RedstoneOverflow',
           'is_source', 'is_component', 'is_conductor', 'is_output', 'is_piston',
           'is_lamp', 'is_door', 'is_pushable', 'piston_input_on',
           'is_repeater', 'repeater_dir', 'repeater_face', 'repeater_front']

#: 信号最大值（与 MC 同为 15）
MAX_POWER = 15
#: 一次重算的网络格数上限（护栏；超了抛 `RedstoneOverflow`，绝不静默截断）
NETWORK_CAP = 30000
#: 固定点迭代上限（状态有限 ⇒ 必然收敛，这是护栏不是算法）
MAX_ITER = 8
#: 活塞一次最多推几格（用户拍板："连锁推 12 格"）
PUSH_LIMIT = 12
#: 按钮按下后多久自动回弹（秒）。MC 是 1 秒（石按钮）/0.5 秒（木按钮），取 1.0
BUTTON_TTL = 1.0
#: 一次 `step` 里最多触发多少个元件事件（护栏）。环形结构（时钟）会**源源不断**产生事件，
#: 没有这个上限的话"一个环里套了 0 延迟事件"会让 `step` 永远出不来。
TICK_EVENTS_CAP = 512
#: 时间比较容差（秒）。**必须留**：`self.now` 是逐帧累加出来的浮点数，
#: 累到几百帧后会比重排的时刻**略小**（`0.05 × 6` 累加得到 `0.30000000000000004`，
#: 而另一条路径算出 `0.29999999999999993`）⇒ 严格的 `due <= now` 会让事件**晚一帧**触发。
#: 而晚一帧不是"抖一下"：它把后续所有事件都推后一帧 ⇒ **相位永久滑移**
#: （实测：1 档时钟的翻转间隔从 2 帧漂到 3 帧，周期 0.2s → 0.3s）。
_T_TIME_EPS = 1e-6

#: 六邻（红石传播用）
_NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

#: 活塞推不动的方块（红石元件会被推走的话状态立刻混乱；基岩/水/作物同理）
_UNPUSHABLE = frozenset({
    B.AIR, B.BEDROCK, B.WATER, B.CROP, B.TORCH,
    B.REDSTONE_WIRE, B.LEVER_OFF, B.LEVER_ON, B.BUTTON_OFF, B.BUTTON_ON,
    B.REDSTONE_TORCH, B.REDSTONE_TORCH_OFF,
    B.REPEATER_OFF, B.REPEATER_ON, B.LAMP_OFF, B.LAMP_ON,
    B.DOOR_LOWER, B.DOOR_UPPER, B.DOOR_OPEN_LOWER, B.DOOR_OPEN_UPPER,
    B.PISTON_ARM,
} | {off for (_n, off, _on) in B.PISTON_STATES}
      | {on for (_n, _off, on) in B.PISTON_STATES}
      # 中继器现在有 32 个状态 id（4 方向 × 4 档 × 开/关）⇒ 由表生成，手写必漏
      | {off for (_d, _n, off, _on) in B.REPEATER_STATES}
      | {on for (_d, _n, _off, on) in B.REPEATER_STATES})


class RedstoneOverflow(RuntimeError):
    """一次重算的网络过大（护栏，见模块 docstring §四）。"""


# ---------------------------------------------------------------- 元件分类
def is_source(bid: int) -> bool:
    """**此刻在供电**的电源（拉杆开 / 按钮按下 / 亮着的红石火把）。

    ⚠ 熄灭的火把（`REDSTONE_TORCH_OFF`）不算 —— 但它仍然属于网络，
    见 `is_component`。
    """
    return int(bid) in (B.LEVER_ON, B.BUTTON_ON, B.REDSTONE_TORCH)


def is_component(bid: int) -> bool:
    """是不是"红石元件"（网络成员，含**熄灭的火把**与关着的拉杆）。

    与 `is_source` 的区别很实在：`mark()` / `_collect_network()` 关心的是
    "这一格改了要不要重算"，而**灭掉的火把**正是最需要重算的那种格
    （它的睡眠条件是算出来的，脚下被充能时它必须醒过来）。
    """
    b = int(bid)
    return (is_source(b) or b == B.REDSTONE_TORCH_OFF
            or is_conductor(b) or is_output(b))


def is_conductor(bid: int) -> bool:
    """会不会**传导**信号（只有红石线）。

    ⚠ 中继器**不算传导者**：它是"有向的源"（背面吃、正面吐），
    把它算成传导者会让它给自己供电（见 `is_repeater` 的说明）。
    """
    return int(bid) == B.REDSTONE_WIRE


def is_repeater(bid: int) -> bool:
    """是不是中继器（四个朝向 × 开/关都算）。"""
    return int(bid) in B.REPEATER_DIR_OF


def repeater_dir(bid: int):
    """中继器的**输出方向**（正面）；不是中继器 ⇒ None。"""
    return B.REPEATER_DIR_OF.get(int(bid))


def repeater_face(coord, bid: int):
    """中继器的**输入面**坐标（背面）；不是中继器 ⇒ None。"""
    d = repeater_dir(bid)
    if d is None:
        return None
    vx, vy, vz = B.PISTON_DIR_VEC[d]
    return (coord[0] - vx, coord[1] - vy, coord[2] - vz)


def repeater_front(coord, bid: int):
    """中继器的**输出面**坐标（正面）；不是中继器 ⇒ None。"""
    d = repeater_dir(bid)
    if d is None:
        return None
    vx, vy, vz = B.PISTON_DIR_VEC[d]
    return (coord[0] + vx, coord[1] + vy, coord[2] + vz)


def is_piston(bid: int) -> bool:
    return int(bid) in B.PISTON_DIR_OF


def is_lamp(bid: int) -> bool:
    return int(bid) in (B.LAMP_OFF, B.LAMP_ON)


def is_door(bid: int) -> bool:
    return int(bid) in (B.DOOR_LOWER, B.DOOR_UPPER, B.DOOR_OPEN_LOWER,
                        B.DOOR_OPEN_UPPER)


def is_output(bid: int) -> bool:
    """是不是"被信号驱动的东西"（灯 / 门 / 活塞 / 中继器 / **红石火把**）。

    火把也算：它是**反相器** —— 亮/灭由"脚下是否被强充能"决定（见模块 docstring §六）。
    不放进这里的话它永远不会被重算，反相就无从发生。
    """
    b = int(bid)
    return (is_lamp(b) or is_door(b) or is_piston(b) or is_repeater(b)
            or b in (B.REDSTONE_TORCH, B.REDSTONE_TORCH_OFF))


def is_pushable(bid: int) -> bool:
    """活塞能不能推动这个方块。"""
    b = int(bid)
    return b != B.AIR and b not in _UNPUSHABLE and B.is_solid(b)


def piston_input_on(bid: int) -> bool:
    return int(bid) in (on for (_n, _off, on) in B.PISTON_STATES)


# ---------------------------------------------------------------- 引擎
class PowerGrid:
    """红石网络：信号强度（dict，只存非零）+ 脏格 + 按钮回弹计时。"""

    __slots__ = ('world', 'power', 'dirty', 'pending', 'on_change', 'stats',
                 'now', 'events', 'sched', '_seq')

    def __init__(self, world, on_change=None):
        self.world = world
        #: `(x,y,z) -> 1..15`（只存非零 —— 红石网络天然稀疏）
        self.power: dict[tuple, int] = {}
        #: 需要重算的种子格（变化点；重算时会展开成整个网络）
        self.dirty: set = set()
        #: 按钮回弹倒计时：`(x,y,z) -> 剩余秒数`
        self.pending: dict[tuple, float] = {}
        #: 方块被红石改动后的回调（内核用它标脏网格 + 让光照失效）
        self.on_change = on_change
        # --- Phase 3-B：元件 tick 队列（见模块 docstring §五）---
        #: 元件时间轴（秒），由 `step(dt)` 推进。**不进存档**（派生状态）
        self.now = 0.0
        #: 事件堆：`(到期时刻, 入队序号, 格子)`。用**自增序号**打破同刻并列
        #: ⇒ 处理顺序不依赖 dict/set 的迭代顺序，可重放
        self.events: list = []
        #: `格子 -> 到期时刻`（去重：同一格同时只挂一个待触发事件）
        self.sched: dict[tuple, float] = {}
        self._seq = 0
        self.stats = {'recompute': 0, 'cells': 0, 'switched': 0, 'buttons': 0,
                      'scheduled': 0, 'fired': 0}

    # ------------------------------------------------------------ 查询
    def power_at(self, x: int, y: int, z: int) -> int:
        return self.power.get((int(x), int(y), int(z)), 0)

    def input_at(self, x: int, y: int, z: int) -> int:
        """这一格"收到的信号" = **六邻里最大的信号**（自己那格不算）。"""
        best = 0
        for (dx, dy, dz) in _NEIGHBORS:
            v = self.power.get((x + dx, y + dy, z + dz), 0)
            if v > best:
                best = v
        return best

    # ------------------------------------------------------------ 记账
    def mark(self, x: int, y: int, z: int):
        """记下"这一格附近变了"（放置 / 挖掘 / 交互后调）。

        ⚠ 只把**变化点本身**与**六邻里的元件格**排进队列：
        早先无脑把六邻全塞进去，空气格会永远留在 `dirty` 里
        （`recompute_from` 只清理"网络内的格"）⇒ 每帧都在做无用重算。
        变化点本身必须留着 —— 它可能"刚被挖掉"（已经是空气），
        但正是它把两侧的网络断开了，重算要从它出发找两侧。
        """
        p = (int(x), int(y), int(z))
        self.dirty.add(p)
        for (dx, dy, dz) in _NEIGHBORS:
            n = (p[0] + dx, p[1] + dy, p[2] + dz)
            b = self.world.get(*n)
            if is_component(b):          # ⚠ 用 is_component：**灭的火把**也必须能被重算到
                self.dirty.add(n)
        # ⚠ 还要多看一层：**红石火把的睡眠条件看的是"脚下那格是否被强充能"**，
        #   而强充能又取决于脚下那格的六邻 —— 于是"变化点自己 + 它的六邻"
        #   这 7 格的**上方**若有火把，那个火把也可能要翻状态。
        #   漏掉这一层的话反相器永远不翻（实测：中继器亮了，块上的火把还是亮的）。
        world_get = self.world.get
        for (sx, sy, sz) in (p,) + tuple((p[0] + dx, p[1] + dy, p[2] + dz)
                                         for (dx, dy, dz) in _NEIGHBORS):
            t = (sx, sy + 1, sz)
            if world_get(*t) in (B.REDSTONE_TORCH, B.REDSTONE_TORCH_OFF):
                self.dirty.add(t)

    # ------------------------------------------------------------ 交互
    def toggle_lever(self, x: int, y: int, z: int):
        """拉杆切换开 / 关。返回新的方块 id（不是拉杆 ⇒ None）。"""
        b = self.world.get(x, y, z)
        if b == B.LEVER_OFF:
            new = B.LEVER_ON
        elif b == B.LEVER_ON:
            new = B.LEVER_OFF
        else:
            return None
        self._write(x, y, z, new)
        self.mark(x, y, z)
        return new

    def press_button(self, x: int, y: int, z: int, ttl: float = BUTTON_TTL):
        """按按钮：变按下状态 + 记回弹倒计时。返回新的方块 id（不是按钮 ⇒ None）。"""
        b = self.world.get(x, y, z)
        if b == B.BUTTON_OFF:
            self._write(x, y, z, B.BUTTON_ON)
            self.pending[(int(x), int(y), int(z))] = float(ttl)
            self.mark(x, y, z)
            self.stats['buttons'] += 1
            return B.BUTTON_ON
        if b == B.BUTTON_ON:                     # 已经按着 ⇒ 只把倒计时重置
            self.pending[(int(x), int(y), int(z))] = float(ttl)
            return B.BUTTON_ON
        return None

    def toggle_repeater(self, x: int, y: int, z: int):
        """中继器手动切亮/灭（**只给测试与调试用**）。

        ⚠ 游戏里不给玩家这个入口：亮灭是信号算出来的，手动切会在下一帧被信号纠正
        （`_apply_outputs` 看到"输入与状态不一致"就排事件）⇒ 玩家会觉得"点了没反应"。
        玩家能改的是**档位**（`cycle_repeater_delay`）。
        """
        b = self.world.get(x, y, z)
        if b not in B.REPEATER_DIR_OF:
            return None
        new = (B.repeater_on_id(b) if b == B.repeater_off_id(b)
               else B.repeater_off_id(b))
        self._write(x, y, z, new)
        self.mark(x, y, z)
        return new

    def cycle_repeater_delay(self, x: int, y: int, z: int):
        """中继器**调档**（1→2→3→4→1 档）。返回新的方块 id（不是中继器 ⇒ None）。

        调档**不改开/关**：如果它正被信号驱动，改完档位状态保持不变，
        但下一次翻转会按新档位的延迟发生（正在排队的那个事件**不重排** ——
        否则"改档位"会把已过的延迟清零，等于偷跑一个瞬发）。
        """
        b = self.world.get(x, y, z)
        if b not in B.REPEATER_DIR_OF:
            return None
        new = B.repeater_cycle_delay(b)
        if new == b:
            return b
        cell = (int(x), int(y), int(z))
        # 旧 id 的排队事件作废（格子没变，但档位变了 ⇒ 重新按新档位排）
        if cell in self.sched:
            del self.sched[cell]
        self._write(x, y, z, new)
        self.mark(x, y, z)
        return new

    @staticmethod
    def delay_label(bid: int) -> str:
        """中继器档位的可读标签（HUD / 日志用）。"""
        n = B.REPEATER_DELAY_OF.get(int(bid))
        return '非中继器' if n is None else f'中继器·{n + 1}档'

    # ------------------------------------------------------------ 每帧
    def step(self, dt: float, budget: int = 2) -> int:
        """推进一步：**推进时间轴** → 按钮回弹 → 触发到期事件 → 处理 `budget` 个脏网络。

        返回被改动的方块数。

        `budget` 是**性能护栏**（同内核的 `LIGHT_BUDGET_PER_FRAME`）：
        一个网络的重算是几十毫秒级，一帧做太多会掉帧。

        顺序有讲究：**先推进时间、再触发事件、最后结算脏网络**
        （触发事件会 `mark()` 出新脏点，必须让它们在**同一帧**里被结算完，
        否则"中继器刚翻转"会晚一帧才传导出去，时钟周期会随帧率漂）。
        """
        self.now += max(0.0, float(dt))
        changed = self._tick_buttons(dt)
        changed += self._fire_due()
        done = 0
        while self.dirty and done < max(1, int(budget)):
            seed = self.dirty.pop()
            changed += self.recompute_from(seed)
            done += 1
        return changed

    # ------------------------------------------------------------ 元件 tick 队列
    def _schedule(self, cell, delay: float) -> bool:
        """把 `cell` 排进 tick 队列（`delay` 秒后触发）。已在队列里 ⇒ 不重复排。

        **去重是必须的**：固定点迭代每轮都会看到"输入与输出不一致"，
        不去重的话会排一堆同刻事件（`MAX_ITER` 轮 × 每轮一个）。
        """
        if cell in self.sched:
            return False
        due = self.now + max(0.0, float(delay))
        self._seq += 1
        heapq.heappush(self.events, (due, self._seq, cell))
        self.sched[cell] = due
        self.stats['scheduled'] += 1
        return True

    def _fire_due(self) -> int:
        """触发所有**到期**事件。返回被改动的方块数。

        ⚠ 循环条件是"堆顶到期"，所以**本轮新排的 0 延迟事件也会被触发** ——
        这是刻意的（延迟可以小到 0），靠 `TICK_EVENTS_CAP` 兜住死循环。
        """
        if not self.events:
            return 0
        changed = 0
        fired = 0
        while self.events and self.events[0][0] <= self.now + _T_TIME_EPS:
            due, _seq, cell = heapq.heappop(self.events)
            if self.sched.get(cell) != due:
                continue                     # 过期条目（这一格被重新排过）
            del self.sched[cell]
            fired += 1
            if fired > TICK_EVENTS_CAP:
                raise RedstoneOverflow(
                    f'一次 step 内触发了超过 {TICK_EVENTS_CAP} 个元件事件 ——'
                    f' 这通常意味着出现了"0 延迟的环"（时钟接在 0 延迟元件上）。'
                    f' 给环里的中继器调一档延迟即可。')
            changed += self._fire_one(cell)
        self.stats['fired'] += fired
        return changed

    def _fire_one(self, cell) -> int:
        """触发一个元件事件：**按当前世界重新判断**要不要翻转（惰性求值）。

        惰性求值是"脉冲整形"的物理来源：延迟期间输入变回去 ⇒ 这里算出 `want == 现值`
        ⇒ 什么都不做。存"目标状态"的做法会凭空造出一个脉冲。
        """
        b = self.world.get(*cell)
        if not is_repeater(b):
            return 0                         # 延迟期间被挖掉 / 换成别的方块
        want_on = self._repeater_input_on(cell, b)
        on = (b == B.REPEATER_ON_OF[int(b)])
        if want_on == on:
            return 0
        self._write(cell[0], cell[1], cell[2],
                    B.repeater_on_id(b) if want_on else B.repeater_off_id(b))
        self.mark(*cell)                     # 新状态要重新传播（同一帧内结算）
        return 1

    def _repeater_input_on(self, cell, bid) -> bool:
        """中继器的**背面**有没有电（有向：背面吃、正面吐）。"""
        back = repeater_face(cell, bid)
        return back is not None and self.power.get(back, 0) >= 1

    def pending_count(self) -> int:
        """队列里还有多少个待触发事件（判据 / HUD 用）。"""
        return len(self.events)

    def run_until_stable(self, *, dt: float = 0.05, max_ticks: int = 200,
                         budget: int = 999) -> int:
        """反复 `step` 直到**没有脏网络也没有待触发事件**（测试与验收用）。

        ⚠ 时钟（环形振荡器）**永远不静止** ⇒ 对它用这个函数会跑满 `max_ticks`。
        这是刻意的：判据里"停下来"和"一直在动"都是要看的事实，函数不替调用方判。
        """
        changed = 0
        for _ in range(max(1, int(max_ticks))):
            if not self.dirty and not self.events:
                break
            changed += self.step(dt, budget=budget)
        return changed

    def _tick_buttons(self, dt: float) -> int:
        if not self.pending:
            return 0
        changed = 0
        expired = []
        for cell, ttl in self.pending.items():
            ttl -= dt
            if ttl <= 0.0:
                expired.append(cell)
            else:
                self.pending[cell] = ttl
        for cell in expired:
            del self.pending[cell]
            x, y, z = cell
            if self.world.get(x, y, z) == B.BUTTON_ON:      # 可能已被玩家挖掉
                self._write(x, y, z, B.BUTTON_OFF)
                changed += 1
            self.mark(x, y, z)
        return changed

    # ------------------------------------------------------------ 重算
    def recompute_from(self, seed) -> int:
        """重算 `seed` 所在的那个红石网络。返回被改动的方块数。"""
        net = self._collect_network(seed)
        if not net:
            return 0
        self.dirty -= net                            # 这批格会被一起算，别再排一遍
        self.stats['recompute'] += 1
        self.stats['cells'] += len(net)
        changed = 0
        for _ in range(MAX_ITER):
            self._clear(net)
            self._propagate(net)
            n = self._apply_outputs(net)
            changed += n
            if n == 0:
                break                               # 固定点
        return changed

    def _collect_network(self, seed) -> set:
        """从 `seed` 出发找出连通的元件格（含输出元件），返回这批格。

        ⚠ 收集时**从 seed 的邻居开始**：`seed` 可能是"刚被挖掉的格子"（现在已经是空气），
        它自己不是元件，但它两侧的网络成员是 —— 不这么写会漏掉断开后的重算。
        """
        world = self.world
        seen = set()
        stack = [tuple(seed)]
        # 先把 seed 的邻居铺开（见 docstring）
        first = tuple(seed)
        for (dx, dy, dz) in _NEIGHBORS:
            stack.append((first[0] + dx, first[1] + dy, first[2] + dz))
        while stack:
            cell = stack.pop()
            if cell in seen:
                continue
            b = world.get(*cell)
            if not is_component(b):      # 同上：灭的火把是网络成员
                continue
            seen.add(cell)
            if len(seen) > NETWORK_CAP:
                raise RedstoneOverflow(
                    f'红石网络超过 {NETWORK_CAP} 格（从 {seed} 出发）——'
                    f' 这通常意味着"一片红石线连成了一个巨型网络"。'
                    f' 放宽 `NETWORK_CAP` 前先想清楚：重算是要遍历整张网络的。')
            for (dx, dy, dz) in _NEIGHBORS:
                stack.append((cell[0] + dx, cell[1] + dy, cell[2] + dz))
        return seen

    def _clear(self, net):
        # 顺手**清理过期条目**：`power` 里只允许留"当前还是元件"的格子。
        # 没有这一条，"通电的线被挖掉""关着的拉杆"会在原地留下**幽灵信号**
        # （实测：松开按钮后中继器背面仍读到 15 ⇒ 短脉冲被当成常亮）。
        # 代价 O(|power|)，而 `power` 只存非零格 ⇒ 稀疏、很便宜。
        for cell in [c for c in self.power
                     if not is_component(self.world.get(*c))]:
            del self.power[cell]
        for cell in net:
            self.power.pop(cell, None)

    def _propagate(self, net):
        """从所有电源（与中继器 ON）出发做 BFS，只在**红石线**上继续走。

        ⚠ **电源给紧邻的线满 15**（不是 14）：这是 MC 的口径 —— 拉杆像"强充能"了
        挨着它的那一格。区别很实在：`MAX_POWER` 级衰减下，14 起步的线只能通 14 格，
        15 起步能通 15 格。中继器 ON 同理（它的本职就是"续满"）。
        """
        world = self.world
        queue = []
        for cell in net:
            b = world.get(*cell)
            # ⚠ `_source_live` 而不是 `is_source`：**灭掉的火把**是一个 id
            #   （`REDSTONE_TORCH_OFF`），但它不是电源 —— 它此刻一个格都不供电
            if self._source_live(cell, b):
                self.power[cell] = MAX_POWER
                queue.append(cell)
            elif is_repeater(b) and b == B.repeater_on_id(b):
                # 中继器 ON：**只给正面那一格**供 15（背面/侧面不给 —— 那正是消除自锁的关键）
                self.power[cell] = MAX_POWER
                front = repeater_front(cell, b)
                if front in net and world.get(*front) == B.REDSTONE_WIRE:
                    if MAX_POWER > self.power.get(front, 0):
                        self.power[front] = MAX_POWER
                        queue.append(front)
        head = 0
        while head < len(queue):
            cell = queue[head]
            head += 1
            lv = self.power.get(cell, 0)
            if lv <= 0:
                continue
            x, y, z = cell
            b = world.get(*cell)
            # 电源往外**满格**供（拉杆像"强充能"了挨着它的那一格），线自己往外 −1
            feed = MAX_POWER if self._source_live(cell, b) else lv - 1
            if feed <= 0:
                continue
            for (dx, dy, dz) in _NEIGHBORS:
                n = (x + dx, y + dy, z + dz)
                if n not in net:
                    continue
                if world.get(*n) != B.REDSTONE_WIRE:      # 只有线继续传导
                    continue
                if feed > self.power.get(n, 0):
                    self.power[n] = feed
                    queue.append(n)

    def _apply_outputs(self, net) -> int:
        """按"六邻最大信号 ≥1"切换**瞬时**输出元件；中继器改为**排队**。返回切换次数。

        瞬时元件 = 灯 / 门 / 活塞 / 红石火把（火把是反相器）。
        中继器**不在**这里翻转 —— 它排进 tick 队列，由 `_fire_due` 在延迟之后处理
        （见模块 docstring §五）。所以这个函数的返回值里**永远没有中继器**，
        固定点迭代才能在"中继器等着翻转"时就收敛。
        """
        changed = 0
        for cell in net:
            b = self.world.get(*cell)
            if not is_output(b):
                continue
            x, y, z = cell
            on = self.input_at(x, y, z) >= 1
            if is_repeater(b):
                # 中继器：**不立刻翻转**，排一个延迟事件（同一格只挂一个）
                if self._repeater_input_on(cell, b) != (b == B.REPEATER_ON_OF[int(b)]):
                    self._schedule(cell, B.repeater_delay(b))
            elif b in (B.REDSTONE_TORCH, B.REDSTONE_TORCH_OFF):
                # 火把是**反相器**：脚下被强充能 ⇒ 熄灭（瞬时，不排队 —— MC 同款）
                want_on = not self.torch_asleep(x, y, z)
                if want_on != (b == B.REDSTONE_TORCH):
                    self._write(x, y, z,
                                B.REDSTONE_TORCH if want_on else B.REDSTONE_TORCH_OFF)
                    changed += 1
            elif is_lamp(b) and on != (b == B.LAMP_ON):
                self._write(x, y, z, B.LAMP_ON if on else B.LAMP_OFF)
                changed += 1
            elif is_door(b):
                # 门：**两格一起**切，且**输入也要两格合看** ——
                # 只看自己那一格的话，上半格会判成"没电"、下半格判成"有电"，
                # 两者轮流改门 ⇒ 每轮振荡（实测：一次重算 switched=32，门最终是关的）。
                changed += self.set_door(x, y, z, self._door_powered(x, y, z, b))
            elif is_piston(b):
                changed += self._set_piston(x, y, z, b, on)
        self.stats['switched'] += changed
        return changed

    # ------------------------------------------------------------ 强充能 / 反相
    def strongly_powered(self, x: int, y: int, z: int) -> bool:
        """这一格是否被**强充能**（红石火把反相的依据）。

        **只有元件能强充能**（MC 同款：拉杆 / 按钮 / 中继器的正面；红石线只能弱充能，
        而弱充能不足以让火把熄灭 —— 这一条正是反相器不会自锁的原因）：

        * 六邻里有 `LEVER_ON` / `BUTTON_ON` ⇒ 本格被强充能
          （⚠ 简化：真实 MC 里拉杆只充能它**附着**的那一块，我们没有"附着"概念，
          所以按"六邻"算。这个放宽只会让火把更容易熄灭，不会自锁）；
        * 六邻里有 `REPEATER_ON` 且**本格就是它的正面那一格** ⇒ 被强充能。
        """
        world = self.world
        for (dx, dy, dz) in _NEIGHBORS:
            nb = (x + dx, y + dy, z + dz)
            b = world.get(*nb)
            if b in (B.LEVER_ON, B.BUTTON_ON):
                return True
            if is_repeater(b) and b == B.REPEATER_ON_OF[int(b)]:
                if repeater_front(nb, b) == (x, y, z):
                    return True
        return False

    def torch_asleep(self, x: int, y: int, z: int) -> bool:
        """红石火把是否**熄灭**：它**脚下那一格**被强充能（或脚下本身就是通电的元件）。

        ⚠ 只看脚下：火把的输出只能进红石线（弱充能）⇒ 永远改不动自己的睡眠条件。
        这一条是整个反相器**不自锁**的全部代价与保障。
        """
        by = y - 1
        if by < 0:
            return False
        below = self.world.get(x, by, z)
        if below in (B.LEVER_ON, B.BUTTON_ON):
            return True                          # 直接坐在通电的拉杆/按钮上
        if is_repeater(below) and below == B.REPEATER_ON_OF[int(below)]:
            return True                          # 直接坐在通电的中继器上
        return self.strongly_powered(x, by, z)

    def _source_live(self, cell, bid: int) -> bool:
        """这一格的电源**此刻**是否在供电（灭掉的火把不算）。"""
        if int(bid) == B.REDSTONE_TORCH:
            return not self.torch_asleep(*cell)
        return is_source(bid)

    # ------------------------------------------------------------ 门 / 活塞
    def _door_powered(self, x: int, y: int, z: int, bid: int) -> bool:
        """门（两格合看）有没有电：任一半格的六邻有信号就算有。"""
        if self.input_at(x, y, z) >= 1:
            return True
        up = bid in (B.DOOR_UPPER, B.DOOR_OPEN_UPPER)
        y2 = y - 1 if up else y + 1
        return self.input_at(x, y2, z) >= 1

    def set_door(self, x: int, y: int, z: int, opened: bool) -> int:
        """把门（连同另一半）切到开 / 关。返回改动格数。

        公开方法：`_apply_outputs`（红石驱动）与玩家的手动开关（`kernel.use`）都走它
        —— "门怎么开"只有一处实现，两条路径不会漂。
        """
        world = self.world
        b = world.get(x, y, z)
        other = B.door_other_half(b)
        if other is None:
            return 0
        # 找到另一半的实际位置：下半的门在 y-1 有另一半时说明当前是上半格
        up = b in (B.DOOR_UPPER, B.DOOR_OPEN_UPPER)
        y2 = y - 1 if up else y + 1
        want = {(x, y, z): (B.door_opened(b) if opened else B.door_closed(b))}
        b2 = world.get(x, y2, z)
        if B.door_other_half(b2) is not None:
            want[(x, y2, z)] = (B.door_opened(b2) if opened else B.door_closed(b2))
        n = 0
        for (wx, wy, wz), nb in want.items():
            if world.get(wx, wy, wz) != nb:
                self._write(wx, wy, wz, nb)
                n += 1
        return n

    def _set_piston(self, x: int, y: int, z: int, bid: int, on: bool) -> int:
        """活塞推出 / 收回。返回改动格数（推不动 ⇒ 0）。"""
        d = B.PISTON_DIR_OF.get(int(bid))
        if d is None:
            return 0
        dx, dy, dz = B.PISTON_DIR_VEC[d]
        if on:
            if bid != B.piston_off_id(bid):
                return 0                             # 已经推出
            return self._extend_piston(x, y, z, bid, (dx, dy, dz))
        if bid != B.piston_on_id(bid):
            return 0                                 # 已经收回
        return self._retract_piston(x, y, z, bid, (dx, dy, dz))

    def _extend_piston(self, x, y, z, bid, d) -> int:
        """推出：把前方 1..`PUSH_LIMIT` 格的方块整体前移一格，臂占住前方那一格。

        ⚠ **原子性**：先收集整条链、确认最远端前面是空气，**再**动手。
        边判边移会在"推到一半发现推不动"时留下被拉长的方块堆（实测踩过）。
        """
        world = self.world
        dx, dy, dz = d
        chain = []
        cx, cy, cz = x + dx, y + dy, z + dz
        while True:
            b = world.get(cx, cy, cz)
            if b == B.AIR:
                break                                # 最远端前面是空气 ⇒ 推得动
            if not is_pushable(b):
                return 0                             # 推不动 ⇒ **整体不动**
            if len(chain) >= PUSH_LIMIT:
                # ⚠ 这里**不能**写成 `while len(chain) < PUSH_LIMIT: ... else: return 0`：
                #   正好 12 个时循环是"条件变假而正常结束"⇒ 会走 else 被当成超限
                #   （实测：12 个方块推不动、13 个的判据反而"对"，看着像上限设错）。
                return 0                             # 还有第 13 个 ⇒ 超过上限，不动
            chain.append((cx, cy, cz, b))
            cx, cy, cz = cx + dx, cy + dy, cz + dz
        n = 0
        for (px, py, pz, b) in reversed(chain):      # 从最远端开始搬，避免自覆盖
            self._write(px + dx, py + dy, pz + dz, b)
            self._write(px, py, pz, B.AIR)
            n += 2
        self._write(x + dx, y + dy, z + dz, B.PISTON_ARM)
        self._write(x, y, z, B.piston_on_id(bid))
        return n + 2

    def _retract_piston(self, x, y, z, bid, d) -> int:
        """收回：**只删臂**（普通活塞不拉回被推的方块），本体切回关状态。"""
        dx, dy, dz = d
        n = 0
        if self.world.get(x + dx, y + dy, z + dz) == B.PISTON_ARM:
            self._write(x + dx, y + dy, z + dz, B.AIR)
            n += 1
        self._write(x, y, z, B.piston_off_id(bid))
        return n + 1

    # ------------------------------------------------------------ 写
    def _write(self, x: int, y: int, z: int, bid: int):
        """红石驱动的写入：**走 `set_generated`（不记存档增量）**，并通知外部标脏。

        ⚠ 顺手**作废这一格的旧信号**：新方块如果不是元件（按钮松开、线被挖掉、
        活塞臂…），它**立刻**不配再持有信号。不能等 `_clear` 来清 ——
        `_fire_due` 在 `_clear` **之前**跑，读到幽灵信号就会把短脉冲当成常亮
        （实测踩过：按钮 0.1s 回弹，中继器却按"背面有电"点了灯）。
        """
        self.world.set_generated(x, y, z, bid)
        if not is_component(bid):
            self.power.pop((int(x), int(y), int(z)), None)
        if self.on_change is not None:
            self.on_change(x, y, z)
