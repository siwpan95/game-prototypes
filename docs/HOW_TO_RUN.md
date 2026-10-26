# PQ Multiverse - 启动说明

## 🚀 快速启动

### 方法 1：使用启动脚本（推荐）

```bash
cd D:\allin\stay\pq_multiverse\src
python run_pq_ui.py
```

### 方法 2：直接运行 UI

```bash
cd D:\allin\stay\pq_multiverse\src
python -c "import tkinter as tk; from ui.tkinter_ui_pq import PQMainWindow; root = tk.Tk(); app = PQMainWindow(root, theme_name='diablo'); root.mainloop()"
```

---

## 🎮 游戏流程

### 1. 启动后
- 会弹出"创建角色"对话框
- 输入角色名称（默认：黑暗流浪者）
- 选择种族（人类、恶魔、天使）
- 选择职业（战士、盗贼、巫师）
- 点击"开始冒险"

### 2. 游戏界面
- **第 1 列**：人物信息（名称、种族、职业、等级）
- **第 2 列**：装备（武器、护甲、饰品）
- **第 3 列**：PQ 状态（当前行动、进度条、队列长度）
- **第 4 列**：游戏日志
- **底部**：行动状态栏（当前任务、进度）
- **控制按钮**：开始、暂停、保存、加载

### 3. 游戏机制（PQ 架构）
- **队列系统**：任务按顺序执行
- **Tick 引擎**：每 50ms 推进一次进度
- **经验获取**：每次 tick 获得经验
- **升级**：经验达到阈值后升级
- **装备获取**：击败怪物后有机会获得装备
- **市场系统**：负重满后自动去市场出售战利品

---

## 🐛 测试检查清单

### ✅ 基础功能
- [ ] 角色创建成功
- [ ] 游戏启动后，当前行动显示"Executing XXX"
- [ ] 进度条正常推进
- [ ] 队列长度 > 0（任务完成后会自动生成新任务）

### ✅ 游戏循环
- [ ] 完成任务后，自动生成新任务
- [ ] 获得经验和金币
- [ ] 升级后属性提升
- [ ] 获得新装备

### ✅ 控制功能
- [ ] 暂停/恢复按钮正常工作
- [ ] 保存/加载功能正常
- [ ] 日志正常显示

---

## 🐛 常见问题

### 问题 1：无法启动，提示"No module named 'tkinter'"
**解决方案**：确保使用 system Python（通常自带 tkinter）
```bash
# 检查 Python 路径
which python
# 或
where python

# 使用完整路径运行
C:\Users\13122\AppData\Local\Programs\Python\Python314\python.exe run_pq_ui.py
```

### 问题 2：启动后没有反应
**可能原因**：
- 主题加载失败
- 角色创建失败

**解决方案**：
1. 检查控制台输出（应该有"✅ 引擎创建成功"等消息）
2. 尝试使用其他主题（修改 `run_pq_ui.py` 中的 `theme_name`）

### 问题 3：游戏运行，但队列长度始终为 0
**可能原因**：任务完成后没有正确生成新任务

**解决方案**：
1. 检查 `core/tick_engine.py` 的 `_select_next_action()` 方法
2. 运行 `test_headless.py` 验证后端逻辑

---

## 📊 性能优化

如果发现游戏运行卡顿：
1. 增加 Tick 间隔（修改 `core/tick_engine.py` 的 `TICK_INTERVAL_MS`）
2. 减少 UI 更新频率（修改 `ui/tkinter_ui_pq.py` 的更新逻辑）

---

## 📝 开发笔记

### PQ 架构核心文件
- `core/queue_system.py`：队列系统
- `core/tick_engine.py`：Tick 引擎
- `core/monster_task_generator.py`：怪物任务生成器
- `core/equipment_generator.py`：装备生成器
- `core/deterministic_rng.py`：确定随机数生成器

### UI 文件
- `ui/tkinter_ui_pq.py`：PQ 架构版 UI
- `themed_engine_pq.py`：PQ 架构版引擎

### 测试文件
- `test_headless.py`：无头测试（验证后端逻辑）
- `test_core_architecture.py`：核心架构测试
- `test_multi_theme.py`：多主题测试

---

## 🚀 下一步

1. **测试完整游戏循环**：在本地运行 UI，观察游戏流程
2. **调整主题数据**：根据测试结果调整 `themes/data/*.json` 中的平衡性
3. **完善 UI**：根据需要调整界面布局和显示

---

**祝你游戏愉快！** 🎮
