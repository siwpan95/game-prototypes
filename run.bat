@echo off
chcp 65001 >nul
title 十二试炼：神话重构
echo ========================================
echo            十二试炼：神话重构
echo ========================================
echo.
echo  [1] 运行打包版本 (exe)
echo  [2] 运行源码版本 (Tkinter 图形界面)
echo  [3] 运行源码版本 (控制台模式)
echo  [4] 运行源码版本 (Pygame 图形界面)
echo.
set /p choice="请选择 (1/2/3/4，默认1): "

if "%choice%"=="2" goto :tkinter
if "%choice%"=="3" goto :console
if "%choice%"=="4" goto :gui
if "%choice%"=="" goto :exe
if "%choice%"=="1" goto :exe

:exe
echo.
echo 正在启动十二试炼...
if exist "%~dp0dist\十二试炼.exe" (
    start "" "%~dp0dist\十二试炼.exe"
) else (
    echo [提示] 未找到打包版本 exe，将启动 Tkinter 源码版本...
    python main.py
)
goto :end

:tkinter
echo.
echo 正在启动 Tkinter 图形界面...
python main.py
goto :end

:console
echo.
echo 正在启动控制台版本...
python main.py --ui=console
pause
goto :end

:gui
echo.
echo 正在启动 Pygame 图形界面...
python main.py --ui=pygame
pause

:end
echo.
echo 再见，英雄！
