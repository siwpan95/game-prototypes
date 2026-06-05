@echo off
chcp 65001 >nul
echo ======================================
echo       十二试炼：神话重构
echo ========================================
echo.
echo [1] 运行打包版本 (exe)
echo [2] 运行源码版本 (控制台模式)
echo [3] 运行源码版本 (GUI模式 - pygame_ce)
echo.
set /p choice="选择 (1/2/3，默认1): "

if "%choice%"=="2" goto :console
if "%choice%"=="3" goto :gui
if "%choice%"=="" goto :exe
if "%choice%"=="1" goto :exe

:exe
echo.
echo 正在启动十二试炼...
start "" "%~dp0dist\十二试炼.exe"
goto :end

:console
echo.
echo 正在启动控制台版本...
python main.py
pause
goto :end

:gui
echo.
echo 正在启动 GUI 版本...
python main.py --gui
pause

:end
echo.
echo 再见，英雄！
