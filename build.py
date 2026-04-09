"""Build PC Monitor into a standalone .exe using PyInstaller."""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "PCMonitor",
    "--icon", "icon.ico",
    "--add-data", "lib;lib",
    "--uac-admin",
    "main.py",
]

print("Building PCMonitor.exe ...")
subprocess.run(cmd, check=True)
print("\nDone! Executable is at: dist/PCMonitor.exe")
print("Copy it wherever you like and run it.")
