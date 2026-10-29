@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  探险日志 — PyInstaller 打包脚本
echo ========================================
echo.

REM 配置：自发现 Python（不写死本机路径）
REM   Windows 有官方启动器 py 时优先用它；否则回退 PATH 里的 python。
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE ( where python >nul 2>nul && set "PYEXE=python" )
if not defined PYEXE (
    echo [X] 找不到 Python。请安装 Python 3.x 并确保 py 或 python 在 PATH 中。
    pause
    exit /b 1
)
REM   PyInstaller 用 `-m PyInstaller` 调用：不再依赖 Scripts 目录位置，
REM   同时修掉原来「把 pyinstaller.exe 当脚本路径传给 python.exe」的调用错误。
set "PYINSTALLER=-m PyInstaller"

REM 1. 清理旧构建（保留 .spec 文件）
if exist build rd /s /q build
if exist dist rd /s /q dist

REM 2. 确保 Excel 存在
if not exist "config\game_data.xlsx" (
    echo [*] 生成 game_data.xlsx...
    %PYEXE% gen_excel.py
)

REM 3. PyInstaller 打包
echo [1/3] 打包中...
%PYEXE% %PYINSTALLER% --onefile --windowed --name "探险日志" --add-data "data;data" --hidden-import pystray --hidden-import pystray._win32 --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw --hidden-import openpyxl --hidden-import ctypes --hidden-import gui.views --hidden-import gui.views.base --hidden-import gui.tabs.wilderness_tab --hidden-import core.game_loop --hidden-import hashlib main.py
if !errorlevel! neq 0 (
    echo [X] 打包失败
    pause
    exit /b 1
)

REM 4. 复制 Excel
echo [2/3] 复制 game_data.xlsx...
copy /y "config\game_data.xlsx" "dist\game_data.xlsx" >nul
echo   OK

REM 5. 显示结果
echo [3/3] 完成!
echo.
for %%F in ("dist\探险日志.exe") do set size=%%~zF
set /a size_mb=!size! / 1048576
echo   dist\探险日志.exe   (!size_mb! MB)
echo   dist\game_data.xlsx (可编辑)
echo.
echo ========================================
echo  打包完成! 直接分发 dist\ 目录即可。
echo ========================================
pause
