# RUNBOOK — 文字FPS（text_fps_zh）事故响应与部署手册

> 配套依据：综合工程审查与事故响应报告（2026-07-25，SEV-1 启动崩溃演练）。
> 适用范围：本地启动失败排查、发布前检查、存档回滚。
> 本手册不修改任何游戏源码，仅描述操作流程。

## 何时使用本手册

- 游戏窗口打不开 / 启动即崩溃（**SEV-1 级**，所有用户受阻，零可玩会话）
- 改了某文件后导入报错（`ImportError` / `ModuleNotFoundError` / `NameError`）
- 发布前做上线检查
- 存档损坏或需回退到旧进度

## 前置条件与所需权限

- Python 3.12+ 与 `pygame_ce`（`pip install -r requirements.txt`）
- 能在**有显示器**的机器上运行（游戏需要 SDL 图形环境）
- 改动源码需走 PR + CI 导入门禁；回滚存档只需文件读写权限

## 一、启动与停止

**启动：**

```bash
pip install -r requirements.txt
python main.py
```

**停止：**

- 正常退出：关闭窗口（`QUIT` 事件），或游戏内结束。
- 强制终止：从启动它的终端按 `Ctrl+C`；若卡死，结束进程 `python main.py`
  （`pkill -f "python main.py"`，或 Windows 任务管理器）。

## 二、常见启动失败排查

| 现象 | 可能根因 | 排查 / 修复 |
|------|----------|------------|
| 启动即崩，报 `ImportError: cannot import name 'Dict'` 之类的 `NameError` | 某模块漏写 `from typing import Dict/List/Optional`（如 `data/enemies.py` / `data/weapons.py` 曾漏写 `Dict`），被 `systems/movement` 等下游导入时连带崩 | 给该模块补回对应 `typing` 导入；跑 `python scripts/import_smoke.py` 看 `FAIL` 列表，锁定是哪个模块 |
| `ModuleNotFoundError: No module named 'pygame_ce'` | 未装依赖，或把发行名 `pygame-ce` 与导入名 `pygame_ce` 搞混 | 重新 `pip install -r requirements.txt`；确认装的是发行名 `pygame-ce` |
| `ModuleNotFoundError: No module named 'shared'`（或其子模块） | 旧版 **F1 启动崩溃**——硬 `import` 一个不存在的 `shared.font_utils` 包 | 必须改为 `try/except ImportError` 可选导入 + 回退（已在 `ui/renderer.py` 落地）。若再出现，说明有人重引入了裸硬依赖，回退该改动 |
| 窗口打开，但中文显示成 □ / 豆腐块 | CJK 字体缺失，回退到仅英文的 Fira Code / pygame 默认字体（**不崩，仅显示问题**） | 系统安装中文字体，或在 `assets/fonts/` 放置 CJK 字体并让 `ui.font_utils.load_cjk_font` 命中 |
| `python main.py` 闪退、无任何窗口 | 多为上述导入错误 | 先在无头环境跑门禁定位：`python scripts/import_smoke.py` 看 `FAIL`，或在本地 `python -c "import main"` 看完整 traceback |

**核心门禁（CI 已配置，`.github/workflows/ci.yml`）：**

每次 push / PR 跑 `python scripts/import_smoke.py`：

- 导入 `core/ systems/ models/ save/ data/`（不含依赖 pygame 的 `main.py` / `ui/`）下的全部模块；
- 校验 `requirements.txt` 中每个依赖可按**模块名**导入（含 `pygame-ce` → `pygame_ce` 映射）；
- 任一失败 → 打印 `GATE_FAIL`、退出码非 0 → **CI 失败，阻断合并**。
- 本地可在无显示器机器上直接跑该脚本——**这是预防"导入即崩"类 bug 的首要手段**。

## 三、存档位置与回滚

- **位置**：项目根目录下的 `saves/save_slot_{1..3}.json`（共 3 个槽，见 `core/constants.py` 的 `SAVE_DIR` / `MAX_SAVE_SLOTS`）。
- **格式**：JSON，含 `_meta`（`schema_version` / `slot` / `level` / `turn` / `player_health`）。
- **回滚思路**：
  1. 存档是纯文本 JSON。某槽损坏 / 进度异常 → 直接删除对应 `save_slot_{n}.json`，从该槽重新开档。
  2. 想回退到某次"好"的进度 → 用备份的 `save_slot_{n}.json` 覆盖回去（建议发布前对 `saves/` 做快照）。
  3. 旧格式（无 `levels` 键）会被 `SaveManager.load` 兼容回退重建；但若关卡改名可能导致 `current_room=None` 软锁——遇到即删除该槽重开。
  4. **关键**：启动期崩溃发生在读档之前，因此导入类事故**不会损坏已有存档**（无用户数据损失，爆炸半径仅限启动路径）。
- **回滚代码（发布事故）**：保留上一稳定构建，发布流水线支持一键回退到上一版本（目标 ≤15min，见报告行动项 #4）。

## 四、发布前检查清单要点

- [ ] **导入门禁通过**：`python scripts/import_smoke.py` 打印 `IMPORT_SMOKE_OK`（CI 已卡，但本地再跑一遍）
- [ ] **依赖可达**：`requirements.txt` 中每个依赖都能按模块名导入；`pygame-ce`（发行名）/ `pygame_ce`（导入名）区分清晰
- [ ] **字体自检降级**：无 CJK 字体时游戏仍能启动（回退而非中止）
- [ ] **存档版本**：存档含 `schema_version`，旧档可迁移 / 兼容
- [ ] **无未登记内部包的硬 import**：任何 `from xxx import ...` 都有 `try/except` 或真实依赖（防 F1 复发）
- [ ] **回滚就绪**：上一稳定构建可用，回退流程 ≤15min
- [ ] **通报**：SEV 级事故触发复盘（见报告配套事故复盘模板）

## 五、SEV-1 升级路径

1. **分诊**：启动崩溃率 100% → 判 **SEV-1**，开战情室、全员响应。
2. **缓解**：先回滚到上一稳定构建（止血），再修根因——不要在线上直接改。
3. **永久修复 + 验证**：CI 导入冒烟 + 手动 100% + 遥测恢复 → 关单。
4. **复盘**：文档沉淀到 `docs/`（按报告配套事故复盘模板），含时间线 / 影响 / 5-Why / 改进项 / 预防 / 经验教训。
