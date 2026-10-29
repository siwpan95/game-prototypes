// fish_painter.cpp —— 见 fish_painter.h。◆ 对偶 pyapp/fish_painter.py

#include "fish_painter.h"

#include "ft_math.h"
#include "ft_str.h"

namespace ft {

// 阶段缩放兜底（对偶 _DEFAULT_STAGE_SCALE）
static const f64 kDefaultStageScale[4] = { 0.45, 0.70, 1.00, 1.10 };

/// stage 名 → 兜底数组下标
static i32 stage_idx(const char* stage) {
    if (str_eq(stage, kStageFry))      return 0;
    if (str_eq(stage, kStageJuvenile)) return 1;
    if (str_eq(stage, kStageAdult))    return 2;
    return 3;  // mature 或未知
}

// ══════════════════════════════════════════════════════════════
//  尺寸
// ══════════════════════════════════════════════════════════════

void fish_body_size(f64 shape_len, f64 shape_ratio, const char* stage,
                    f64 base_len, const f64* stage_scale,
                    f64* out_rx, f64* out_ry) {
    f64 length = (shape_len > 0.0) ? shape_len : 1.0;
    f64 ratio  = (shape_ratio > 0.0) ? shape_ratio : 0.4;

    f64 sc;
    if (stage_scale != FT_NULL) {
        sc = stage_scale[stage_idx(stage)];
    } else {
        sc = kDefaultStageScale[stage_idx(stage)];
    }
    if (sc <= 0.0) sc = 1.0;

    f64 total = length * base_len * sc;
    f64 rx = total * 0.5;
    *out_rx = rx;
    *out_ry = rx * ratio;
}

// ══════════════════════════════════════════════════════════════
//  摆尾偏移
// ══════════════════════════════════════════════════════════════

static f64 tail_tip_dy(f64 rx, f64 phase) {
    return sin_(2.0 * kPi * phase) * rx * kTailSwing;
}

// ══════════════════════════════════════════════════════════════
//  部件
// ══════════════════════════════════════════════════════════════

static void emit_ellipse(Prim* p, u8 role, f64 cx, f64 cy, f64 rx, f64 ry) {
    p->kind = PRIM_ELLIPSE;
    p->role = role;
    p->cx = cx; p->cy = cy;
    p->rx = rx; p->ry = ry;
    p->n_points = 0; p->width = 0;
}

static void emit_ellipse_half(Prim* p, u8 role, f64 cx, f64 cy, f64 rx, f64 ry) {
    p->kind = PRIM_ELLIPSE_HALF;
    p->role = role;
    p->cx = cx; p->cy = cy;
    p->rx = rx; p->ry = ry;
    p->n_points = 0; p->width = 0;
}

static void emit_circle(Prim* p, u8 role, f64 cx, f64 cy, f64 r) {
    p->kind = PRIM_CIRCLE;
    p->role = role;
    p->cx = cx; p->cy = cy;
    p->rx = r; p->ry = r;
    p->n_points = 0; p->width = 0;
}

static void emit_outline(Prim* p, f64 rx, f64 ry, f64 w) {
    p->kind = PRIM_OUTLINE;
    p->role = ROLE_OUTLINE;
    p->cx = 0; p->cy = 0;
    p->rx = rx; p->ry = ry;
    p->n_points = 0; p->width = w;
}

static i32 emit_polygon(Prim* p, u8 role, const f64 pts[][2], i32 n) {
    p->kind = PRIM_POLYGON;
    p->role = role;
    p->cx = 0; p->cy = 0;
    p->rx = 0; p->ry = 0;
    p->n_points = 0; p->width = 0;
    if (n > kMaxPolyPts) n = kMaxPolyPts;
    for (i32 i = 0; i < n; ++i) {
        p->points[2 * i]     = pts[i][0];
        p->points[2 * i + 1] = pts[i][1];
    }
    p->n_points = n;
    return n;
}

// ── 身体 ──

static void part_body(Prim* p, f64 rx, f64 ry) {
    emit_ellipse(p, ROLE_BODY, 0.0, 0.0, rx, ry);
}

static void part_belly(Prim* p, f64 rx, f64 ry) {
    emit_ellipse_half(p, ROLE_BELLY, 0.0, ry * kBellyCy,
                      rx * 0.92, ry * kBellyRy);
}

// ── 尾鳍 ──

static i32 part_tail(Prim* out, i32 cap, f64 rx, f64 ry,
                     const char* tail, f64 phase) {
    f64 dy = tail_tip_dy(rx, phase);
    f64 root_x = -rx * 0.92;
    f64 span   = rx * 0.55;
    f64 tip_x  = -rx - span;
    f64 h      = ry * 1.35;
    i32 n = 0;

    if (str_eq(tail, "fork")) {
        // 双三角：上/下各一片
        if (n < cap) {
            f64 upper[][2] = { {root_x, 0.0}, {tip_x, -h + dy}, {-rx * 0.55, -ry * 0.15} };
            emit_polygon(&out[n], ROLE_FIN, upper, 3);
            ++n;
        }
        if (n < cap) {
            f64 lower[][2] = { {root_x, 0.0}, {tip_x, h + dy}, {-rx * 0.55, ry * 0.15} };
            emit_polygon(&out[n], ROLE_FIN, lower, 3);
            ++n;
        }
    } else if (str_eq(tail, "fan")) {
        // 五点扇
        if (n < cap) {
            f64 pts[][2] = {
                {root_x, 0.0},
                {tip_x, -h * 0.95 + dy},
                {tip_x - span * 0.18, dy * 0.6},
                {tip_x, h * 0.95 + dy},
                {-rx * 0.6, 0.0}
            };
            emit_polygon(&out[n], ROLE_FIN, pts, 5);
            ++n;
        }
    } else if (str_eq(tail, "round")) {
        // 半椭圆：用折线逼近，保证 C++ 端也能用同样的点数复现
        if (n < cap) {
            f64 pts[10][2];
            pts[0][0] = root_x; pts[0][1] = 0.0;
            i32 steps = 8;
            for (i32 i = 0; i <= steps; ++i) {
                f64 a = -kPi * 0.5 + kPi * (static_cast<f64>(i) / static_cast<f64>(steps));
                pts[i + 1][0] = tip_x + span * (1.0 - cos_(a)) * 0.35;
                pts[i + 1][1] = sin_(a) * h * 0.9 + dy;
            }
            emit_polygon(&out[n], ROLE_FIN, pts, steps + 2);
            ++n;
        }
    } else {
        // long：四点飘带
        f64 long_span = span * 1.8;
        if (n < cap) {
            f64 pts[][2] = {
                {root_x, 0.0},
                {-rx - long_span * 0.5, -h * 0.7 + dy * 1.4},
                {-rx - long_span, dy * 2.0},
                {-rx - long_span * 0.5, h * 0.7 + dy * 1.4}
            };
            emit_polygon(&out[n], ROLE_FIN, pts, 4);
            ++n;
        }
    }
    return n;
}

// ── 背鳍 ──

static void part_dorsal(Prim* p, f64 rx, f64 ry, f64 phase) {
    f64 sway = sin_(2.0 * kPi * phase) * rx * 0.04;
    f64 pts[][2] = {
        {rx * 0.20, -ry * 0.95},
        {-rx * 0.10 + sway, -ry * (1.0 + kDorsalH)},
        {-rx * 0.45, -ry * 0.90}
    };
    emit_polygon(p, ROLE_FIN, pts, 3);
}

// ── 腹鳍 ──

static void part_pelvic(Prim* p, f64 rx, f64 ry, f64 phase) {
    f64 sway = sin_(2.0 * kPi * phase + kPi * 0.5) * ry * 0.10;
    f64 pts[][2] = {
        {rx * 0.10, ry * 0.72},
        {-rx * 0.10, ry * 1.15 + sway},
        {-rx * 0.30, ry * 0.70}
    };
    emit_polygon(p, ROLE_FIN, pts, 3);
}

// ── 眼睛 ──

static i32 part_eyes(Prim* out, i32 cap, f64 rx, f64 ry) {
    i32 n = 0;
    f64 ex = rx * kEyeX;
    f64 ey = ry * kEyeY;
    f64 er = ry * kEyeR;
    if (n < cap) {
        emit_circle(&out[n], ROLE_EYE, ex, ey, er);
        ++n;
    }
    if (n < cap) {
        emit_circle(&out[n], ROLE_EYE_HL,
                    ex + er * 0.35, ey - er * 0.35,
                    ry * kEyeHlR);
        ++n;
    }
    return n;
}

// ── 花纹 ──

static i32 part_pattern(Prim* out, i32 cap, f64 rx, f64 ry,
                        const char* pattern) {
    i32 n = 0;
    if (pattern == FT_NULL || pattern[0] == '\0' || str_eq(pattern, "none")) {
        return 0;
    }
    if (str_eq(pattern, "stripes")) {
        for (i32 i = 0; i < kStripeCount && n < cap; ++i) {
            f64 t = (static_cast<f64>(i) + 1.0) / static_cast<f64>(kStripeCount + 1);
            f64 cx = rx * (0.45 - 1.30 * t);
            f64 inside = 1.0 - (cx / rx) * (cx / rx);
            f64 half_h = ry * sqrt_(fmax_(0.0, inside)) * 0.92;
            f64 w = rx * 0.055;
            f64 pts[][2] = {
                {cx - w, -half_h}, {cx + w, -half_h},
                {cx + w, half_h},  {cx - w, half_h}
            };
            emit_polygon(&out[n], ROLE_ACCENT, pts, 4);
            ++n;
        }
    } else if (str_eq(pattern, "spots")) {
        for (i32 i = 0; i < kSpotCount && n < cap; ++i) {
            f64 t = (static_cast<f64>(i) + 1.0) / static_cast<f64>(kSpotCount + 1);
            f64 cx = rx * (0.40 - 1.20 * t);
            f64 cy = ry * ((i % 2) ? 0.30 : -0.28);
            f64 r = ry * 0.20;
            emit_circle(&out[n], ROLE_ACCENT, cx, cy, r);
            ++n;
        }
    }
    return n;
}

// ── 描边 ──

static i32 part_outline(Prim* out, i32 cap, f64 rx, f64 ry, i32 level) {
    if (level <= 0 || cap < 1) return 0;
    emit_outline(&out[0], rx, ry, static_cast<f64>(level));
    return 1;
}

// ══════════════════════════════════════════════════════════════
//  ★ geometry() —— 主入口
// ══════════════════════════════════════════════════════════════

i32 fish_geometry(f64 shape_len, f64 shape_ratio, const char* shape_tail,
                  const char* stage, f64 phase, f64 base_len,
                  const f64* stage_scale, const char* pattern, i32 outline,
                  Prim* out_prims, i32 max_prims) {
    f64 rx, ry;
    fish_body_size(shape_len, shape_ratio, stage, base_len, stage_scale, &rx, &ry);
    if (rx <= 0.0 || ry <= 0.0) return 0;

    // 尾鳍类型
    if (shape_tail == FT_NULL || shape_tail[0] == '\0') shape_tail = "fork";

    i32 n = 0;

    // 绘制顺序 = 列表顺序，后画的盖前面的：
    // 尾鳍 → 背鳍 → 腹鳍 → 身体 → 腹部 → 花纹 → 眼睛 → 描边

    n += part_tail(out_prims + n, max_prims - n, rx, ry, shape_tail, phase);
    if (n < max_prims) { part_dorsal(&out_prims[n], rx, ry, phase); ++n; }
    if (n < max_prims) { part_pelvic(&out_prims[n], rx, ry, phase); ++n; }
    if (n < max_prims) { part_body(&out_prims[n], rx, ry); ++n; }
    if (n < max_prims) { part_belly(&out_prims[n], rx, ry); ++n; }
    n += part_pattern(out_prims + n, max_prims - n, rx, ry, pattern);
    n += part_eyes(out_prims + n, max_prims - n, rx, ry);
    n += part_outline(out_prims + n, max_prims - n, rx, ry, outline);

    return n;
}

// ══════════════════════════════════════════════════════════════
//  包围盒
// ══════════════════════════════════════════════════════════════

void fish_bounding_box(const Prim* prims, i32 n,
                       f64* min_x, f64* min_y, f64* max_x, f64* max_y) {
    if (n <= 0) {
        *min_x = 0; *min_y = 0; *max_x = 0; *max_y = 0;
        return;
    }
    f64 x0 = 1e30, y0 = 1e30, x1 = -1e30, y1 = -1e30;
    for (i32 i = 0; i < n; ++i) {
        const Prim& p = prims[i];
        if (p.n_points > 0) {
            for (i32 k = 0; k < p.n_points; ++k) {
                f64 px = p.points[2 * k];
                f64 py = p.points[2 * k + 1];
                if (px < x0) x0 = px; if (px > x1) x1 = px;
                if (py < y0) y0 = py; if (py > y1) y1 = py;
            }
        } else {
            f64 lx = p.cx - p.rx;
            f64 rx2 = p.cx + p.rx;
            f64 ty = p.cy - p.ry;
            f64 by = p.cy + p.ry;
            if (lx < x0) x0 = lx; if (rx2 > x1) x1 = rx2;
            if (ty < y0) y0 = ty; if (by > y1) y1 = by;
        }
    }
    *min_x = x0; *min_y = y0; *max_x = x1; *max_y = y1;
}

}  // namespace ft
