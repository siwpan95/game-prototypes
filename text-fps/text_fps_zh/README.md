# 文字FPS 战术射击（text_fps_zh）

文字界面（由 **pygame_ce** 渲染）的回合制 FPS 战术射击游戏。玩家在房间之间移动、利用掩体、管理弹药与道具，逐关清剿敌人直至通关。

> 项目根目录：本 README 所在目录（`text_fps_zh/`）

## 环境要求

- **Python 3.12+**（CI 门禁使用 Python 3.13）
- 操作系统：Windows / Linux / macOS（需要 SDL 图形环境；无显示器环境无法启动游戏窗口，但可跑导入门禁，见下）
- 运行依赖：`pygame_ce`（导入名，详见下方「⚠️ 重要：依赖名称说明」）

## 安装与启动

```bash
# 1) 安装依赖（发行名是 pygame-ce，连字符）
pip install -r requirements.txt

# 2) 启动游戏
python main.py
```

窗口（1024×768）打开后即进入第 1 关。

### ⚠️ 重要：依赖名称说明（务必读）

`requirements.txt` 里写的是**发行名 `pygame-ce`**（连字符），但**代码里导入的是 `pygame_ce`**（下划线）：

```python
# main.py:6-9 / ui/renderer.py:5-8
try:
    import pygame_ce as pygame
except ImportError:
    import pygame
```

- **发行名（pip 安装用，连字符）**：`pygame-ce`
- **导入名（代码里 `import` 用，下划线）**：`pygame_ce`

二者拼写不同是 pygame 社区版（Community Edition）的命名惯例，**不是笔误**。

- 请按上面的命令安装，不要因为看到 `pygame_ce` 就去 `pip install pygame_ce`（那不是正确的发行名）。
- 反之，也不要因为 `requirements.txt` 写的是 `pygame-ce` 就以为代码里该写 `import pygame-ce`（语法不允许连字符）。
- `scripts/import_smoke.py` 的依赖可达性门禁会自动把 `pygame-ce` 映射到 `pygame_ce` / `pygame` 尝试导入，CI 因此能通过。

## 操作说明（键盘 + 鼠标）

| 按键 | 动作 |
|------|------|
| `F` | 开火（攻击当前锁定敌人） |
| `A` | 瞄准（提升命中率） |
| `R` | 换弹 |
| `G` | 投掷手雷 |
| `C` | 进入掩体 |
| `W` / `S` / `D` 或 `↑` / `↓` / `→` | 向北 / 南 / 东 移动 |
| `←` | 向西移动 |
| `P` | 拾取地面物品 |
| `Tab` | 切换武器 |
| 鼠标左键 | 点击 UI 按钮；滚轮上下滚动日志 |
| `N` | 游戏结束 / 胜利后开新游戏 |

> 存档位置：`saves/save_slot_{1..3}.json`（项目根目录下的 `saves/`）。详见 [RUNBOOK.md](RUNBOOK.md) 第三、四节。

## 项目结构

| 目录 | 职责 |
|------|------|
| `core/` | 游戏状态、常量、事件总线 |
| `systems/` | 战斗 / 移动 / 背包 / 潜行等系统逻辑 |
| `models/` | 实体模型（敌人、武器、物品） |
| `save/` | 存档读写（JSON） |
| `data/` | 敌人 / 武器 / 关卡 等静态模板数据 |
| `ui/` | pygame 渲染与面板 |
| `scripts/` | `import_smoke.py` 导入冒烟 + 依赖可达性门禁 |

## 更多文档

- [RUNBOOK.md](RUNBOOK.md) — 事故响应与部署手册（启动/停止、启动失败排查、存档回滚、发布前检查）
- [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md) — 代码格式 / 命名 / 类型注解规范
