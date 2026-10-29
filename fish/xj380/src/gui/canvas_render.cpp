// canvas_render.cpp —— 鱼缸背景渲染

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "canvas_render.h"

namespace ft { namespace gui {

// 窗口尺寸（对偶 balance.json::ui.xj_size）
static const UINT32 kW = 640;
static const UINT32 kH = 400;

// 颜色常量（对偶 balance.json::ui）
static const UINT32 kWaterTop    = 0x0A3A52;
static const UINT32 kWaterBottom = 0x062434;
static const UINT32 kGlassEdge   = 0x12506E;
static const UINT32 kChroma      = 0x010203;

void canvas_render_background(HDLE handle, const GameState& state,
                              const BalanceTable& bal) {
    (void)state;
    (void)bal;
#ifdef __XJ380_OS__
    // 色键清屏
    xapi_DrawRect(handle, 0, 0, kW, kH, kChroma, true);

    // 水面渐变：从上到下从亮到暗
    // 由于没有渐变 API，用 8 条水平色带近似
    UINT32 band_h = kH / 8;
    for (UINT32 i = 0; i < 8; ++i) {
        // 线性插值水色
        f64 t = static_cast<f64>(i) / 7.0;
        UINT32 r = (UINT32)(((kWaterTop >> 16) & 0xFF) * (1.0 - t) +
                            ((kWaterBottom >> 16) & 0xFF) * t);
        UINT32 g = (UINT32)(((kWaterTop >> 8) & 0xFF) * (1.0 - t) +
                            ((kWaterBottom >> 8) & 0xFF) * t);
        UINT32 b = (UINT32)((kWaterTop & 0xFF) * (1.0 - t) +
                            (kWaterBottom & 0xFF) * t);
        UINT32 color = (r << 16) | (g << 8) | b;
        xapi_DrawRect(handle, 0, i * band_h, kW, (i + 1) * band_h, color, true);
    }

    // 玻璃边框（2px）
    xapi_DrawRect(handle, 0, 0, kW, 2, kGlassEdge, true);       // 上
    xapi_DrawRect(handle, 0, kH - 2, kW, kH, kGlassEdge, true); // 下
    xapi_DrawRect(handle, 0, 0, 2, kH, kGlassEdge, true);       // 左
    xapi_DrawRect(handle, kW - 2, 0, kW, kH, kGlassEdge, true); // 右
#endif
}

} }  // namespace ft::gui
