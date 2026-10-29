@echo off
REM Endless Highway 3D —— 运行环境初始化（对齐 3dworld-demos 约定）
REM
REM 用法：双击或命令行执行后，在本窗口内运行  python main.py
REM   python main.py             正常游玩
REM   python main.py --smoke 3   冒烟 3 秒后自动关闭
REM   python main.py --size 1280x720
REM
REM 说明：3dworld（pip 安装）的 platform.app 用 WORLD3D_PROJECT_ROOT 定位
REM 截图/文档落点；本仓不使用 cordis 配置树，故不设置 WORLD3D_CONFIGS。

set WORLD3D_PROJECT_ROOT=%CD%
REM 若虚拟环境尚未创建，可先建好：  python -m venv .venv
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
