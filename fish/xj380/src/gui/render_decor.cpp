// render_decor.cpp —— 装饰物渲染（底部简单形状）

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "render_decor.h"

namespace ft { namespace gui {

static const UINT32 kWinH = 400;
static const UINT32 kWinW = 640;

void render_all_decor(HDLE handle, const GameState& state,
                      const DecorLibrary& decor_lib) {
#ifdef __XJ380_OS__
    // 每个装饰物渲染为底部的一个小色块
    i32 n = state.tank.n_decors;
    if (n == 0) return;
    UINT32 slot_w = kWinW / (UINT32)n;
    for (i32 i = 0; i < n; ++i) {
        const DecorDef* dd = decor_lib.get(state.tank.decors[i]);
        if (dd == FT_NULL) continue;
        UINT32 x0 = (UINT32)i * slot_w + 4;
        UINT32 y0 = kWinH - 32;
        UINT32 x1 = x0 + slot_w - 8;
        UINT32 y1 = kWinH - 2;
        xapi_DrawRect(handle, x0, y0, x1, y1, dd->color0, true);
        xapi_DrawRect(handle, x0, y0 - 4, x1, y0, dd->color1, true);
    }
#else
    (void)handle; (void)state; (void)decor_lib;
#endif
}

} }  // namespace ft::gui
