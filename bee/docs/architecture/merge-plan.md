# G:games 项目并入计划（P0–P2）与执行记录

> 日期：本会话 | 目标：将 G:games 下可复用项目按优先级并入 bee

## P0 — pq_multiverse 主题并入（✅ 已完成）

**方案**：主题包机制 —— 「JSONPool.set_theme()」使 src/resources/themes/<id>/
下的同名 JSON 优先于默认 resources/data/，缺失文件自动回退。
「SimCore(theme=...)」显式复位单例池，防止跨实例泄漏（黄金基准零影响）。

**已导入 10 个主题**（tools/import_pq_themes.py / tools/import_pq_classic.py）：

| 主题 | 敌人 | 词缀 | 附加内容 |
|---|---|---|---|
| warcraft / diablo / genshin / pokemon / lol / final_fantasy / warhammer_40k / warhammer_fantasy / zelda | 271 | 19/主题 | spells 法术名 |
| pq_classic（progress_quest 经典 PQ） | 138 | 39 | 40 件 PQ 特殊宝物（神器 schema）、47 法术、21 种族、18 职业 |

**验证**：主题引擎 60s 无头运行 ✓；主题复位（145 敌人/107 词缀）✓；
pytest 7/7（默认路径不受影响）✓。

## P1 — 内容与健壮性（✅ 已完成）

1. **stay 式存档容错**（engine._load_game）：JSON 解析/恢复异常 → 自动备份为
   save.json.corrupt-<ts> 并新建游戏；字段缺失仅告警不动原文件。
2. **DDA 反馈回路补全**（顺手修复的死亡螺旋）：
   - 阵亡现在上报 on_combat_end(False) → 回血抑制 +0.25/场
   - _restart_game 用 load_dict(old.to_dict()) 继承上世抑制状态
   - 稀有度按等级门控：Lv<5 仅普通、<10 精英、<20 稀有、传说 Lv≥20；
     词缀数收敛到 _max_affixes(level)
   - 效果：1 小时无头模拟阵亡 115 → 0，Lv.5 / 164 击杀全程稳定
3. **回归**：黄金基准重新生成（17 行），pytest 7/7、smoke 120 局、编译全过。

## P2 — 酒馆小游戏房间（设计，未实施）

**目标**：把 G:games 下的小游戏变成 bee 城镇/酒馆里的「小游戏房间」。

**架构模式**（借鉴 hell below 启动器：shared_core + 独立游戏目录）：
- 小游戏全部放在 **GUI 层**（bee 已有 src/app/controllers/），**绝不进 sim_core**
  （sim_core 引擎无关红线：零 tkinter/pygame 依赖，黄金测试守卫）。
- 通过 **IPC/事件桥** 与模拟内核交互（沿用 M2 的 src/sim_core/bridge.py 模式）：
  小游戏结算 → 桥接指令 → sim_core 发放金币/经验/道具。
- 首期房间候选（零依赖，直接可嵌）：
  2048（CLI→tkinter 适配）、Snake-master、Tic-Tac-Toe、ice（SkiFree）、
  moyuxiaqi、merged_gui 的井字棋/掷硬币类、aotuplay。
- 二期（需 pygame，放独立进程经桥接接入）：Endless Highway（旅行小游戏）、
  darksouls（Boss 卡牌战）、oddtown。

**不并入原因（记录在案）**：
- MCclone / mahjong / kard / loly / cheatcard / text_fps / TavernRogue / dungeon：
  绑定 pygame/allin_engine，与挂机内核无交集；强行并入破坏 sim_core 引擎无关约束。
- carimara_py（366MB 类库）、fish（2GB 内嵌 Python）、math / legend_demo
  （加密分发）、russia（PyInstaller 产物）：非游戏项目或不可维护。
- maga / paotuan / moba_battle_platform / project_root / mahjong：完整度高的独立作品。
- TwelveLabors / Life Reset Simulator：数据可借鉴（任务/事件卡），引擎各自独立；
  后续可经转换器按需抽取内容（本次仅做 pq_multiverse/progress_quest 两个最高价值源）。
