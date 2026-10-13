@echo off
rem Starts krillionDbot. The first run creates .venv and installs the packages.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv || goto fail
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto fail
)
.venv\Scripts\python.exe bot.py
pause
exit /b

:fail
echo Setup failed. Is Python installed? Get it from https://www.python.org/downloads/
pause
