# M3 模拟层 · 交付概览（mc_clone_gui / D:\allin\example）

## 一句话总结
在 M1（GUI 垂直切片）+ M2（生存基底）之上，完成 M3「模拟层」：启用 Z 层级多层世界、温度/水/岩浆流体模拟、DF 式挖掘·建造作业系统。全量 **193 测试通过 / 0 失败**，1 个真实源码 Bug（流体碰撞丢质量）已修复闭环。

## 团队与流程
标准 SOP 增量（架构 → 工程 → QA）：
- 团队 `software-minecraft-m3`（主理人齐活林 → 高见远架构师 → 寇豆码工程师 → 严过关 QA）
- M3 设计：`docs/architecture_m3.md`（13 条任务 T-M3-01~13 + 类图 + 时序图 + R5/R6 风险）

## 关键决策
- **Z 层级启用**：地基 `BlockWorld` 已支持 depth>1，但 `terrain.py` 不可改 → 新建 `worldgen/multilayer.py`，z=0 调 `TerrainGenerator` 生成并拷贝，z≥1 用 `random.Random(seed)` 程序化填充；`depth=8`，底部 z=depth-1 填岩浆湖。确定性可复现。
- **模拟层**：`WorldSim`（温度扩散 + 水/岩浆流动，脏 chunk 机制，≤20Hz 节流）；温度场岩浆格恒高温并向下扩散；水每 tick 流 1 步、岩浆每 4 tick 流 1 步（更慢）。
- **作业系统**：`JobSystem`（DF 式 dig/build 作业——玩家指派 → 队列 → 逐 tick 推进 → 完成改世界 → 可取消）。
- **渲染/交互**：`Camera.current_z` 真正生效（Z/X 切层、钳制 depth 范围）；`TileWorldRenderer` 按层渲染 + 温度/水/岩浆覆盖层 tint；HUD 增 Z 层指示、覆盖层开关、作业列表；键位避开冲突（W 已为跳跃，水/岩浆覆盖层改用 V）。

## 文件清单（M3 增量，地基零改动）
新建：`worldgen/__init__.py`、`worldgen/multilayer.py`、`simulation/__init__.py`、`simulation/cell.py`、`simulation/world_sim.py`、`simulation/overlays.py`、`systems/jobs.py`、`data/blocks.m3.json`、`docs/architecture_m3.md` + 2 张 Mermaid 图
改造（M1/M2）：`camera.py`、`tile_world_renderer.py`、`player.py`、`main_gui.py`、`hud.py`、`mouse_input.py`、`event_bus.py`
测试：`tests/test_m3_*.py`（30 项）+ QA 补 `tests/test_qa_m3_logic.py`（8 项）

## 质量与验证
- 全量 **193 passed / 0 failed**（M1 96 + M2 52 + M3 38）
- QA 第 1 轮独立验证发现 1 个真实源码 Bug → 工程师修复 → 主理人亲自 Bash 确认 193 绿
- 雷区 R5（地基零改动）、R6（lava=8 经 `register(from_json(m3).get(8))` 稳健注册）、R1（滚轮顺序）均确认未触发

## 已知限制 / 待办
1. **GUI 窗口需真实显示环境手测**：多层瓦片、温度蓝→红 tint、水/岩浆 tint、作业 HUD 观感需人眼目检。
2. **疑点 B（已修复）**：`_flow_target` 同层两侧流动缺「侧下方须为 AIR」约束，水会向无支撑侧向扩一格。已于 M3 交付后在 `world_sim.py` `_flow_target` 方法补修（第126-142行，含"侧下方须有支撑"约束），M3 验收不受影响。
3. **QA 第 2 轮回归因 500 基础设施错误中断**：主理人已独立验证 193 全绿替代确认。
4. 续做 M4（生物/精灵/刷怪）、M5（群系/洞穴/存档/PyInstaller 打包）。
