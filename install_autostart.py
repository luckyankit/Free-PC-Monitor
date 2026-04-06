"""Add or remove PCMonitor from Windows startup using Task Scheduler.

Uses Task Scheduler instead of registry Run key because the exe requires
admin privileges, and Windows suppresses UAC prompts for registry startup items.
Task Scheduler can run tasks with highest privileges without a UAC prompt.
"""
import sys
import os
import subprocess

EXE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "PCMonitor.exe")
TASK_NAME = "PCMonitor"


def add_startup():
    if not os.path.exists(EXE_PATH):
        print(f"ERROR: {EXE_PATH} not found. Build it first with: python build.py")
        return

    # Remove old registry entry if it exists
    _remove_registry_entry()

    # Create a scheduled task that runs at logon with highest privileges
    result = subprocess.run([
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", f'"{EXE_PATH}"',
        "/sc", "onlogon",
        "/rl", "highest",
        "/f",  # force overwrite if exists
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Added to startup via Task Scheduler: {EXE_PATH}")
        print("PCMonitor will now start automatically with admin privileges when you log in.")
    else:
        print(f"ERROR: {result.stderr.strip()}")
        print("Try running this script as administrator.")


def remove_startup():
    result = subprocess.run([
        "schtasks", "/delete",
        "/tn", TASK_NAME,
        "/f",
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("Removed from startup.")
    else:
        print("Not in Task Scheduler.")

    _remove_registry_entry()


def _remove_registry_entry():
    """Clean up old registry-based startup entry if present."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, TASK_NAME)
    except (FileNotFoundError, OSError):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        remove_startup()
    else:
        add_startup()
