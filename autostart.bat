@echo off
rem Keeps krillionDbot running. The Windows startup task (install_autostart.ps1) opens this
rem minimized at login. If the bot stops (crash, no internet yet), it restarts 30 seconds later.
title krillionDbot
cd /d "%~dp0"
:loop
.venv\Scripts\python.exe bot.py
echo.
echo krillionDbot stopped. Restarting in 30 seconds. Close this window to stop it for good.
timeout /t 30 /nobreak >nul
goto loop
