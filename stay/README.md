# Progress Quest 2 — The Progression（Python / Tkinter 移植版）

一个单人进度放置类游戏（Progress Quest 2）的 Python + Tkinter 移植实现。
包含完整的角色养成、战斗、装备、任务、剧情、商店系统，以及一套面向"不可信存档"
的健壮存档机制。

> 文档语言：本仓库的说明文档（含本文件）以中文为主，命令与代码标识符保留英文。

---

## 1. 环境要求

- Python **≥ 3.10**
- 依赖：`numpy`（兼容区间 `>=1.24,<3`，由 `requirements.txt` / `pyproject.toml` 声明）
- 操作系统：Windows（GUI 依赖 `tkinter` + Win32 `AddFontResourceEx` 注册中文字体；
  字体回退逻辑在其它平台也能运行，但中文显示效果依赖系统字体）

---

## 2. 快速开始

```bash
# 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt

# 启动游戏（Windows 下用 .pyw 避免弹出控制台）
python main.pyw
# 或显式加载某个存档
python main.pyw --savefile savefile.pq2
```

开发依赖（测试）：

```bash
pip install -e ".[dev]"     # pyproject.toml 中声明了 pytest
# 或直接
pip install pytest
```

---

## 3. 目录结构

```
G:\stay
├── main.pyw                # 入口（Tkinter GUI 启动 + 可选 --savefile 自愈加载）
├── pyproject.toml          # 项目元数据 / 依赖治理（#12）
├── requirements.txt        # 运行时依赖（numpy 兼容区间，#11）
├── settings.json           # 用户配置：{"theme": "...", "is_cn": true}
├── savefile.pq2(.bak)      # 当前存档及其备份
├── assets/
│   └── STKAITI.TTF         # 华文楷体（2026-07-27 起归档至此，由 gui 加载）
├── scripts/
│   └── _run_pytest.py      # 本地跑全套测试的便捷脚本（输出 pytest_out.txt）
├── docs/                   # 复盘 / 审查文档（见第 8 节）
├── pq2/                    # 游戏包
│   ├── game.py             # Game：存档 / 新游戏 / 主循环 / 战斗 / 装备 / 任务 / 剧情
│   ├── serializer.py       # 存档序列化（gzip+JSON）、A6 信封、schema 校验、gzip 炸弹防护
│   ├── localization.py     # 中英本地化字典 + 缺键监控（A11）
│   ├── themes.py           # 三套视觉主题
│   ├── types.py            # LoadError / SaveError / GameState 等枚举
│   ├── newgame.py          # 自动投骰
│   ├── data/               # 种族 / 职业 / 法术 / 武器 / 盾牌 / 盔甲 / 怪物 / 特殊物品 … 数据
│   ├── gui/                # Tkinter GUI（tkinter_gui.py 为主实现）
│   └── utils/              # 名称生成 / 复数 / 罗马数字等工具
└── tests/                  # pytest 回归套件
```

---

## 4. 存档格式与健壮性

存档为 **gzip 压缩的 JSON**，落地于 `*.pq2`。经过两轮加固，已能抵御不可信 / 损坏存档：

| 能力 | 说明 | 代码锚点 |
|------|------|----------|
| **A6 信封** | JSON 顶层携带 `version` + `mac`（HMAC-SHA256，与荷载分离），防止静默篡改 | `serializer` 的 `version` / `mac` 字段 |
| **schema 校验（#1）** | 反序列化后校验 Level≥1、数值类型、枚举范围，拒绝畸形数据 | `serializer.deserialize` |
| **原子写（#4）** | 先写临时文件 + `os.replace`，并保留上一版为 `.bak` | `serializer.save_to_file` |
| **gzip 炸弹防护（#3）** | 限制解压后最大体积并分块读取 | `serializer._SaveTooLargeError` |
| **损坏分层（ADR-001）** | 信封/结构损坏 → `LoadError.Corrupt`；数据层非法 → `LoadError.NotValidSaveFile` | `types.LoadError.Corrupt` |
| **A7 启动自愈** | 主档损坏 → 隔离为 `*.corrupt`（不删除）→ 回退 `.bak` → 成功则回填主档 | `game.load_game_with_recovery` |

> 旧格式（无 `version` 字段）会被**容忍**并以软警告加载，保证向后兼容。

---

## 5. 本地化（A11 缺键监控）

- 中文翻译基于 `localization.TRANSLATION_TABLE` 字典；`get_cn(text)` 做精确键查找。
- 显式键查找若缺失翻译，会通过 `record_missing_key` 记入 `MISSING_KEYS` 注册表
  （`get_missing_keys()` 可取回），用于 i18n 可观测性——**不再静默回退英文**。
- 启动时 `TkGUI` 调用 `audit_translation_coverage()` 审计翻译覆盖；审计范围刻意
  **排除**按设计应为英文的怪物名 / 特殊物品 / 物品属性，避免监控被噪声淹没。
- `translate()` 目前仍是子串替换（存在误伤专有名词的已知风险），基于词边界的精确匹配
  尚未实现（见第 9 节）。

---

## 6. 主题

`pq2/themes.py` 提供三套视觉主题：`original`（经典，默认）、`龙之皇冠`、`hollow-knight`
（空洞骑士）。主题由 `settings.json` 的 `theme` 字段选择。

字体统一使用 **STKaiti（华文楷体）**，由 `gui/tkinter_gui.py` 启动时通过 Win32
`AddFontResourceEx` 从 `assets/STKAITI.TTF` 注册；注册失败则回退到系统 CJK 字体。

---

## 7. 测试

```bash
# 方式一：直接跑
pytest tests -q

# 方式二：便捷脚本（路径自适应，输出 pytest_out.txt）
python scripts/_run_pytest.py
```

当前套件状态：**38 passed / 3 xfailed / 1 xpassed**（xfail 为刻意未做的范围外项，见下）。

---

## 8. 文档索引（`docs/`）

| 文档 | 内容 |
|------|------|
| `CODE_REVIEW_Cody.md` | 代码审查报告（#1–#16 缺陷清单）+ 修复状态追踪 |
| `incident-postmortem-pq2-savefile.md` | 存档损坏事故的无责复盘（A3–A7 / A11 设计）+ 状态更新 |
| `COORD_A3A4_Cody.md` | A3 / A4 修复协调记录 |
| `Docu-postmortem-review.md` | 对事故复盘文档的清晰度审查 |

---

## 9. 已知遗留（刻意未做，已以 `xfail(strict=False)` 跟踪）

- **A5 字体缺失显式告警**：字体路径（PyInstaller `_MEIPASS`）已修复，但"无任何可用
  CJK 字体时显式告警 / 抛 typed error"尚未实现，目前静默回退。
- **A11 基于词边界的 `translate`**：当前子串替换可能误伤包含修饰词前缀的专有名词，
  精确词边界匹配未实现（见 `tests/test_localization_regression.py`）。

---

## 10. 许可证

代码以本项目既有约定为准；`assets/STKAITI.TTF` 字体文件**未附带 LICENSE 标注**，
分发前需确认其授权（代码审查 #39 资源合规项）。
