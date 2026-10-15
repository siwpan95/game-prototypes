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

## 五、状态切换走 `set_generated`（不记存档增量）

红石驱动的变化（灯亮、门开、活塞推）是**派生状态**，不写进存档增量：

* 存档里存的是"玩家放的 `lamp_off` / `door_lower`"；
* 读档后按同一套布局重算 ⇒ 得到同样的亮/开/推结果（单测钉住）。

⚠ 一个必须写明的后果：**被活塞推走的方块不在存档里**（它的新位置是算出来的）。
读档后活塞若仍通电，会**再推一次**得到同样结果；若玩家把活塞拆了，
被推的方块会"回到"存档记录的位置（因为它根本没被记录移动过）。
这与"改结构规则老档会变"是同一性质，见设计稿。
"""

from __future__ import annotations

from . import blocks as B

__all__ = ['MAX_POWER', 'NETWORK_CAP', 'MAX_ITER', 'PUSH_LIMIT', 'BUTTON_TTL',
           'PowerGrid', 'RedstoneOverflow',
           'is_source', 'is_conductor', 'is_output', 'is_piston', 'is_lamp',
           'is_door', 'is_pushable', 'piston_input_on',
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

#: 六邻（红石传播用）
_NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

#: 活塞推不动的方块（红石元件会被推走的话状态立刻混乱；基岩/水/作物同理）
_UNPUSHABLE = frozenset({
    B.AIR, B.BEDROCK, B.WATER, B.CROP, B.TORCH,
    B.REDSTONE_WIRE, B.LEVER_OFF, B.LEVER_ON, B.BUTTON_OFF, B.BUTTON_ON,
    B.REDSTONE_TORCH, B.REPEATER_OFF, B.REPEATER_ON, B.LAMP_OFF, B.LAMP_ON,
    B.DOOR_LOWER, B.DOOR_UPPER, B.DOOR_OPEN_LOWER, B.DOOR_OPEN_UPPER,
    B.PISTON_ARM,
} | {off for (_n, off, _on) in B.PISTON_STATES}
      | {on for (_n, _off, on) in B.PISTON_STATES})


class RedstoneOverflow(RuntimeError):
    """一次重算的网络过大（护栏，见模块 docstring §四）。"""


# ---------------------------------------------------------------- 元件分类
def is_source(bid: int) -> bool:
    """是不是电源（拉杆开 / 按钮按下 / 红石火把）。"""
    return int(bid) in (B.LEVER_ON, B.BUTTON_ON, B.REDSTONE_TORCH)


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
    """是不是"被信号驱动的东西"（灯 / 门 / 活塞 / 中继器）。"""
    b = int(bid)
    return (is_lamp(b) or is_door(b) or is_piston(b) or is_repeater(b))


def is_pushable(bid: int) -> bool:
    """活塞能不能推动这个方块。"""
    b = int(bid)
    return b != B.AIR and b not in _UNPUSHABLE and B.is_solid(b)


def piston_input_on(bid: int) -> bool:
    return int(bid) in (on for (_n, _off, on) in B.PISTON_STATES)


# ---------------------------------------------------------------- 引擎
class PowerGrid:
    """红石网络：信号强度（dict，只存非零）+ 脏格 + 按钮回弹计时。"""

    __slots__ = ('world', 'power', 'dirty', 'pending', 'on_change', 'stats')

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
        self.stats = {'recompute': 0, 'cells': 0, 'switched': 0, 'buttons': 0}

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
            if is_conductor(b) or is_source(b) or is_output(b):
                self.dirty.add(n)

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
        """中继器手动切换（demo 里方便铺线时先手动点亮看效果）。"""
        b = self.world.get(x, y, z)
        if b == B.REPEATER_OFF:
            new = B.REPEATER_ON
        elif b == B.REPEATER_ON:
            new = B.REPEATER_OFF
        else:
            return None
        self._write(x, y, z, new)
        self.mark(x, y, z)
        return new

    # ------------------------------------------------------------ 每帧
    def step(self, dt: float, budget: int = 2) -> int:
        """推进一步：按钮回弹 + 处理 `budget` 个脏网络。返回被改动的方块数。

        `budget` 是**性能护栏**（同内核的 `LIGHT_BUDGET_PER_FRAME`）：
        一个网络的重算是几十毫秒级，一帧做太多会掉帧。
        """
        changed = self._tick_buttons(dt)
        done = 0
        while self.dirty and done < max(1, int(budget)):
            seed = self.dirty.pop()
            changed += self.recompute_from(seed)
            done += 1
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
            if not (is_conductor(b) or is_source(b) or is_output(b)):
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
            if is_source(b):
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
            feed = MAX_POWER if is_source(b) else lv - 1
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
        """按"六邻最大信号 ≥1"切换输出元件的状态。返回切换次数。"""
        changed = 0
        for cell in net:
            b = self.world.get(*cell)
            if not is_output(b):
                continue
            x, y, z = cell
            on = self.input_at(x, y, z) >= 1
            if is_repeater(b):
                # 中继器是**有向**的：只看**背面**有没有信号（六邻都看会自锁）
                back = repeater_face(cell, b)
                live = back is not None and self.power.get(back, 0) >= 1
                if live and b == B.repeater_off_id(b):
                    self._write(x, y, z, B.repeater_on_id(b))
                    changed += 1
                elif not live and b == B.repeater_on_id(b):
                    self._write(x, y, z, B.repeater_off_id(b))
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
        """红石驱动的写入：**走 `set_generated`（不记存档增量）**，并通知外部标脏。"""
        self.world.set_generated(x, y, z, bid)
        if self.on_change is not None:
            self.on_change(x, y, z)
