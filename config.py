import os
import json

# Paths
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(APP_DIR, "lib")
LHM_DLL = os.path.join(LIB_DIR, "LibreHardwareMonitorLib.dll")
STATE_FILE = os.path.join(APP_DIR, "state.json")


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    """Atomic write — write to temp file then rename to prevent corruption."""
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass

# Polling
POLL_INTERVAL_MS = 1000

# Temperature thresholds (Celsius)
TEMP_GREEN_MAX = 60
TEMP_YELLOW_MAX = 80

# Colors (dark theme)
BG_COLOR = "#1e1e1e"
BG_SECTION = "#2a2a2a"
FG_COLOR = "#e0e0e0"
FG_LABEL = "#888888"
COLOR_GREEN = "#4caf50"
COLOR_YELLOW = "#ff9800"
COLOR_RED = "#f44336"
ACCENT_COLOR = "#60a5fa"

# Font
FONT_FAMILY = "Segoe UI"
FONT_SIZE_TITLE = 11
FONT_SIZE_VALUE = 10
FONT_SIZE_LABEL = 9
