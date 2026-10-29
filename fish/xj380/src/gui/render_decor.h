// render_decor.h —— 装饰物渲染

#ifndef FT_GUI_RENDER_DECOR_H
#define FT_GUI_RENDER_DECOR_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "../core/data_defs.h"
#include "../core/state.h"

namespace ft { namespace gui {

/// 渲染缸底装饰物。
void render_all_decor(HDLE handle, const GameState& state,
                      const DecorLibrary& decor_lib);

} }  // namespace ft::gui

#endif
