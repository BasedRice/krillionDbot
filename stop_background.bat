@echo off
rem Stops krillionDbot when it's running in the background.
cd /d "%~dp0"
.venv\Scripts\python.exe background.py --stop
pause
