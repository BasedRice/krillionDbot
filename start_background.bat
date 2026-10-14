@echo off
rem Starts krillionDbot in the background (no window). Stop it with stop_background.bat.
cd /d "%~dp0"
.venv\Scripts\python.exe background.py --start
pause
