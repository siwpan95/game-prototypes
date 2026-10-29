# 懒人桌面养鱼模拟器 · lazy_fish_tank

> 仓库：<https://gitee.com/siwpan/fish> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

一个**不催你上线**的桌面养鱼桌宠。鱼不会死、不会病、不会消失；收益不过期、不清零；
离开多久回来都只是"欢迎回来"，没有一句催促。

> 设计宪法是 8 条懒人准则（L1–L8），见 `docs/PRD.md`。任何与之冲突的需求都要让路。

---

## 1. 环境要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Python | **≥ 3.10**（本机开发/验证用 3.14.4） | 需带 `tkinter`（Windows 官方安装包默认自带） |
| 操作系统 | Windows 10/11 优先 | 透明桌宠依赖 `-transparentcolor`；非 Windows 会自动降级为不透明窗口 |
| `allin_engine` | **必需，本地路径引用，不是 pip 包** | 见下节 |

**全部 pip 依赖都是可选的**——`pystray` / `Pillow` / `numpy` / `scipy` / `asteval`
任何一个缺失都不会导致程序崩溃，只会走降级路径。

```bash
pip install -r requirements.txt   # 可选；不装也能跑
```

> 本机实测 `pystray` 未安装 → 程序默认走**无托盘降级模式**（窗口右键菜单 + 全局热键 `Ctrl+Alt+F`）。这是正常路径，不是错误。

## 2. 配置引擎路径

`allin_engine` 按以下顺序三级定位（`fishtank/engine_bootstrap.py`）：

1. 环境变量 **`ALLIN_ENGINE_HOME`**（显式覆盖，优先级最高）
2. 项目内置 **`<项目根>\tools\allin_engine`**（随仓库分发的副本，零外部依赖，复制后即用）
3. PyInstaller 冻结环境 **`sys._MEIPASS\tools\allin_engine`**（仅打包运行时存在，引擎随包捆绑）

判定标准是该目录下存在 `core/ecs.py`。三级都找不到会抛出带修复指引的 `RuntimeError`。

```powershell
# 引擎不在候选位置时（应指向含 core/ecs.py 的 allin_engine 目录）：
setx ALLIN_ENGINE_HOME "<allin_engine 目录>"
```

> 🔴 `allin_engine` 属于只读资产：本项目只 import / 继承 / 组合，**绝不修改其中任何一个字节**。

> 📌 因此 `tools/allin_engine/` 副本**自带的** `README.md`、`pyproject.toml` 里仍保留上游的历史沿革与示例措辞
> （如「从 `D:\allin` 下多项目提炼」「`cd D:/allin && python allin_engine/…`」）——那是**上游文本，不是本仓的
> 可执行指令**，本仓按只读纪律不去改它。**本项目实际口径以上面三级候选链与 `fishtank/engine_bootstrap.py` 现码为准**
> （即 `ALLIN_ENGINE_HOME` → `<项目根>\tools\allin_engine` → `sys._MEIPASS\tools\allin_engine`）。

## 3. 运行

```bash
python main.py                 # 正常启动桌宠窗口
python main.py --no-tray       # 强制无托盘模式
python main.py --safe          # 安全自检：引擎就绪 + 数据加载 + 校验后退出
python main.py --headless 60   # 无头模拟 60 秒，打印金币/水质/鱼坐标变化
python main.py --data-dir <PATH> # 自定义数据目录（存档写到 <PATH>）
```

### 存档位置

默认 **`%APPDATA%\LazyFishTank\saves\autosave.json`**。

实现方式是在 `import allin_engine` **之前**设置环境变量 `ALLIN_USER_DATA`
（引擎 `core/paths.py` 在模块导入期求值，晚设无效）。可用 `--data-dir` 改成便携目录。

存档采用**原子写**：`autosave.json.tmp` → `os.replace()` → 保留上一份 `autosave.json.bak`。
主档解析失败时自动回退 `.bak`；**任何字段缺失或类型错误都只补默认值 + 记 warning，绝不清档、绝不崩溃**。

## 4. 测试

```bash
python -m pytest              # 全量
python -m pytest -m "not slow"
python tools/gen_fish_data.py --check   # 校验 fish_data.json 与 FISH_CONTENT.md 一致
python tools/gen_golden.py --check      # 校验离线结算黄金用例未漂移
```

## 5. 目录结构

```
main.py                入口（第一行必须 import fishtank.engine_bootstrap）
data/                  ★ 双端共享的唯一数值源，玩法逻辑零硬编码
  balance.json         全部平衡参数
  fish_data.json       24 种鱼（由 tools/gen_fish_data.py 从 FISH_CONTENT.md 生成）
  decor_data.json      12 件装饰
  ui_text.json         全部 UI 文案（L6 零催促）
fishtank/              L1+L2 平台无关领域层（🔴 严禁 import tkinter）
  economy.py offline.py  ★ 纯函数内核，与 XJ380 C++ 端逐位对偶
  systems/             ECS 系统（priority 固定表）
pyapp/                 L3+L4 Python GUI（唯一允许 import tkinter 处）
xj380/                 C++ 端（XJ380OS）
tests/                 pytest + 双端共用黄金用例
tools/                 数据生成与校验脚本
docs/                  PRD / ARCHITECTURE / TASKS / FISH_CONTENT
```

## 6. 关于 XJ380 SDK（合规说明）

XJ380 端源码位于 `xj380/`，但**本仓库不包含 XJ380 SDK 的任何文件**。

该 SDK（XACT 工具链、`XJ380_CPP_API_Depend_1_3` 头文件与预编译对象）为专有软件，
未随附 LICENSE，**需使用者自行从官方渠道获取**，并放置到本机路径后由构建脚本引用。
本机默认引用位置为 `<PATH>`。

同样地，构建 XJ380 端还需要自行安装 `clang ≥ 18.1.8` 与 `GNU ld ≥ 2.42`；
在 QEMU 中运行还需要 XJ380OS 镜像。这些均不在本仓库分发范围内。

## 7. 开发铁律（提交前自查）

1. 🔴 任何含 dataclass 的文件**禁止** `from __future__ import annotations`
   —— 会让引擎 `Serializable` 的嵌套 `from_dict` 静默返回 dict（无异常的数据损坏，Python 3.14 实测）。
2. `fishtank/` 包内**严禁 import tkinter**。
3. `allin_engine` 与 `<PATH>` **只读**，一个字节都不许改。
4. 玩法逻辑**零硬编码数值**，全部走 `data/balance.json`。
5. 金币一律整数厘（`coins_milli`，1 金币 = 1000 厘）；取整统一 `floor(x + 0.5)`，**禁用内置 `round()`**。
6. 时间一律 UTC 整数秒；坐标一律归一化 `[0,1]`；遍历鱼**必须按 uid 升序**。
7. `settle_offline()` 必须保持**无副作用纯函数**（返回深拷贝）——这是双端一致性的基石。
8. 每条鱼一棵**独立**行为树（节点持有 RUNNING 状态，共享会串味）。
9. 代码里不得出现任何桌面通知 API；音效默认关闭。

---

*文档：`docs/PRD.md`（需求） · `docs/ARCHITECTURE.md`（实现依据） · `docs/TASKS.md`（任务分解） · `docs/FISH_CONTENT.md`（内容源）*
