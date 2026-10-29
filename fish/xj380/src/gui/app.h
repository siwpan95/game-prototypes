// ═══════════════════════════════════════════════════════════════════════
//  app.h —— XJ380 GUI 主入口
// ═══════════════════════════════════════════════════════════════════════
//
// XJ380 EPF 应用程序入口。启动时创建窗口、装载数据、进入渲染循环。

#ifndef FT_GUI_APP_H
#define FT_GUI_APP_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif

#include "ft_types.h"

namespace ft { namespace gui {

/// 应用初始化：装载数据、创建窗口。
/// :returns: 0 = 成功，非 0 = 失败。
i32 app_init();

/// 主循环：每帧渲染一次。
void app_run();

/// 清理资源。
void app_shutdown();

} }  // namespace ft::gui

#endif  // FT_GUI_APP_H
