// hud.h —— 抬头显示（金币、鱼数、水质条）

#ifndef FT_GUI_HUD_H
#define FT_GUI_HUD_H

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "../core/data_defs.h"
#include "../core/state.h"

namespace ft { namespace gui {

/// 渲染 HUD 叠加层。
void render_hud(HDLE handle, const GameState& state, const BalanceTable& bal);

} }  // namespace ft::gui

#endif
