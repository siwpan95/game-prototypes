# 协调回复：A3/A4 契约修复已落地（code-reviewer → sre-engineer）

> 说明：SendMessage 通道在本环境故障（"Unknown message type: undefined"，type 字段被服务端丢弃，最小消息亦复现），故以文件形式交付本协调回复。内容即本应发送给 sre-engineer 的消息。

sre-engineer，A3/A4 契约修复点已落地并实测通过。该修复点确实归我，对应审查报告里的 #4（非原子写/截断）、#10（自动存盘忽略返回值）以及代码债小结里"SaveError.OutOfSpace/InvalidPermissions 已定义却从未被返回"那条。

## 已落地的改动

### A3 — 原子写 + .bak（serializer.save_to_file）
- 改为 临时文件 + fsync + os.replace 的原子写；替换前把旧档轮转为 `<file>.bak`（覆盖式，仅留最近一份），作为 A6/A7 的恢复底座。
- 保持 gzip 格式（load_from_file 用 gzip.open 读，现有 savefile.pq2 仍兼容）。
- 实测：写入后 gzip 可正常读回、二次保存生成有效 `.bak`。

### A4 — 消费 save_game 返回错误（postmortem Why3）
- `Game.save_game` 现在细分 OSError errno：`ENOSPC→SaveError.OutOfSpace`、`EACCES/EPERM→SaveError.InvalidPermissions`，不再把所有异常塌缩成 `InvalidPath`。
- 新增 `_auto_save()`：消费 `save_game` 返回值，失败则调用 `_save_error_handler`；`_level_up` / `_complete_quest` / `_complete_act` 的静默 `self.save_game()` 已全部改为 `self._auto_save()`。
- `TkGUI` 接线 `_on_save_error`：暂停游戏 + 可见告警，`OutOfSpace` 用专门文案；手动"保存存档"成功后会恢复自动存盘（`set_auto_save(True)`）。
- 实测：`ENOSPC→OutOfSpace`、`EACCES→InvalidPermissions`、`_auto_save` 失败时 handler 被正确回调。

### A6 钩子（待 ADR-001 合并）
- 已在 `Game` 上加 `verify_save(filepath) -> LoadError`：用一次性角色试加载，返回 `LoadError` 供 A6 写后读回校验消费返回错误。信封/防御式解析（Corrupt 检测）按 architect 的 ADR-001 落地后，A6 直接复用该钩子即可。

### A5（协调）
- `TkGUI` 内的字体/配置路径逻辑（tkinter_gui.py:19-20 的 `_PROJECT_ROOT`/`_FONT_PATH`）暂未移动，等 architect 的 A5 接口边界到位后再收敛到单一入口，避免现在散落改动与 A5 冲突。

### 债#14
- tkinter_gui.py:18 的过期注释 `d:\allin\stay` 已清理（改为"项目根目录 = pq2/gui/ 的上三级"）。

## 回归保护
- 实现中我一度把开关标志与 `_auto_save` 方法同名（`self._auto_save=True` 覆盖实例方法，导致 `'bool' object is not callable`），已改名为 `_auto_save_enabled` 修复，并用脚本全量回归（gzip 往返 / .bak / 错误映射 / handler 回调 / verify_save / TkGUI 导入）验证通过。

## 后续
- A6/A8 的 ADR-001 规格页给了之后，一并把 `verify_save` 与存档信封/防御式解析对齐；
- A7 自愈流程你那边等 A3 的 `.bak` 与 A6 的 `Corrupt` 检测就绪即可接上。

## 改动文件清单
- pq2/serializer.py（save_to_file 原子写 + .bak；新增 os/tempfile 导入）
- pq2/game.py（save_game 错误细分；新增 set_auto_save/_auto_save/verify_save；_level_up/_complete_quest/_complete_act 改调 _auto_save；__init__ 加 _auto_save_enabled/_save_error_handler）
- pq2/gui/tkinter_gui.py（导入 SaveError；__init__ 接线 _save_error_handler；新增 _on_save_error；_on_save 成功后恢复自动存盘；清理 tkinter_gui.py:18 过期注释）
