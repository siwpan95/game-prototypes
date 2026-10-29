// render_fish.cpp —— 用 fish_painter 画鱼

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "render_fish.h"
#include "../core/ft_str.h"

namespace ft { namespace gui {

// 窗口中心
static const UINT32 kCx = 320;
static const UINT32 kCy = 200;

/// 将 Prim 的局部坐标换算为 XJ380 画布坐标并渲染
static void render_prim(HDLE handle, const Prim& prim, f64 ox, f64 oy,
                        bool flip, const FishSpeciesDef* sp) {
    // 颜色映射（对偶 FishPainter.color_for）
    u32 color = 0x8899AA;
    switch (prim.role) {
    case ROLE_BODY:    color = (sp != FT_NULL) ? sp->color_body    : 0x8899AA; break;
    case ROLE_BELLY:   color = (sp != FT_NULL) ? sp->color_belly   : 0xB8C4CE; break;
    case ROLE_FIN:     color = (sp != FT_NULL) ? sp->color_fin     : 0x9AA7B2; break;
    case ROLE_ACCENT:  color = (sp != FT_NULL) ? sp->color_pattern : 0x2B2F36; break;
    case ROLE_EYE:     color = 0x101418; break;
    case ROLE_EYE_HL:  color = 0xFFFFFF; break;
    case ROLE_OUTLINE: color = 0x2B2F36; break;
    }

    f64 sx = flip ? -1.0 : 1.0;

#ifdef __XJ380_OS__
    if (prim.n_points > 0) {
        // 多边形：用线条描边
        for (i32 i = 0; i < prim.n_points; ++i) {
            i32 j = (i + 1) % prim.n_points;
            UINT32 x1 = (UINT32)(ox + prim.points[2 * i] * sx);
            UINT32 y1 = (UINT32)(oy + prim.points[2 * i + 1]);
            UINT32 x2 = (UINT32)(ox + prim.points[2 * j] * sx);
            UINT32 y2 = (UINT32)(oy + prim.points[2 * j + 1]);
            xapi_DrawLine(handle, x1, y1, x2, y2, color);
        }
        // 简单填充：用水平扫描线
        // （完整三角/多边形填充需要光栅化算法，这里用线条近似）
    } else if (prim.kind == PRIM_OUTLINE) {
        f64 l = prim.cx - prim.rx;
        f64 r = prim.cx + prim.rx;
        f64 t = prim.cy - prim.ry;
        f64 b = prim.cy + prim.ry;
        if (flip) {
            f64 tmp = ox + r * sx; r = ox + l * sx; l = tmp;
            l = ox + (prim.cx - prim.rx) * sx;
            r = ox + (prim.cx + prim.rx) * sx;
            if (l > r) { f64 tt = l; l = r; r = tt; }
        }
        UINT32 x0 = (UINT32)(ox + l * sx);
        UINT32 y0 = (UINT32)(oy + t);
        UINT32 x1 = (UINT32)(ox + r * sx);
        UINT32 y1 = (UINT32)(oy + b);
        if (x0 > x1) { UINT32 tt = x0; x0 = x1; x1 = tt; }
        xapi_DrawRect(handle, x0, y0, x1, y1, color, false);
    } else {
        // 椭圆 / 圆 / 半椭圆：用包围矩形 + DrawSvg 近似
        f64 l = prim.cx - prim.rx;
        f64 r = prim.cx + prim.rx;
        f64 t = prim.cy - prim.ry;
        f64 b = prim.cy + prim.ry;
        UINT32 x0 = (UINT32)(ox + l * sx);
        UINT32 y0 = (UINT32)(oy + t);
        UINT32 x1 = (UINT32)(ox + r * sx);
        UINT32 y1 = (UINT32)(oy + b);
        if (x0 > x1) { UINT32 tt = x0; x0 = x1; x1 = tt; }
        // 用椭圆 SVG
        UINT32 w = x1 - x0;
        UINT32 h = y1 - y0;
        if (w > 0 && h > 0) {
            WSTR svg = (WSTR)L"<svg><ellipse cx='50%' cy='50%' rx='50%' ry='50%'/></svg>";
            xapi_DrawSvg(handle, x0, y0, w, svg, false);
        }
    }
#else
    (void)handle; (void)ox; (void)oy; (void)flip; (void)color;
#endif
}

void render_all_fish(HDLE handle, const GameState& state,
                     const FishLibrary& species_lib, const BalanceTable& bal,
                     f64 base_len) {
#ifdef __XJ380_OS__
    const f64* stage_scale_arr = FT_NULL;
    f64 ss[4];
    ss[0] = bal.num("growth.stage_scale.fry", 0.45);
    ss[1] = bal.num("growth.stage_scale.juvenile", 0.70);
    ss[2] = bal.num("growth.stage_scale.adult", 1.00);
    ss[3] = bal.num("growth.stage_scale.mature", 1.10);
    stage_scale_arr = ss;

    Prim prims[kMaxPrims];

    for (i32 i = 0; i < state.n_fishes; ++i) {
        const FishState& f = state.fishes[i];
        const FishSpeciesDef* sp = species_lib.get(f.species);

        f64 shape_len   = (sp != FT_NULL) ? sp->shape_length       : 1.0;
        f64 shape_ratio = (sp != FT_NULL) ? sp->shape_height_ratio : 0.4;
        const char* tail= (sp != FT_NULL) ? sp->shape_tail         : "fork";
        const char* pattern = "none";
        i32 outline = 0;

        f64 phase = 0.25;  // 固定相位（在动画时由帧循环更新）

        i32 n = fish_geometry(shape_len, shape_ratio, tail,
                              f.stage, phase, base_len,
                              stage_scale_arr, pattern, outline,
                              prims, kMaxPrims);

        // 鱼在缸内的像素坐标
        f64 ox = kCx + (f.x - 0.5) * 400.0;  // 映射 [0,1] → 画布
        f64 oy = kCy + (f.y - 0.5) * 300.0;
        bool flip = f.heading < 0.0;

        for (i32 k = 0; k < n; ++k) {
            render_prim(handle, prims[k], ox, oy, flip, sp);
        }
    }
#else
    (void)handle; (void)state; (void)species_lib; (void)bal; (void)base_len;
#endif
}

} }  // namespace ft::gui
