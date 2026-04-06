import threading
import time
import sys
import os
import logging
import config

log = logging.getLogger("pc-monitor")

# Use .NET Framework (net472 build), must be set before importing clr
from pythonnet import load
load("netfx")

# Ensure .NET can find dependent DLLs (HidSharp.dll etc.)
sys.path.insert(0, config.LIB_DIR)
os.add_dll_directory(config.LIB_DIR)

import clr
import System
import System.IO
import System.Reflection

# Help .NET find assemblies in our lib dir (needed for PyInstaller builds)
def _resolve_assembly(sender, args):
    name = args.Name.split(",")[0] + ".dll"
    path = os.path.join(config.LIB_DIR, name)
    if os.path.exists(path):
        return System.Reflection.Assembly.LoadFrom(path)
    return None

System.AppDomain.CurrentDomain.AssemblyResolve += _resolve_assembly

clr.AddReference(config.LHM_DLL)

from LibreHardwareMonitor.Hardware import Computer, SensorType, HardwareType


HARDWARE_TYPE_NAMES = {
    HardwareType.Cpu: "CPU",
    HardwareType.GpuNvidia: "GPU",
    HardwareType.GpuAmd: "GPU",
    HardwareType.GpuIntel: "GPU",
    HardwareType.Memory: "RAM",
    HardwareType.Motherboard: "Motherboard",
    HardwareType.SuperIO: "Fans / Voltages",
    HardwareType.Storage: "Storage",
    HardwareType.Network: "Network",
    HardwareType.Battery: "Battery",
    HardwareType.Psu: "PSU",
    HardwareType.EmbeddedController: "Embedded Controller",
    HardwareType.Cooler: "Cooler",
}

# Use per-drive names for storage instead of generic "Storage"
STORAGE_TYPES = {HardwareType.Storage}

# Sensor types we care about for the popup
DISPLAY_SENSOR_TYPES = {
    SensorType.Temperature,
    SensorType.Fan,
    SensorType.Clock,
    SensorType.Load,
    SensorType.Power,
    SensorType.Data,
    SensorType.SmallData,
}

# Left column categories (top to bottom)
LEFT_COLUMN = ["CPU", "RAM", "Fans / Voltages"]
# Right column categories (top to bottom)
RIGHT_COLUMN = ["GPU", "Motherboard"]
# Storage drives go in right column, appended after Motherboard

# Categories to completely hide
HIDDEN_CATEGORIES = set()

# Blacklist: sensors to HIDE (substring match, case-insensitive)
# Everything else shows by default
SENSOR_HIDE = {
    "CPU": [
        "distance to tjmax",
        "core average",
        "cpu core #",          # per-core temps/clocks/loads (too many)
        "cpu memory",          # usually 0
        "cpu platform",        # usually 0
    ],
    "GPU": [
        "d3d ",
        "gpu bus",
        "gpu video engine",
        "gpu board power",
        "gpu power",           # load %, not watts — confusing
    ],
    "RAM": [
        "virtual memory",
    ],
    "Fans / Voltages": [
        "voltage",
        "control",
    ],
    "Embedded Controller": [
        "water",
        "t sensor",
    ],
}

# Storage: only show these (whitelist, since drives have lots of noise)
STORAGE_SHOW = ["=temperature", "used space", "data read", "data written"]


def _sensor_passes_filter(category, sensor_name, sensor_type, is_storage=False):
    """Blacklist filter for normal categories, whitelist for storage.
    Prefix a pattern with '=' for exact match (case-insensitive).
    """
    name_lower = sensor_name.lower()

    if is_storage:
        for pattern in STORAGE_SHOW:
            if pattern.startswith("="):
                if name_lower == pattern[1:]:
                    return True
            elif pattern in name_lower:
                return True
        return False

    hide_list = SENSOR_HIDE.get(category, [])
    for pattern in hide_list:
        if pattern in name_lower:
            return False
    return True


class SensorReading:
    __slots__ = ("name", "value", "sensor_type", "unit", "sensor_id")

    def __init__(self, name, value, sensor_type, sensor_id=""):
        self.name = name
        self.value = value
        self.sensor_type = sensor_type
        self.unit = self._get_unit(sensor_type)
        self.sensor_id = sensor_id

    @staticmethod
    def _get_unit(sensor_type):
        units = {
            SensorType.Temperature: "\u00b0C",
            SensorType.Fan: " RPM",
            SensorType.Clock: " MHz",
            SensorType.Load: "%",
            SensorType.Power: " W",
            SensorType.Voltage: " V",
            SensorType.Data: " GB",
            SensorType.SmallData: " MB",
        }
        return units.get(sensor_type, "")

    def formatted(self):
        if self.value is None:
            return "N/A"
        if self.sensor_type in (SensorType.Temperature, SensorType.Power):
            return f"{self.value:.1f}{self.unit}"
        if self.sensor_type == SensorType.Clock:
            return f"{self.value:.0f}{self.unit}"
        if self.sensor_type == SensorType.Load:
            return f"{self.value:.1f}{self.unit}"
        if self.sensor_type == SensorType.Fan:
            return f"{int(self.value)}{self.unit}"
        if self.sensor_type == SensorType.SmallData:
            return f"{self.value:.0f}{self.unit}"
        return f"{self.value:.1f}{self.unit}"


class SensorEngine:
    def __init__(self):
        self._computer = Computer()
        self._computer.IsCpuEnabled = True
        self._computer.IsGpuEnabled = True
        self._computer.IsMemoryEnabled = True
        self._computer.IsMotherboardEnabled = True
        self._computer.IsStorageEnabled = True
        self._computer.IsNetworkEnabled = False
        self._computer.IsControllerEnabled = True
        self._computer.Open()

        self._lock = threading.Lock()
        self._update_lock = threading.Lock()
        self._data = {}
        # Last-known-good CPU package temp for tray icon.
        # Intentionally keeps stale value if sensor temporarily returns None.
        self._cpu_package_temp = None
        self._running = False
        self._thread = None
        self._storage_names = []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        try:
            self._computer.Close()
        except Exception:
            pass

    def refresh(self):
        if self._update_lock.acquire(blocking=False):
            try:
                self._update()
            except Exception:
                log.error("Sensor refresh failed", exc_info=True)
            finally:
                self._update_lock.release()

    def get_data(self):
        with self._lock:
            return dict(self._data)

    def get_cpu_temp(self):
        with self._lock:
            return self._cpu_package_temp

    def get_storage_names(self):
        with self._lock:
            return list(self._storage_names)

    def _poll_loop(self):
        while self._running:
            if self._update_lock.acquire(blocking=False):
                try:
                    self._update()
                except Exception:
                    log.error("Sensor update failed", exc_info=True)
                finally:
                    self._update_lock.release()
            time.sleep(config.POLL_INTERVAL_MS / 1000.0)

    def _update(self):
        data = {}
        cpu_temp = None
        storage_names = []

        for hw in self._computer.Hardware:
            hw.Update()
            category = HARDWARE_TYPE_NAMES.get(hw.HardwareType, str(hw.HardwareType))
            if category in HIDDEN_CATEGORIES:
                continue

            is_storage = hw.HardwareType in STORAGE_TYPES
            if is_storage:
                category = str(hw.Name)
                storage_names.append(category)

            for sub in hw.SubHardware:
                sub.Update()
                sub_cat = HARDWARE_TYPE_NAMES.get(sub.HardwareType, category)
                if sub_cat not in HIDDEN_CATEGORIES:
                    self._collect_sensors(sub, sub_cat, data, is_storage)

            self._collect_sensors(hw, category, data, is_storage)

            if hw.HardwareType == HardwareType.Cpu:
                for sensor in hw.Sensors:
                    if (sensor.SensorType == SensorType.Temperature
                            and "package" in sensor.Name.lower()
                            and sensor.Value is not None):
                        cpu_temp = float(sensor.Value)

        with self._lock:
            self._data = data
            self._storage_names = storage_names
            if cpu_temp is not None:
                self._cpu_package_temp = cpu_temp

    def _collect_sensors(self, hw, category, data, is_storage=False):
        if category not in data:
            data[category] = []

        for sensor in hw.Sensors:
            if sensor.SensorType not in DISPLAY_SENSOR_TYPES:
                continue
            if not _sensor_passes_filter(category, sensor.Name, sensor.SensorType, is_storage):
                continue
            value = float(sensor.Value) if sensor.Value is not None else None
            reading = SensorReading(
                name=sensor.Name,
                value=value,
                sensor_type=sensor.SensorType,
                sensor_id=str(sensor.Identifier),
            )
            data[category].append(reading)
