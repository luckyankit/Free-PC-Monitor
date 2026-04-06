# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A portable Windows system tray app that shows real-time hardware sensor data (temps, fan RPMs, power, storage stats) using LibreHardwareMonitor's .NET library via pythonnet. Runs with admin privileges for kernel driver access.

## Build & Run

```bash
pip install -r requirements.txt        # pythonnet, pystray, Pillow
python main.py                          # runs app (requests UAC elevation)

pip install pyinstaller
python build.py                         # builds dist/PCMonitor.exe

python install_autostart.py             # add to Windows startup registry
python install_autostart.py --remove    # remove from startup
```

Must run as administrator. If not admin, `main.py` re-launches itself elevated via `ShellExecuteW`.

## Architecture

**Startup flow:** `main.py` checks admin → elevates via UAC if needed → imports `sensor_engine` (which loads .NET runtime and LHM DLL at import time) → starts sensor polling thread → creates hidden tkinter root → launches pystray tray icon on its own thread → enters tkinter mainloop.

**Three threads at runtime:**
1. **Main thread** — tkinter mainloop, popup panel rendering, tray icon updates via `root.after()`
2. **Sensor thread** — `SensorEngine._poll_loop()`, calls LHM's .NET `Hardware.Update()` every 1s
3. **Tray thread** — pystray's `Icon.run()` win32 message loop

**Data flow:** `SensorEngine._update()` builds a fresh `dict[category → list[SensorReading]]` each cycle, swaps it under `_lock`. UI reads via `get_data()` which returns a shallow copy. Readings are immutable after creation — no cross-thread mutation.

**Sensor filtering:** Two-pass system in `_sensor_passes_filter()`:
- Normal categories use a **blacklist** (`SENSOR_HIDE`) — everything shows unless explicitly hidden
- Storage uses a **whitelist** (`STORAGE_SHOW`) — only listed sensors show
- Prefix `=` for exact name match (e.g., `"=temperature"` matches "Temperature" but not "Temperature 1")

**Key design decisions:**
- `.NET Framework 4.7.2` (net472 build) chosen over .NET Core because it's pre-installed on Windows 10/11. Set via `pythonnet.load("netfx")` before any `clr` import.
- `_resolve_assembly` handler registered on `AppDomain.AssemblyResolve` so .NET can find HidSharp.dll from `lib/` — critical for PyInstaller builds where extraction path differs.
- `_update_lock` prevents concurrent `Hardware.Update()` calls (not thread-safe in LHM). Separate from `_lock` which only guards data reads.
- `_cpu_package_temp` intentionally keeps last-known-good value when sensor returns None (for tray icon display).
- Popup position persisted to `state.json` via atomic write (temp file + `os.replace`).

## Sensor Data Source

All sensor data comes from `LibreHardwareMonitorLib.dll` (bundled in `lib/`). It uses a kernel driver (WinRing0) for CPU MSR reads and SuperIO chip access. Norton antivirus blocks this driver unless "Product Tamper Protection" is disabled.

Storage drives each become their own category (using `hw.Name` as category key instead of generic "Storage").
