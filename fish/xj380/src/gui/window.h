// window.h —— XJ380 窗口管理

#ifndef FT_GUI_WINDOW_H
#define FT_GUI_WINDOW_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif

#include "ft_types.h"

namespace ft { namespace gui {

/// 创建养鱼窗口（640x400，对偶 ui.xj_size）。
/// :returns: true = 成功。
bool window_create(HDLE* out_handle);

} }  // namespace ft::gui

#endif
