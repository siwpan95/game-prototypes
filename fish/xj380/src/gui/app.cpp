// ═══════════════════════════════════════════════════════════════════════
//  app.cpp —— XJ380 应用程序入口
// ═══════════════════════════════════════════════════════════════════════

#ifdef __XJ380_OS__
#include "xguiapi.h"
#include "libsys.h"
#endif

#include "app.h"
#include "window.h"
#include "canvas_render.h"

#include "../core/data_defs.h"
#include "../core/state.h"
#include "../core/economy.h"
#include "../core/rng.h"
#include "../core/json_min.h"

namespace ft { namespace gui {

// ── 全局对象 ──
static HDLE                g_hwnd = 0;
static BalanceTable        g_bal;
static FishLibrary         g_species;
static DecorLibrary        g_decor;
static GameState           g_state;
static DetRandom           g_rng;

// JSON 文档（必须在对象存活期内有效）
static JsonDoc  g_bal_doc;   static JsonNode g_bal_pool[4096];
static JsonDoc  g_fish_doc;  static JsonNode g_fish_pool[8192];
static JsonDoc  g_decor_doc; static JsonNode g_decor_pool[2048];

// 外部 JSON 数据指针（由链接脚本提供或 objcopy 嵌入）
// 当前版本：EPF 内不嵌入 JSON，使用 hardcoded fallback 进行编译测试
#ifdef __XJ380_OS__
// extern "C" const char _binary_data_balance_json_start[];
// extern "C" const char _binary_data_balance_json_end[];
// 留待后续通过 objcopy 嵌入 JSON 后再启用
#endif

static bool load_json_doc(JsonDoc* doc, const char* start, const char* end) {
    i32 len = static_cast<i32>(end - start);
    // 原地解析需要可写缓冲区；JSON 数据嵌入为 const，需要复制
    // 在宿主环境用栈上拷贝（足够小），在 XJ380 用 alloc
#ifdef __XJ380_OS__
    char* buf = (char*)malloc((size_t)(len + 1));
    if (buf == FT_NULL) return false;
#else
    static char buf[65536];
    if (len >= 65536) return false;
#endif
    for (i32 i = 0; i < len; ++i) buf[i] = start[i];
    buf[len] = '\0';
    bool ok = doc->parse(buf, len);
#ifdef __XJ380_OS__
    // buf 由 parse 原地改写后仍需保留，暂不释放
#endif
    return ok;
}

#ifdef __XJ380_OS__
// ── 消息回调 ──
static void msg_callback(UINT64 type, UINT64 hData, UINT64 lData) {
    (void)hData;
    (void)lData;
    if (type == 1) {  // WM_CLOSE
        app_shutdown();
    }
}
#endif

i32 app_init() {
    g_rng.restore(kDefaultSeed);

#ifdef __XJ380_OS__
    g_bal_doc.init(g_bal_pool, 4096);
    g_fish_doc.init(g_fish_pool, 8192);
    g_decor_doc.init(g_decor_pool, 2048);

    // 使用硬编码的最小 JSON（后续通过 objcopy 嵌入完整 data/*.json）
    static char bal_json[] = "{\"economy\":{\"coin_scale\":1000,\"base_income\":{\"R1\":1.0}},\"water\":{\"min\":50,\"max\":100,\"init\":100,\"decay_per_fish\":0.03,\"filter_gain\":[0,0.2,0.5,1.2],\"quality_floor\":0.5},\"feeder\":{\"output_floor\":0.85,\"satiety_min\":0,\"satiety_max\":1,\"decay_per_min\":0.012,\"feed_gain\":0.5,\"auto_feed_level\":0.6},\"shop\":{\"capacity\":[6]},\"offline\":{\"hard_cap_sec\":315360000,\"segments\":[[0,480,1.0],[480,1440,0.6],[1440,null,0.35]],\"fine_step_sec\":60,\"fine_limit_sec\":86400,\"coarse_step_sec\":3600}}";
    static char fish_json[] = "[]";
    static char decor_json[] = "[]";

    if (!g_bal_doc.parse(bal_json, sizeof(bal_json) - 1)) return 1;
    if (!g_fish_doc.parse(fish_json, sizeof(fish_json) - 1)) return 1;
    if (!g_decor_doc.parse(decor_json, sizeof(decor_json) - 1)) return 1;

    g_bal.bind(&g_bal_doc, g_bal_doc.root());
    g_species.load(g_fish_doc, g_fish_doc.root());
    g_decor.load(g_decor_doc, g_decor_doc.root());

    // 创建新档
    g_state.new_game(g_bal, g_species, 0);

    // 创建窗口
    window_create(&g_hwnd);
    SetMsgPrcor(g_hwnd, msg_callback);
#else
    // Host 环境：只做初始化，不创建窗口
    g_state.clear();
#endif
    return 0;
}

void app_run() {
#ifdef __XJ380_OS__
    while (1) {
        // 渲染一帧
        canvas_render_background(g_hwnd, g_state, g_bal);
        // TODO: render fishes, decor, HUD

        xapi_RefreshWindow(g_hwnd);

        // 简易帧率控制（约 15fps，对偶 loop.xj_render_hz）
        // 在实际 XJ380 上可以用 sleep/定时器
    }
#endif
}

void app_shutdown() {
#ifdef __XJ380_OS__
    if (g_hwnd != 0) {
        xapi_CloseWindow(g_hwnd);
        g_hwnd = 0;
    }
#endif
}

// ── 外部存取 ──
HDLE app_hwnd()          { return g_hwnd; }
const BalanceTable& app_bal()      { return g_bal; }
const FishLibrary&  app_species()  { return g_species; }
const DecorLibrary& app_decor()    { return g_decor; }
GameState&          app_state()    { return g_state; }
DetRandom&          app_rng()      { return g_rng; }

} }  // namespace ft::gui
