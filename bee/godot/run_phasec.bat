@echo off
chcp 65001 >nul
setlocal
title BeeIdleRPG - Phase C 一键启动

REM ================= 配置（路径有变动时只改这里）=================
REM BEE_ROOT: bee 项目根（本 bat 在 godot\ 下，上一级即根）
set "BEE_ROOT=%~dp0.."
REM GODOT_EXE: 运行游戏用 GUI 版（非 _console 版）
REM 2026-09-23 去本地化：优先取同名环境变量，其次探测常见安装位置；都没有则由下方错误分支提示设置
REM 2026-09-23 去本地化：删除已失效的原路径 候选（保留本机 F: 安装位置探测 + PATH 探测）
if not defined GODOT_EXE for %%G in ("F:\Godot-4.7.1\Godot_v4.7.1-stable_win64.exe") do if exist "%%~G" set "GODOT_EXE=%%~G"
REM PYTHON: 起 bridge 的解释器（优先同名环境变量，其次 PATH 里的 python）
if not defined PYTHON set "PYTHON=python"
REM PORT: 必须与 sim_bridge.gd 里的 const PORT 一致，改这里也要同步改那里
set "PORT=18765"
REM =============================================================

if not exist "%PYTHON%" set "PYTHON=python"

if not exist "%GODOT_EXE%" (
    echo [错误] 找不到 Godot 可执行文件：
    echo        %GODOT_EXE%
    echo 请用记事本打开本脚本，修改顶部 GODOT_EXE 变量后重试。
    pause
    exit /b 1
)

echo [1/2] 启动 sim_core 桥接服务（端口 %PORT%，独立窗口保持运行）...
start "BeeIdleRPG sim_core bridge (port %PORT%)" /d "%BEE_ROOT%" cmd /k %PYTHON% -m src.sim_core.bridge --port %PORT%

echo       等待 bridge 就绪（约 2 秒）...
timeout /t 2 /nobreak >nul

echo [2/2] 启动 Godot 前端（等价 F5 运行 game.tscn）...
"%GODOT_EXE%" --path "%~dp0."

echo.
echo Godot 已退出。前端退出时会向 bridge 发送 quit；
echo 若 bridge 窗口仍开着，切到该窗口按 Ctrl-C 关闭即可。
endlocal
