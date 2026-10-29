// render_fish.h —— 用 fish_painter 画鱼到 XJ380 窗口

#ifndef FT_GUI_RENDER_FISH_H
#define FT_GUI_RENDER_FISH_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "../core/data_defs.h"
#include "../core/state.h"
#include "../core/fish_painter.h"

namespace ft { namespace gui {

/// 渲染缸内全部鱼。
/// :param base_len: 基准体长（像素），对偶 paint.base_len
void render_all_fish(HDLE handle, const GameState& state,
                     const FishLibrary& species_lib, const BalanceTable& bal,
                     f64 base_len);

} }  // namespace ft::gui

#endif
