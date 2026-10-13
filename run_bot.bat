@echo off
rem Starts krillionDbot. The first run sets up .venv, installs the packages and creates .env.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo First run: setting things up, this takes a minute...
    py -3 -m venv .venv 2>nul || python -m venv .venv || goto fail
)
.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt || goto fail
if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe bot.py
pause
exit /b

:fail
echo Setup failed. Install Python from https://www.python.org/downloads/ and run this again.
pause
