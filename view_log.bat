@echo off
rem Opens the background bot's log in Notepad.
cd /d "%~dp0"
.venv\Scripts\python.exe background.py --log || pause
