"""Runs krillionDbot in the background, with no window.

    pythonw background.py          the supervisor itself (what the Windows login task runs)
    python background.py --start   start the supervisor in the background (start_background.bat)
    python background.py --stop    stop it (stop_background.bat)
    python background.py --log     open the log (view_log.bat)

The supervisor runs bot.py, writes its output to bot.log next to the database,
and restarts it 30 seconds after it stops (a crash, or no internet yet). It quits
when asked to stop, or when bot.py says another copy is already running.
"""
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import bot

HERE = Path(__file__).resolve().parent
LOG_PATH = bot.DB_PATH.parent / "bot.log"
STOP_PATH = bot.DB_PATH.parent / "STOP"
RESTART_DELAY = 30
MAX_LOG_BYTES = 5_000_000
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def interpreter(windowless: bool) -> str:
    """This venv's python.exe, or pythonw.exe (no window at all) on Windows."""
    exe = Path(sys.executable)
    if os.name != "nt":
        return str(exe)
    return str(exe.with_name("pythonw.exe" if windowless else "python.exe"))


def note(text: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [background] {text}\n")


def take_stop_request() -> bool:
    try:
        STOP_PATH.unlink()
        return True
    except FileNotFoundError:
        return False


def bot_is_running() -> bool:
    lock = bot.single_instance_lock(bot.LOCK_PATH)
    if lock is None:
        return True
    lock.close()
    return False


def supervise() -> None:
    take_stop_request()  # a leftover stop request shouldn't stop a fresh start
    while True:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_LOG_BYTES:
            LOG_PATH.replace(LOG_PATH.with_name("bot.log.1"))
        with open(LOG_PATH, "ab") as log:
            proc = subprocess.Popen(
                [interpreter(windowless=False), str(HERE / "bot.py")], cwd=HERE, stdout=log,
                stderr=subprocess.STDOUT, env={**os.environ, "PYTHONUTF8": "1"}, creationflags=NO_WINDOW,
            )
            while proc.poll() is None:
                if take_stop_request():
                    proc.terminate()
                    proc.wait()
                    note("Stopped.")
                    return
                time.sleep(2)
        if proc.returncode == bot.ALREADY_RUNNING:
            note("Another copy of the bot is already running, so this one is quitting.")
            return
        note(f"The bot stopped (exit code {proc.returncode}). Restarting in {RESTART_DELAY} seconds.")
        deadline = time.monotonic() + RESTART_DELAY
        while time.monotonic() < deadline:
            if take_stop_request():
                note("Stopped.")
                return
            time.sleep(2)


def start() -> int:
    if bot_is_running():
        print("krillionDbot is already running.")
        return 0
    offset = LOG_PATH.stat().st_size if LOG_PATH.exists() else 0
    subprocess.Popen([interpreter(windowless=True), str(HERE / "background.py")], cwd=HERE,
                     creationflags=DETACHED, start_new_session=os.name != "nt")
    print("Starting krillionDbot in the background...")
    # Watch the log for the bot logging in, or the supervisor reporting a failed start.
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        time.sleep(1)
        if not LOG_PATH.exists():
            continue
        if LOG_PATH.stat().st_size < offset:  # the log was just rotated
            offset = 0
        with open(LOG_PATH, encoding="utf-8", errors="replace") as log:
            log.seek(offset)
            new = log.read()
        if "Logged in as" in new:
            print("krillionDbot is running in the background. It shows as online in Discord.")
            return 0
        if "[background]" in new:
            print("krillionDbot didn't start. From its log:\n")
            print("\n".join(new.strip().splitlines()[-6:]))
            return 1
    print("It's still starting. If it isn't online in Discord in a minute, open view_log.bat.")
    return 0


def stop() -> int:
    STOP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STOP_PATH.touch()
    deadline = time.monotonic() + 10
    while STOP_PATH.exists() and time.monotonic() < deadline:
        time.sleep(0.5)
    if take_stop_request():  # nobody picked it up: no background bot
        if bot_is_running():
            print("krillionDbot is running in a window, not in the background. Close that window to stop it.")
        else:
            print("krillionDbot isn't running.")
        return 0
    deadline = time.monotonic() + 15
    while bot_is_running() and time.monotonic() < deadline:
        time.sleep(0.5)
    print("Stopped krillionDbot. It starts again at your next Windows login if auto-start is on,\n"
          "or right away with start_background.bat.")
    return 0


def open_log() -> int:
    if not LOG_PATH.exists():
        print("No log yet. It's created the first time the bot runs in the background.")
        return 1
    if os.name == "nt":
        os.startfile(LOG_PATH)
    else:
        print(LOG_PATH)
    return 0


if __name__ == "__main__":
    bot.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "--start":
        sys.exit(start())
    if command == "--stop":
        sys.exit(stop())
    if command == "--log":
        sys.exit(open_log())
    try:
        supervise()
    except Exception:
        note("Supervisor crashed:\n" + traceback.format_exc())
        raise
