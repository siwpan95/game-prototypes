# 懒人桌面养鱼模拟器 — 运维手册（RUNBOOK）

> **定位**：本文档面向运维人员与日常使用者，覆盖启动/关闭、存档管理、故障排查与数据维护。
> **前置阅读**：`README.md`（运行说明）、`docs/ARCHITECTURE.md`（系统架构）。
> **路径占位符**：`<仓库根>`（本项目根目录）、`<数据目录>`、`<备份目录>`、`<PATH>`（XJ380 SDK 根）请替换为你本机实际路径。

---

## 1. 日常运行

### 1.1 启动

```powershell
cd <仓库根>
python main.py
```

程序将启动桌宠窗口（无边框透明置顶可拖拽鱼缸）并自动加载存档。

可选启动参数：

| 参数 | 作用 | 示例 |
|------|------|------|
| `--no-tray` | 强制禁用托盘，走窗口右键菜单降级 | `python main.py --no-tray` |
| `--safe` | 安全自检：引擎就绪 + 数据加载 + 校验后退出（不建窗口） | `python main.py --safe` |
| `--headless SEC` | 无头模拟指定秒数后退出（用于验证，不建窗口） | `python main.py --headless 60` |
| `--data-dir DIR` | 自定义数据目录（存档写到 `DIR/saves/`） | `python main.py --data-dir <数据目录>` |
| `--no-save` | 本次运行不写存档（自检/测试用，不污染玩家进度） | `python main.py --no-save` |

### 1.2 关闭

**窗口的关闭按钮（×）不是退出，而是隐藏。** 要真正退出程序，需通过以下任一方式：

| 方式 | 操作 |
|------|------|
| **托盘菜单** | 右键托盘图标 →「退出」 |
| **窗口右键菜单** | 右键鱼缸空白水域 →「退出」（无托盘模式下） |
| **管理面板** | 打开面板 → 设置页签 →「退出」 |

> **设计意图**：关闭按钮 = 最小化到托盘/隐藏，符合用户「暂时不想看到鱼缸但程序继续跑收益」的心智模型。

### 1.3 隐藏与恢复

程序提供三层降级体系确保窗口始终可恢复：

| 层级 | 条件 | 恢复方式 |
|------|------|----------|
| **L1 系统托盘** | `pystray` 已安装（非默认） | 单击托盘图标切换显隐；右键托盘图标 →「显示窗口」 |
| **L2 全局热键** | `pystray` 未安装时的默认路径 | 按下 **`Ctrl+Alt+F`** 恢复窗口 |
| **L3 迷你角标** | 热键注册也失败时的最后兜底 | 窗口缩为 48×48 迷你角标固定在屏幕角落，点击即可恢复 |

> **关键原则**：三级降级体系保证**永远存在至少一条恢复路径**。用户绝不会陷入「窗口消失了但不知道怎么找回来」的困境。

当前本机实测环境 `pystray` 未安装，默认走 **L2 热键路径**，这是正常行为而非错误。

### 1.4 托盘操作（pystray 已安装时）

右键托盘图标弹出菜单，包含以下操作：

- **显示/隐藏窗口**
- **置顶开关**（切换窗口是否始终在最前）
- **鼠标穿透开关**（开启后点击直接穿透到下层应用）
- **打开面板**（展开管理面板：图鉴/商店/升级/设置）
- **退出**

### 1.5 窗口交互速查

| 操作 | 方式 |
|------|------|
| 拖拽鱼缸 | 左键按住鱼缸空白区域拖动 |
| 贴边吸附 | 拖到屏幕边缘附近（24px 内）自动吸附 |
| 点击鱼 | 弹出该鱼的信息小卡（名称/稀有度/成长阶段/科普），3 秒后自动消失 |
| 双击空白水域 | 展开管理面板 |
| 右键鱼缸 | 弹出右键菜单（打开面板/置顶/穿透/隐藏/退出） |
| 鼠标移出 2 秒 | HUD 条淡出至 30% 不透明度 |

---

## 2. 存档管理

### 2.1 存档位置

```
%APPDATA%\LazyFishTank\saves\
├── autosave.json          ← 主存档
├── autosave.json.bak      ← 备份（上一份存档的副本）
└── autosave.json.tmp      ← 写入中的临时文件（正常运行时短暂存在）
```

例如在本机上为：
```
C:\Users\13122\AppData\Roaming\LazyFishTank\saves\autosave.json
```

> **提示**：在文件资源管理器地址栏输入 `%APPDATA%\LazyFishTank\saves` 即可快速跳转。

### 2.2 自动存档时机

| 触发条件 | 说明 |
|----------|------|
| **定时存档** | 每 60 秒自动保存一次 |
| **窗口隐藏时** | 用户点击关闭按钮隐藏窗口时立即保存 |
| **退出前** | 通过托盘菜单、右键菜单或面板退出时强制保存 |
| **购买后立即** | 任何购买行为（买鱼、买装饰、升级设施）完成后立即落盘 |
| **领取离线收益后** | 用户点击「收下，谢谢」后立即保存 |

### 2.3 存档安全机制

程序采用**原子写（三段式）**保护数据安全：

1. 写入 `autosave.json.tmp`
2. `os.replace()` 原子替换 → 将 `.tmp` 重命名为 `autosave.json`
3. 保留上一份存档为 `autosave.json.bak`

这意味着即使程序在写入过程中崩溃或断电，**最多丢失最近一次自动存盘点（≤ 60 秒）的数据**，不会出现存档完全损坏的情况。

### 2.4 手动备份

**备份整个存档目录：**

```powershell
# 复制到备份位置
xcopy "%APPDATA%\LazyFishTank\saves" "<备份目录>\fish_saves_%date:~0,4%%date:~5,2%%date:~8,2%\" /E /I
```

**仅备份主存档：**

```powershell
copy "%APPDATA%\LazyFishTank\saves\autosave.json" "<备份目录>\autosave_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
```

**恢复备份（见 §3.2）。**

### 2.5 使用便携目录

如果希望存档保存在程序目录或任何自定义位置（如 U 盘），使用 `--data-dir` 参数：

```powershell
# 存档写到 <数据目录>\saves\
python main.py --data-dir <数据目录>

# 存档写到程序目录旁的 saves 文件夹
python main.py --data-dir .\userdata
```

---

## 3. 故障排查

### 3.1 窗口消失后如何恢复

**症状**：鱼缸窗口找不到了，但程序仍在运行。

**按优先级依次尝试：**

| 步骤 | 操作 | 适用条件 |
|------|------|----------|
| 1 | 检查系统托盘，单击鱼缸图标 | `pystray` 已安装 |
| 2 | 按 **`Ctrl+Alt+F`** | 无托盘模式的默认恢复方式 |
| 3 | 查看屏幕四角是否有 48×48 小方块 | 热键注册失败时的最后兜底，点击即可恢复 |

**如果以上全部无效：**

1. 打开任务管理器（`Ctrl+Shift+Esc`）
2. 在「详细信息」标签页找到 `python.exe`（命令行含 `main.py`）
3. 结束该进程
4. 重新启动程序（存档完好，收益不丢）

> **为什么会消失？** 通常是因为用户点击了关闭按钮（正常行为 = 隐藏到托盘/后台）或误触了隐藏操作。

### 3.2 存档损坏时手动恢复

**症状**：启动时看到存档加载警告日志，或程序以全新初始状态启动。

**自动恢复**：程序启动时会自动检测主存档是否有效；若 JSON 解析失败，**自动回退到 `autosave.json.bak`**。

**手动恢复步骤：**

```powershell
# 1. 进入存档目录
cd "%APPDATA%\LazyFishTank\saves"

# 2. 查看文件大小（大小为 0 或异常的 .json 就是损坏的）
dir autosave*

# 3. 备份当前状态（保留现场，方便排查）
mkdir _recovery_%date:~0,4%%date:~5,2%%date:~8,2%
copy autosave.json _recovery_%date:~0,4%%date:~5,2%%date:~8,2%\autosave_corrupted.json
copy autosave.json.bak _recovery_%date:~0,4%%date:~5,2%%date:~8,2%\autosave.bak

# 4. 用备份文件恢复
copy autosave.json.bak autosave.json

# 5. 重新启动程序验证
cd <仓库根>
python main.py
```

**如果 `.bak` 也损坏**：检查是否有你自己手动创建的备份（见 §2.4），复制过来覆盖。

**最坏情况**：两档都不可恢复。程序会以全新初始状态启动（赠送 3 条 R1 鱼，金币 0，水质 100），但**程序绝不会崩溃或清空磁盘上的存档文件**。损坏的文件仍在原位置，可供后续排查。

### 3.3 引擎找不到

**症状**：

```
RuntimeError: 未找到 allin_engine，请设置环境变量 ALLIN_ENGINE_HOME
```

或程序启动时报找不到 `allin_engine` 相关模块。

**原因排查**：程序按三级策略定位引擎——

| 优先级 | 位置 | 如何检查 |
|--------|------|----------|
| 1 | 环境变量 `ALLIN_ENGINE_HOME` | `echo %ALLIN_ENGINE_HOME%` |
| 2 | 项目内置 `<仓库根>\tools\allin_engine` | `dir <仓库根>\tools\allin_engine\core\ecs.py` |
| 3 | PyInstaller 冻结环境 `<_MEIPASS>\tools\allin_engine` | 打包产物内自动包含，无需手工检查 |

判定标准是目录下存在 `core/ecs.py`。

**解决方案**：

```powershell
# 如果引擎在其他位置，设置环境变量指向它
setx ALLIN_ENGINE_HOME "<allin_engine 目录>"

# 验证设置生效（需要重新打开命令行窗口）
echo %ALLIN_ENGINE_HOME%

# 重新运行
python main.py --safe
```

### 3.4 程序启动失败

#### 情况 A：缺少 tkinter

**症状**：导入时报 `ModuleNotFoundError: No module named '_tkinter'` 或类似错误。

**原因**：Python 安装时未包含 tkinter（常见于部分 Linux 发行版或精简安装）。

**解决**：

```powershell
# Windows：重新安装 Python 时勾选 "tcl/tk and IDLE" 选项
# 或使用官方提供的完整安装包（默认自带 tkinter）

# 验证 tkinter 可用：
python -c "import tkinter; print(tkinter.TkVersion)"
```

#### 情况 B：Python 版本不兼容

**症状**：各种语法错误或 API 不可用。

**原因**：程序要求 **Python ≥ 3.10**（本机开发/验证使用 3.14.4）。

**解决**：

```powershell
# 检查当前版本
python --version

# 如果 < 3.10，安装新版本 Python 3.10+
# 官方下载：https://www.python.org/downloads/
```

#### 情况 C：可选依赖缺失（不是错误）

**症状**：启动日志中出现 `pystray未安装，走无托盘降级模式`。

**这不是错误。** 程序设计为 `pystray` / `Pillow` / `numpy` / `scipy` / `asteval` 全部可选，缺失任何一个都不会崩溃，只会走对应的降级路径。

| 缺失的包 | 降级行为 |
|----------|----------|
| `pystray` | 无系统托盘，走右键菜单 + 热键 `Ctrl+Alt+F` |
| `Pillow` | 托盘图标无法生成（但 `pystray` 也需要它） |
| `numpy` | 粒子系统用纯 Python 路径（稍慢，不影响功能） |
| `scipy` | 环境音效不可用（音效默认关闭，无影响） |
| `asteval` | 公式沙盒禁用（核心算法用普通函数，无影响） |

---

## 4. 数据维护

### 4.1 验证数据完整性

使用 `--safe` 模式进行全量自检（不弹出窗口，不修改任何存档）：

```powershell
python main.py --safe
```

输出示例：

```
[1/4] 引擎就绪
      engine_home = <仓库根>\tools\allin_engine
      user_data   = C:\Users\13122\AppData\Roaming\LazyFishTank
      save_dir    = C:\Users\13122\AppData\Roaming\LazyFishTank\saves
      deps        = {'numpy': True, 'scipy': True, 'asteval': True, 'PIL': True, 'pystray': False, 'tkinter': True}

[2/4] 数据加载
      balance.json  keys=28
      fish_data     24 种
      decor_data    12 件
      ui_text       N 组

[3/4] 数值表校验
      balance.json 全部校验通过

[4/4] 领域内核自检
      离线结算     = N 厘 / 离开 Ns / 等效 N 小时
      金币         = N.N
      鱼           = N 条 / 容量 N
      水质         = N.NNNN
      系统         = autofeeder_system, brain_system, ...
自检完成：引擎就绪、数据加载。
```

如果 `[3/4]` 部分出现 `[警告]`，说明 `balance.json` 存在内容问题（如数值越界、分段不连续等），程序会用内置默认值兜底并继续运行，但建议检查并修复数据文件。

### 4.2 运行全量测试

```powershell
cd <仓库根>

# 全量测试
python -m pytest

# 跳过慢速测试
python -m pytest -m "not slow"

# 仅运行离线结算测试
python -m pytest tests/test_offline_golden.py -v

# 仅运行数据完整性测试
python -m pytest tests/test_data_integrity.py -v
```

### 4.3 验证黄金用例未漂移

黄金用例是双端（Python + C++ XJ380）一致性的唯一保障，**任何算法改动后必须验证**：

```powershell
cd <仓库根>

# Python 端验证
python -m pytest tests/test_offline_golden.py -v

# 校验 fish_data.json 与 FISH_CONTENT.md 一致
python tools/gen_fish_data.py --check

# 校验离线结算黄金用例未漂移
python tools/gen_golden.py --check

# C++ 端验证（需要宿主 g++/clang 编译 golden_runner）
g++ -std=c++11 -I xj380/src -I xj380/src/core \
    xj380/tools/golden_runner.cpp \
    xj380/src/core/*.cpp -o golden_runner.exe && \
    ./golden_runner.exe
```

> 预期：全部 14 组黄金用例 `PASS`，退出码 0。任何 `FAIL` 都意味着双端算法漂移，**必须修复后才能提交**。

### 4.4 校验引擎未被修改

```powershell
python tools/engine_hash.py --check
```

> 该命令对比 `allin_engine` 目录的 SHA256 哈希基线。若哈希不匹配，说明引擎文件被意外修改（违反只读铁律）。

---

## 5. 高级配置

### 5.1 自定义存档位置

**方式一：`--data-dir` 命令行参数（推荐，每次启动指定）**

```powershell
python main.py --data-dir <数据目录>
```

存档将写入 `<数据目录>\saves\autosave.json`。

**方式二：环境变量持久化设置**

```powershell
# 设置为自定义目录
setx ALLIN_USER_DATA "<数据目录>"

# 验证
echo %ALLIN_USER_DATA%
```

> **注意**：`ALLIN_USER_DATA` 必须在 Python 进程启动时就已经设置好。引擎的 `paths.py` 在模块导入期读取该变量，运行时修改无效。

**方式一与方式二的关系**：`--data-dir` 在 `main.py` 中解析后会设置 `ALLIN_USER_DATA` 环境变量，效果与方式二相同，但只在当前会话生效。如果需要永久生效，使用方式二。

### 5.2 自定义引擎位置

如果 `allin_engine` 不在项目内置的 `<仓库根>\tools\allin_engine`：

```powershell
setx ALLIN_ENGINE_HOME "<allin_engine 目录>"
```

### 5.3 便携部署

如果希望程序完全不依赖 `%APPDATA%`（例如放在 U 盘上使用）：

```powershell
# 假设程序在 U 盘 X:\fish
X:
cd X:\fish
python main.py --data-dir X:\fish\userdata
```

存档将保存在 `X:\fish\userdata\saves\`，与程序放在同一介质上。

### 5.4 强制无托盘模式

即使 `pystray` 已安装，也可以强制走降级路径：

```powershell
python main.py --no-tray
```

此模式适用于以下场景：
- 桌面上托盘图标过多，不想再增加一个
- 自动化/CI 环境中运行
- 调试托盘相关问题

---

## 附录 A：快速命令速查

| 操作 | 命令 |
|------|------|
| 正常启动 | `python main.py` |
| 安全自检 | `python main.py --safe` |
| 无头模拟 60 秒 | `python main.py --headless 60` |
| 自定义存档目录 | `python main.py --data-dir <数据目录>` |
| 强制无托盘 | `python main.py --no-tray` |
| 恢复隐藏窗口 | `Ctrl+Alt+F` |
| 打开存档目录 | `explorer %APPDATA%\LazyFishTank\saves` |
| 备份存档 | `copy "%APPDATA%\LazyFishTank\saves\autosave.json" backup.json` |
| 从 .bak 恢复 | `copy "%APPDATA%\LazyFishTank\saves\autosave.json.bak" "%APPDATA%\LazyFishTank\saves\autosave.json"` |
| 运行全部测试 | `python -m pytest` |
| 黄金用例验证 | `python -m pytest tests/test_offline_golden.py -v` |

## 附录 B：存档字段容错原则

程序对存档采用**宽松容错策略**：

- **任何字段缺失** → 用游戏默认值补齐 + 记录 warning
- **任何字段类型错误** → 用游戏默认值替换 + 记录 warning
- **解析失败** → 自动回退 `.bak` 文件
- **绝不清档** → 绝不抛异常终止程序

这意味着：即使手动编辑存档 JSON 出了错，程序会尽力挽救可用部分，不会丢失全部进度。

---

*文档结束 · 项目运行说明见 `README.md` · 架构设计见 `docs/ARCHITECTURE.md`*
