"""gui/panels —— 各视图/操作面板的渲染函数（无 self 的自由函数）。

每个模块导出若干 draw_*(canvas, state, callbacks) 自由函数：
  character_view.py  draw_character_card / draw_gauges         —— 角色卡 / 仪表盘
  pathways_view.py   draw_pathway_list / draw_pathways_view    —— 序列途径列表与全途径视图
  groups_view.py     draw_groups_view                          —— 权柄体系（途径组）视图
  action_panel.py    draw_action_panel / draw_collection_panel / draw_old_one_panel
                                                                 —— 操作面板（扮演/晋升/权柄收集/旧日晋升）
  log_panel.py       add_log / draw_log                        —— 事件日志（写与画分离）

面板不持有根窗口、不引用 GUI 实例：canvas 是兼容 tkinter.Canvas 接口的对象，
state 提供 character/old_one_info/fonts/pathway_items/event_log，callbacks 是
{动作名: 处理器} 字典。因此每个面板都能被完全独立的单元测试覆盖。
"""
