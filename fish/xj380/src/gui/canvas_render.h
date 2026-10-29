// canvas_render.h —— 画布背景渲染

#ifndef FT_GUI_CANVAS_RENDER_H
#define FT_GUI_CANVAS_RENDER_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "../core/data_defs.h"
#include "../core/state.h"

namespace ft { namespace gui {

/// 渲染鱼缸背景（渐变水面 + 玻璃边框）。
void canvas_render_background(HDLE handle, const GameState& state,
                              const BalanceTable& bal);

} }  // namespace ft::gui

#endif
