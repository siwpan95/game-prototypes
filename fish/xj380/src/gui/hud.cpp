// hud.cpp —— HUD 渲染

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "hud.h"

#include "../core/ft_str.h"

namespace ft { namespace gui {

static const UINT32 kHudText  = 0xDDEAF2;
static const UINT32 kBarBg    = 0x0E3346;
static const UINT32 kBarGood  = 0x57C7A0;
static const UINT32 kBarMid   = 0xE8C05A;
static const UINT32 kBarLow   = 0xD98A6A;

void render_hud(HDLE handle, const GameState& state, const BalanceTable& bal) {
#ifdef __XJ380_OS__
    // 金币显示
    char coin_buf[32];
    i64 coins = state.coins_milli;
    i32 scale = bal.coin_scale();
    if (scale <= 0) scale = 1000;
    f64 gold = static_cast<f64>(coins) / static_cast<f64>(scale);
    fmt_fixed(coin_buf, 32, gold, 1);

    xapi_DrawText(handle, 8, 8, (WSTR)coin_buf, 16, kHudText);

    // 鱼数
    char count_buf[16];
    fmt_i64(count_buf, 16, state.fish_count());

    xapi_DrawText(handle, 8, 28, (WSTR)count_buf, 14, kHudText);

    // 水质条
    UINT32 bar_x = 540;
    UINT32 bar_y = 8;
    UINT32 bar_w = 90;
    UINT32 bar_h = 14;
    xapi_DrawRect(handle, bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, kBarBg, true);

    f64 water = state.tank.water;
    f64 lo = bal.water_min();
    f64 hi = bal.water_max();
    f64 t = (hi > lo) ? (water - lo) / (hi - lo) : 1.0;
    if (t < 0.0) t = 0.0; if (t > 1.0) t = 1.0;
    UINT32 fill_w = (UINT32)(t * (f64)bar_w);

    UINT32 bar_color = kBarGood;
    if (t < 0.4) bar_color = kBarLow;
    else if (t < 0.7) bar_color = kBarMid;

    if (fill_w > 0) {
        xapi_DrawRect(handle, bar_x, bar_y, bar_x + fill_w, bar_y + bar_h, bar_color, true);
    }
#else
    (void)handle; (void)state; (void)bal;
#endif
}

} }  // namespace ft::gui
