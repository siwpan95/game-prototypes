"""gui 包 —— 诡秘之主序列途径模拟系统的 Canvas 图形界面。

gui_app.py 已拆为：
  theme.py        颜色主题 / 塔罗图标 / 字体路径 / 字体注册
  drawing.py      Canvas 自绘辅助（圆角矩形 / 弧形仪表 / 排序键 / 换行）
  state.py        GUIState 运行时状态中介
  app.py          LordOfMysteriesGUI 主类（窗口骨架 + 组合各 mixin）
  panels/         character_view / pathways_view / groups_view / action_panel / log_panel
  controllers.py  所有 _do_* 操作处理器

入口仍可用 `python gui_app.py`（薄启动器）。

为保证从任意目录 import 时项目模块（pathways_data 等）可被解析，
这里把项目根加入 sys.path（幂等）。
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
