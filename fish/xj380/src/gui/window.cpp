// window.cpp —— XJ380 窗口实现

#ifdef __XJ380_OS__
#include "xguiapi.h"
#endif
#include "window.h"

namespace ft { namespace gui {

static const UINT32 kWinW = 640;
static const UINT32 kWinH = 400;

bool window_create(HDLE* out_handle) {
#ifdef __XJ380_OS__
    XWINDOW xw;
    xw.width  = kWinW;
    xw.height = kWinH;
    xw.title  = (WSTR)L"懒人养鱼模拟器";
    xw.sets   = XWIN_NORMAL;
    xapi_CreateWindow(out_handle, &xw);
    return (*out_handle != 0);
#else
    (void)out_handle;
    return true;
#endif
}

} }  // namespace ft::gui
