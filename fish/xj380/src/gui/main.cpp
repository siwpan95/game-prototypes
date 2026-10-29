// main.cpp —— XJ380 EPF 入口点
// 对偶 Python 端 __main__.py，由 start.cpp.o CRT 调用

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif

#include "app.h"
#include "window.h"
#include "canvas_render.h"
#include "render_fish.h"
#include "render_decor.h"
#include "hud.h"

// 外部声明（app.cpp 中定义）
namespace ft { namespace gui {
    extern HDLE              app_hwnd();
    extern const BalanceTable& app_bal();
    extern const FishLibrary&  app_species();
    extern const DecorLibrary& app_decor();
    extern GameState&          app_state();
} }

extern "C" int main() {
    int ret = ft::gui::app_init();
    if (ret != 0) return ret;

    // 主消息循环
#ifdef __XJ380_OS__
    while (1) {
        // 渲染
        HDLE hwnd = ft::gui::app_hwnd();
        const ft::BalanceTable& bal = ft::gui::app_bal();
        const ft::FishLibrary& sp  = ft::gui::app_species();
        const ft::DecorLibrary& dc = ft::gui::app_decor();
        ft::GameState&      st = ft::gui::app_state();

        ft::gui::canvas_render_background(hwnd, st, bal);
        ft::gui::render_all_fish(hwnd, st, sp, bal, 46.0);
        ft::gui::render_all_decor(hwnd, st, dc);
        ft::gui::render_hud(hwnd, st, bal);

        xapi_RefreshWindow(hwnd);

        // 简易帧率控制（~15fps）
        volatile int wait = 0;
        for (int i = 0; i < 500000; ++i) { wait += i; }
    }
#endif
    return 0;
}
