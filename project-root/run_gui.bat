@echo off
chcp 65001 >nul
title 诡秘之主 - 序列途径模拟系统
echo.
echo    🜃 诡秘之主 序列途径模拟系统 v2.1
echo    Canvas Edition - GUI 图形界面
echo.
echo    启动中……
echo.
cd /d "%~dp0"
python gui_app.py
pause
