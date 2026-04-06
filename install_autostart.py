"""Add or remove PCMonitor from Windows startup."""
import sys
import os
import winreg

EXE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "PCMonitor.exe")
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "PCMonitor"


def add_startup():
    if not os.path.exists(EXE_PATH):
        print(f"ERROR: {EXE_PATH} not found. Build it first with: python build.py")
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, EXE_PATH)
    print(f"Added to startup: {EXE_PATH}")
    print("PCMonitor will now start automatically when you log in.")


def remove_startup():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, REG_NAME)
        print("Removed from startup.")
    except FileNotFoundError:
        print("Not in startup registry.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        remove_startup()
    else:
        add_startup()
