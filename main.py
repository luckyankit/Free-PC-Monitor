import sys
import os
import ctypes
import threading
import logging
from logging.handlers import RotatingFileHandler
import traceback
import tkinter as tk

import config

# Log with rotation (max 1MB, keep 2 backups)
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc-monitor.log")
_handler = RotatingFileHandler(LOG_FILE, maxBytes=1024 * 1024, backupCount=2)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.root.addHandler(_handler)
logging.root.setLevel(logging.INFO)
log = logging.getLogger("pc-monitor")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    script = os.path.abspath(__file__)
    work_dir = os.path.dirname(script)
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        f'"{script}"', work_dir, 1,
    )
    if result <= 32:
        show_error("Failed to get administrator privileges.\nThe application requires admin access to read hardware sensors.")
    sys.exit(0)


def show_error(message):
    ctypes.windll.user32.MessageBoxW(0, message, "PC Monitor - Error", 0x10)


def main():
    log.info("Starting PC Monitor, admin=%s, cwd=%s", is_admin(), os.getcwd())

    if not is_admin():
        print("Requesting admin privileges (required for hardware sensor access)...")
        run_as_admin()
        return

    # Change to script directory (important when launched via UAC)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    log.info("Working directory: %s", os.getcwd())

    # Initialize sensor engine (needs admin for hardware access)
    try:
        from sensor_engine import SensorEngine
        engine = SensorEngine()
        log.info("Sensor engine initialized")
    except Exception as e:
        log.error("Sensor init failed: %s", traceback.format_exc())
        show_error(
            f"Failed to initialize hardware sensors:\n\n{e}\n\n"
            "Make sure you are running as administrator."
        )
        return

    engine.start()

    # Set up tkinter root (hidden)
    root = tk.Tk()
    root.withdraw()

    from popup_panel import PopupPanel
    from tray_icon import TrayIcon

    popup = PopupPanel(engine)
    popup.set_root(root)

    def on_tray_click():
        root.after(0, popup.toggle)

    def on_refresh():
        engine.refresh()

    def on_quit():
        root.after(0, root.quit)

    tray = TrayIcon(engine, on_click=on_tray_click, on_quit=on_quit, on_refresh=on_refresh)
    icon = tray.create()

    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    def update_tray_icon():
        tray.update_icon()
        root.after(config.POLL_INTERVAL_MS, update_tray_icon)

    root.after(config.POLL_INTERVAL_MS, update_tray_icon)

    root.mainloop()

    # Cleanup after mainloop exits
    engine.stop()
    try:
        tray.stop()
    except Exception:
        pass


if __name__ == "__main__":
    main()
