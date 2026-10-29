// ═══════════════════════════════════════════════════════════════════════
//  fish_painter.h —— 程序化画鱼几何（双端共享规范）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：pyapp/fish_painter.py::geometry()（纯函数区）
//
// 坐标系约定（C++ 端照抄）：
//   * 原点 = 鱼的中心；+x 指向鱼头朝向（永远画成朝右，朝左由渲染层水平镜像）。
//   * 单位 = 归一化体长。L = shape.length * base_len * stage_scale[stage]
//   * rx = L / 2，ry = rx * height_ratio
//   * phase ∈ [0, 1) 是摆尾相位，尾尖 y 偏移 = sin(2π·phase) * rx * TAIL_SWING
//
// 绘制顺序 = 列表顺序，后画的盖前面的：
//   尾鳍 → 背鳍 → 腹鳍 → 身体 → 腹部 → 花纹 → 眼睛 → 描边

#ifndef FT_CORE_FISH_PAINTER_H
#define FT_CORE_FISH_PAINTER_H

#include "ft_types.h"
#include "data_defs.h"

namespace ft {

// ── 图元类型 ──
enum PrimKind {
    PRIM_ELLIPSE      = 0,
    PRIM_ELLIPSE_HALF = 1,
    PRIM_POLYGON      = 2,
    PRIM_CIRCLE       = 3,
    PRIM_OUTLINE      = 4
};

// ── 语义角色（决定用哪个颜色）──
enum PrimRole {
    ROLE_BODY    = 0,
    ROLE_BELLY   = 1,
    ROLE_FIN     = 2,
    ROLE_ACCENT  = 3,
    ROLE_EYE     = 4,
    ROLE_EYE_HL  = 5,
    ROLE_OUTLINE = 6
};

// ── 常量 ──
static const f64 kTailSwing = 0.25;
static const f64 kEyeX = 0.55;
static const f64 kEyeY = -0.25;
static const f64 kEyeR = 0.22;
static const f64 kEyeHlR = 0.08;
static const f64 kBellyRy = 0.55;
static const f64 kBellyCy = 0.35;
static const f64 kDorsalH = 0.55;
static const i32 kStripeCount = 4;
static const i32 kSpotCount = 5;

// 多边形顶点数上限
static const i32 kMaxPolyPts = 16;
// 图元总数上限
static const i32 kMaxPrims = 32;

// ── 图元 ──
struct Prim {
    u8  kind;       // PrimKind
    u8  role;       // PrimRole
    f64 cx;
    f64 cy;
    f64 rx;
    f64 ry;
    f64 points[2 * kMaxPolyPts];  // (x, y) 交替
    i32 n_points;
    f64 width;      // OUTLINE 用

    Prim() : kind(0), role(0), cx(0), cy(0), rx(0), ry(0), n_points(0), width(0) {}
};

// ── 函数声明 ──

/// 算出鱼的半长 rx 与半高 ry。对偶 body_size()。
/// :param shape_len: fish_data.json shape.length
/// :param shape_ratio: shape.height_ratio
/// :param stage: fry / juvenile / adult / mature
/// :param base_len: 基准体长（像素）
/// :param stage_scale: 阶段缩放表（BalanceTable 读取），NULL 用内置兜底
/// :returns: (rx, ry)
void fish_body_size(f64 shape_len, f64 shape_ratio, const char* stage,
                    f64 base_len, const f64* stage_scale,
                    f64* out_rx, f64* out_ry);

/// ★ 生成一条鱼的完整图元列表。对偶 geometry()。
/// :param shape_len: shape.length
/// :param shape_ratio: shape.height_ratio
/// :param shape_tail: "fork" / "fan" / "round" / "long"
/// :param stage: 成长阶段
/// :param phase: 摆尾相位 [0, 1)
/// :param base_len: 基准体长
/// :param stage_scale: 阶段缩放数组 [fry, juvenile, adult, mature]，NULL 用默认
/// :param pattern: "none" / "stripes" / "spots"
/// :param outline: 0 / 1 / 2
/// :param out_prims: 输出图元数组
/// :param max_prims: 输出数组容量
/// :returns: 实际生成的图元数
i32 fish_geometry(f64 shape_len, f64 shape_ratio, const char* shape_tail,
                  const char* stage, f64 phase, f64 base_len,
                  const f64* stage_scale, const char* pattern, i32 outline,
                  Prim* out_prims, i32 max_prims);

/// 包围盒。对偶 bounding_box()。
void fish_bounding_box(const Prim* prims, i32 n,
                       f64* min_x, f64* min_y, f64* max_x, f64* max_y);

}  // namespace ft

#endif  // FT_CORE_FISH_PAINTER_H
