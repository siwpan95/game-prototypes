# 设计文档：为 allin_engine 补齐「我的世界复刻（2D 文字/卡牌向）」引擎地基

> 架构师：高见远（Gao）
> 范围：仅补引擎地基（A–G 七块缺口 + mc_clone 骨架），不写任何游戏逻辑（无玩家循环/移动/碰撞/UI 玩法）。
> 方向：2D 侧视方块世界 + 文字(ASCII/ANSI)渲染。保持代码 3D-就绪，第一轮只做 2D 侧视。
> 约束：纯 Python 3.14 扩展 allin_engine，零新增硬依赖（pygame 仅作可选软依赖）。

---

## 1. 实现方案 + 框架选型

**框架/库选型（结论：纯标准库扩展，零硬依赖）**
- 噪声：自实现 Perlin（梯度噪声）+ fbm。确定性来源用 `random.Random(seed)`（Mersenne Twister，整数 seed 跨进程/跨版本稳定），自行构建置换表。不引入任何第三方库。
- 方块注册表：复用引擎已有 `core/data_library.py` 的 `DataLibrary[T]` 与 `core/serializable.py` 的 `Serializable`；默认方块集以 JSON 资源附带，`json_loader` 加载。
- 世界模型：复用 `Serializable` 做存档序列化；chunk 切片序列化供 `systems/save_load.py` 的 `SaveLoadManager` 使用（第一轮仅定义接口，不接存档 UI）。
- 渲染：复用 `render/console_renderer.py` 的 ANSI 能力（或直接产 ANSI 文本行，不强制依赖 Tkinter 窗口）。新增独立 `render/text_world_renderer.py`。
- 输入：复用 `systems/input.py` 的 `InputManager`，新增 `systems/input_realtime.py` 的 `PygameKeyStateSource`。pygame 用延迟 import（try/except），引擎加载时绝不 import pygame。
- 几何：新增 `core/geometry.py`（Vec2i / AABB2D / clamp / lerp）。

**架构模式**：数据驱动（DataLibrary 注册方块）+ ECS 就绪。分层：`core`（几何）→ `world`（噪声/方块/世界/地形）→ `render`/`systems`（渲染/输入）→ `mc_clone`（最小骨架）。

---

## 2. 文件列表及相对路径

### 2.1 引擎侧（`D:\allin\tools\allin_engine\`，相对引擎根）
| 文件 | 职责 |
|---|---|
| `core/geometry.py` | 新增：`Vec2i`、`AABB2D`、`clamp`、`lerp` 几何/视口数学原语。 |
| `world/__init__.py` | 新增包：导出 noise/block_registry/block_world/terrain 并集中 re-export。 |
| `world/noise.py` | 新增：纯 Python 确定性 `PerlinNoise`（含 `fbm` 分形叠加），无外部依赖。 |
| `world/block_registry.py` | 新增：`BlockDef` + `BlockRegistry`（默认集 + JSON 加载）。 |
| `world/block_world.py` | 新增：`BlockWorld`——以 `(x,y,z)` 元组为键的方块存储，get/set/边界/区域填充/chunk 序列化。 |
| `world/terrain.py` | 新增：`TerrainGenerator`——给定 seed+尺寸，用噪声生成侧视世界（石/土/草/水/沙分层）。 |
| `world/data/blocks.default.json` | 新增资源：默认方块集 JSON 定义，供 `BlockRegistry.load_defaults()` 加载。 |
| `render/text_world_renderer.py` | 新增：`TextWorldRenderer`——给定 BlockWorld + 视口，按方块 glyph+color 产出 ANSI/ASCII 文本行。 |
| `systems/input_realtime.py` | 新增：`PygameKeyStateSource`（按住状态、is_down/poll）+ `RealtimeInputManager`。延迟 import pygame。 |
| `allin_engine/__init__.py` | 更新：re-export 新模块。 |
| `render/__init__.py`、`systems/__init__.py` | 更新：补充新模块导出（在末尾追加，不覆盖既有）。 |

### 2.2 游戏骨架侧（`D:\allin\tools\mc_clone\`）
| 文件 | 职责 |
|---|---|
| `mc_clone/__init__.py` | 新增：包初始化，导出 `main`。 |
| `mc_clone/main.py` | 新增：stub `main()`——导入 allin_engine 并打印就绪信息（无玩法代码）。 |
| `mc_clone/README.md` | 新增：骨架说明。 |

---

## 3. 数据结构和接口

```python
# ===== core/geometry.py =====
@dataclass(slots=True)
class Vec2i:
    x: int
    y: int
    def __add__(self, o: "Vec2i") -> "Vec2i": ...
    def __sub__(self, o: "Vec2i") -> "Vec2i": ...
    def __eq__(self, o: object) -> bool: ...
    def __hash__(self) -> int: ...
    def as_tuple(self) -> tuple[int, int]: ...
    @staticmethod
    def from_tuple(t: tuple[int, int]) -> "Vec2i": ...

@dataclass(slots=True)
class AABB2D:
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    def contains(self, x: int, y: int) -> bool: ...
    def width(self) -> int: ...
    def height(self) -> int: ...
    def clamp_point(self, x: int, y: int) -> tuple[int, int]: ...
    def intersects(self, o: "AABB2D") -> bool: ...

def clamp(v, lo, hi): ...
def lerp(a: float, b: float, t: float) -> float: ...

# ===== world/noise.py =====
class PerlinNoise:
    def __init__(self, seed: int, perm_size: int = 256) -> None: ...
    def noise(self, x: float, y: float) -> float: ...        # [-1,1]
    def fbm(self, x: float, y: float, octaves: int = 4,
            lacunarity: float = 2.0, persistence: float = 0.5) -> float: ...  # 约 [-1,1]

# ===== world/block_registry.py =====
@dataclass(slots=True)
class BlockDef(Serializable):
    id: int
    name: str
    glyph: str
    color: str
    solid: bool = True
    transparent: bool = False
    props: dict = field(default_factory=dict)
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "BlockDef": ...

class BlockRegistry:
    def register(self, block: BlockDef) -> None: ...
    def get(self, block_id: int) -> BlockDef: ...
    def get_by_name(self, name: str) -> BlockDef | None: ...
    def __contains__(self, block_id: int) -> bool: ...
    def ids(self) -> list[int]: ...
    @classmethod
    def load_defaults(cls) -> "BlockRegistry": ...
    @classmethod
    def from_json(cls, path: str) -> "BlockRegistry": ...

# ===== world/block_world.py =====
class BlockWorld(Serializable):
    def __init__(self, width: int, height: int, depth: int = 1) -> None: ...
    def get(self, x: int, y: int, z: int = 0) -> int: ...   # 越界/缺失返回 0(air)
    def set(self, x: int, y: int, z: int, block_id: int) -> None: ...
    def in_bounds(self, x: int, y: int, z: int = 0) -> bool: ...
    def fill_rect(self, x0, y0, x1, y1, block_id, z=0) -> None: ...
    def bounds(self) -> AABB2D: ...
    def serialize_chunk(self, cx: int, cy: int, size: int) -> dict: ...
    def load_chunk(self, cx: int, cy: int, size: int, data: dict) -> None: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "BlockWorld": ...

# ===== world/terrain.py =====
class TerrainGenerator:
    def __init__(self, registry: BlockRegistry, seed: int,
                 noise: PerlinNoise | None = None) -> None: ...
    def generate(self, width: int, height: int, depth: int = 1) -> BlockWorld: ...

# ===== render/text_world_renderer.py =====
class TextWorldRenderer:
    def __init__(self, registry: BlockRegistry) -> None: ...
    def render(self, world: BlockWorld, viewport: AABB2D, use_ansi: bool = True) -> list[str]: ...
    def render_to_string(self, world, viewport, use_ansi=True) -> str: ...
    def render_line(self, world, x0, x1, world_y, use_ansi=True) -> str: ...

# ===== systems/input_realtime.py =====
class PygameKeyStateSource:
    def __init__(self) -> None: ...
    def poll(self) -> None: ...
    def is_down(self, key: int) -> bool: ...
    def pressed_this_frame(self, key: int) -> bool: ...
    def reset_frame(self) -> None: ...

class RealtimeInputManager:
    def __init__(self, base: "InputManager", key_source: PygameKeyStateSource) -> None: ...
    def is_down(self, key: int) -> bool: ...
    def update(self) -> None: ...
```

---

## 4. 程序调用流程（第一轮组合）

`BlockRegistry.load_defaults()` → `PerlinNoise(seed)` → `TerrainGenerator(reg, seed, noise).generate(w,h)` → `TextWorldRenderer(reg).render(world, viewport)` → print。

未来游戏循环：`FixedTimestepLoop` + `RealtimeInputManager.update()` 每帧 poll 按键 → `System` 读 `is_down` 改 `BlockWorld`、发 `EventTypes`（第一轮不实现）。

---

## 5. 任务列表（有序、供工程师执行）

| 任务 | 名称 | 源文件 | 依赖 | 优先级 |
|---|---|---|---|---|
| T01 | 几何与噪声地基 | `core/geometry.py`、`world/noise.py`、`world/__init__.py`、`allin_engine/__init__.py`（补导出） | 无 | P0 |
| T02 | 方块数据层 | `world/block_registry.py`、`world/data/blocks.default.json`、`world/__init__.py`（补导出） | 无 | P0 |
| T03 | 世界模型与地形生成 | `world/block_world.py`、`world/terrain.py`、`world/__init__.py`（补导出） | T01、T02 | P0 |
| T04 | 文字渲染与实时输入 | `render/text_world_renderer.py`、`systems/input_realtime.py`、`render/__init__.py`、`systems/__init__.py` | T01、T02、T03 | P1 |
| T05 | 游戏骨架与集成验证 | `mc_clone/__init__.py`、`mc_clone/main.py`、`mc_clone/README.md` | T01–T04 | P1 |

实现顺序：T01 → T02（可并行）→ T03 → T04 → T05。

---

## 6. 依赖包列表

无新增硬依赖。唯一例外（可选软依赖）：`pygame`——仅在运行 `PygameKeyStateSource`/实时键盘时按需 import，引擎加载阶段绝不引入；未安装时该类给出清晰报错。

---

## 7. 共享知识（跨文件约定）

- **坐标约定**：世界坐标 x 向右递增，y 向上递增（标准数学向），z 向前（第一轮恒为 0）。文字渲染映射（终端从上往下）：屏幕第 r 行对应世界 `y = viewport.max_y - r`；屏幕第 c 列对应世界 `x = viewport.min_x + c`。所有涉及视口的代码一律遵守此映射。
- **方块 id 方案**：`0=air`、`1=stone`、`2=dirt`、`3=grass`、`4=water(透明)`、`5=sand`。注册表以 id 为主键，唯一。
- **glyph/color 约定**：`glyph` 为单个可打印字符；`color` 用语义名（`"gray"|"brown"|"green"|"blue"|"yellow"|"white"`），由 `TextWorldRenderer` 内部调色板映射为 ANSI 转义码。`use_ansi=False` 时仅输出 glyph。
- **序列化格式（chunk→JSON）**：`serialize_chunk` 返回 `{ "cx", "cy", "size", "blocks": [[id,...],...] }`，blocks 为 size 行 size 列，行序从上到下（第 0 行 = chunk 内最大 world y），列序从左到右（x 递增）。整世界 `to_dict()` 额外含 `width/height/depth`。
- **确定性规则**：所有随机性只来自 `random.Random(seed)`；禁止全局 random/系统时间/os.urandom。`PerlinNoise` 用 `Random(seed)` 构建置换表。同 `(seed,width,height)` 必产出逐格一致的 `BlockWorld`。

---

## 8. 待明确事项的采纳默认值（第一轮）

1. y 轴方向：采用「世界 y 向上，渲染时上下翻转」。
2. 多层 z：第一轮仅 `depth=1`，结构保留 `depth` 字段。
3. ANSI：标准 8/16 色 ANSI（`\033[3Xm`）。
4. pygame：延迟 import，未安装仅报错，不触发于骨架。
5. `BlockRegistry.from_json` 基于 `JSONLoader` + `BlockDef.from_dict`（不强行绑 `DataLibrary`）。
6. 第一轮 `TerrainGenerator` 不发任何 `EventTypes` 事件。
