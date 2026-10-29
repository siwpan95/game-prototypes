# 🧬 细胞工厂

> 仓库：<https://gitee.com/siwpan/yuanbao> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 元胞自动机 × CNN 标签任务系统 —— 一个把 Conway 生命游戏式演化与卷积模式检测结合的轻量"挂机收集"沙盒。

细胞在带标签的网格上按生命游戏规则演化，标签随演化扩散与混合；一个类 CNN 的固定卷积核扫描空间模式（如"红细胞且周围恰有 1 个绿邻居"），命中即被"收集"，凑齐需求即完成任务。

---

## ✨ 特性

- **元胞自动机引擎**：环面拓扑、可配置规则（存活/诞生邻居数）、可配置初始密度与随机种子（可复现）。
- **CNN 风格检测器**：以 3×3 固定卷积核描述任意"中心标签 + 邻居标签精确计数"模式，零依赖纯 Python。
- **任务系统**：任务由若干需求组成，进度实时可查，支持重置。
- **自动化引擎**：演化 + 检测 + 收集一体化；支持阻塞运行（CLI）与后台线程运行（GUI），通过回调与展示层解耦。
- **双前端**：
  - **GUI**（tkinter，免第三方依赖）：彩色网格、进度条、速度调节、开始/暂停/单步/重置。
  - **CLI**：原汁原味的文本网格输出。
- **零第三方运行时依赖**：仅用 Python 标准库。

---

## 📦 项目结构

```
<PATH>
├── yuanbao/                      # 主包
│   ├── __init__.py               # 包出口，导出主要类
│   ├── __main__.py               # 支持 python -m yuanbao
│   ├── config.py                 # Config：规则参数与标签系统（依赖注入）
│   ├── core/                     # 核心引擎层
│   │   ├── automaton.py          # CellularAutomaton 元胞自动机
│   │   └── detector.py           # CNNDetector 模式检测器
│   ├── tasks/                    # 任务系统层
│   │   ├── requirement.py        # TaskRequirement 单个收集需求
│   │   └── task.py               # Task 任务（多需求聚合）
│   ├── engine/                   # 自动化引擎层
│   │   └── auto_runner.py        # AutoRunner 演化+收集循环
│   ├── gui/                      # GUI 层（tkinter）
│   │   ├── app.py                # 主窗口 + 线程桥接
│   │   ├── grid_canvas.py        # 网格画布渲染
│   │   ├── control_panel.py      # 控制条（开始/暂停/单步/重置/速度）
│   │   └── task_panel.py         # 任务进度面板
│   └── cli.py                    # 命令行入口 + 默认任务定义
├── tests/                        # 单元测试（unittest）
│   ├── test_automaton.py
│   ├── test_detector.py
│   ├── test_task.py
│   └── test_auto_runner.py
├── main.py                       # 启动入口（默认 GUI）
├── yuanbao.py                    # 旧入口（向后兼容，薄封装）
├── yuanbao.spec                  # PyInstaller 打包配置
├── requirements.txt              # 依赖说明（仅标准库 + 可选 pyinstaller）
└── README.md
```

### 分层设计

```
┌─────────────────────────────────────────────┐
│  前端层   cli.py  /  gui/*.py                │  展示与交互
├─────────────────────────────────────────────┤
│  引擎层   engine/auto_runner.py             │  演化+收集编排（回调解耦）
├─────────────────────────────────────────────┤
│  领域层   core/  +  tasks/                   │  CA、检测器、任务模型
├─────────────────────────────────────────────┤
│  配置层   config.py                          │  参数与标签（依赖注入）
└─────────────────────────────────────────────┘
```

关键解耦点：`AutoRunner` 不再直接 `print`/`sleep` 副作用，而是通过 `on_step`/`on_complete` 回调把展示职责交还调用方；`Config` 改为可实例化的 dataclass 并注入各模块，不再全局硬编码。

---

## 🚀 快速开始

### 环境要求

- Python 3.9+（用了 `dict | None` 类型语法，3.10+ 原生支持；3.9 需 `from __future__ import annotations`，代码已加）
- tkinter：Windows / macOS 自带；Linux 需 `sudo apt install python3-tk`

### 运行 GUI

```bash
python main.py
# 或
python -m yuanbao
```

界面包含：左侧彩色网格（红/绿/蓝/黄四种标签细胞），右侧任务进度条与需求清单，底部控制条。

### 运行 CLI

```bash
python -m yuanbao --cli --grid 20 --steps 200 --interval 0.3 --seed 42
```

参数：

| 参数          | 说明                          | 默认 |
|---------------|-------------------------------|------|
| `--cli`       | 使用命令行模式（不加则启动 GUI） | -    |
| `--grid`      | 网格大小                      | 20   |
| `--steps`     | CLI 最大步数                  | 200  |
| `--interval`  | 步间隔（秒）                  | 0.3  |
| `--seed`      | 随机种子（便于复现）          | 随机 |

---

## 🧪 测试

```bash
python -m unittest discover -s tests -v
```

覆盖范围：

- **CA 引擎**：网格尺寸、种子可复现、step 状态变化、清空/设置细胞、环面环绕、状态拷贝隔离、存活计数。
- **检测器**：正例匹配、计数不符不匹配、中心标签不符不匹配、死细胞不检测、无 neighbors 子句、环面对角邻居、未知标签。
- **任务系统**：完成判定、进度计算（含超额封顶、空需求边界）、重置、状态文本。
- **自动化引擎**：步计数、无任务边界、收集清空、去重、count=0 立即完成、停止标志、回调触发、后台线程完成、重置、all_done 属性。

---

## 📦 打包成 exe

```bash
pip install pyinstaller
pyinstaller yuanbao.spec
```

产物：`dist/yuanbao.exe`（无控制台窗口，双击即启动 GUI）。

---

## 🔧 扩展指南

### 添加新标签

```python
from yuanbao.config import Config

cfg = Config(TAGS=['red', 'green', 'blue', 'yellow', 'purple'])
```

并在 `yuanbao/gui/grid_canvas.py` 的 `TAG_COLORS` 里补一个颜色即可（不补则用灰色回退）。

### 添加新任务

```python
from yuanbao.tasks.requirement import TaskRequirement
from yuanbao.tasks.task import Task

req = TaskRequirement(
    description="黄细胞且周围恰有3个红邻居",
    pattern={"center": "yellow", "neighbors": {"red": 3}},
    count=5,
)
task = Task("火焰收集", [req])
```

`pattern` 格式：

```python
{
    "center": "<标签名>",            # 中心细胞必须是该标签
    "neighbors": {"<标签名>": <数量>} # 8 邻域中各标签的精确出现次数（可选）
}
```

### 调整演化规则

```python
# 例如"高生命"规则：存活 2~3，诞生 3 或 6
cfg = Config(SURVIVE_MIN=2, SURVIVE_MAX=3, BORN_MIN=3, BORN_MAX=6)
```

### 在自己的程序里用引擎

```python
from yuanbao import Config, CellularAutomaton, CNNDetector, AutoRunner, Task, TaskRequirement

cfg = Config(GRID_SIZE=30, INIT_DENSITY=0.4)
ca = CellularAutomaton(cfg, seed=1)
det = CNNDetector(cfg.GRID_SIZE, cfg)
task = Task("demo", [TaskRequirement("红+1绿", {"center": "red", "neighbors": {"green": 1}}, 3)])
runner = AutoRunner(ca, det, [task])

runner.run(
    max_steps=500,
    interval=0.1,
    on_step=lambda n, r: print(f"gen {n}, alive={r.ca.count_alive()}"),
    on_complete=lambda ok, r: print("done" if ok else "timeout"),
)
```

---

## 📐 设计说明

### 为什么把 Config 做成可实例化 dataclass？

原实现中 `Config` 是被各处直接 `Config.GRID_SIZE` 引用的全局类，导致规则参数无法在不同实例间独立调整，也阻碍测试隔离。重构后 `Config` 既是默认值命名空间（`Config.GRID_SIZE` 仍可用），又可实例化注入。各模块只持有传入的实例，不再回引全局类。

### 为什么 AutoRunner 用回调而不是直接 print？

原 `run()` 在循环里直接 `print` 网格和任务状态，把逻辑与展示耦合死，GUI 无法复用。重构后 `step()` 是纯逻辑（无 IO 副作用），`run()`/`run_threaded()` 通过 `on_step`/`on_complete` 回调把展示交还调用方。这样 CLI、GUI、未来的 Web 前端都能共享同一份引擎逻辑。

GUI 的线程安全：tkinter 不是线程安全的，工作线程的回调统一用 `self.after(0, ...)` 调度回主线程刷新 UI。

---

## 📄 许可

MIT
