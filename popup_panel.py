import tkinter as tk
import ctypes
import ctypes.wintypes
import config
from sensor_engine import SensorEngine, SensorType, LEFT_COLUMN, RIGHT_COLUMN


def temp_color(value, sensor_type):
    if sensor_type != SensorType.Temperature or value is None:
        return config.FG_COLOR
    if value < config.TEMP_GREEN_MAX:
        return config.COLOR_GREEN
    if value < config.TEMP_YELLOW_MAX:
        return config.COLOR_YELLOW
    return config.COLOR_RED


def get_work_area():
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


class PopupPanel:
    def __init__(self, engine: SensorEngine):
        self._engine = engine
        self._root = None
        self._window = None
        self._visible = False
        self._labels = {}
        self._drag_x = 0
        self._drag_y = 0
        self._refresh_id = None

    def set_root(self, root: tk.Tk):
        self._root = root
        # Pre-build the popup offscreen so first click is instant
        self._root.after(500, self._prebuild)

    def _prebuild(self):
        if self._window is not None:
            return
        # Wait until sensor engine has real data before building
        data = self._engine.get_data()
        has_data = any(r.value is not None for readings in data.values() for r in readings)
        if not has_data:
            self._root.after(1000, self._prebuild)
            return
        self._labels = {}
        self._window = tk.Toplevel(self._root)
        self._window.overrideredirect(True)
        self._window.configure(bg=config.BG_COLOR)
        # Render offscreen so all pixels are pre-painted, then hide
        self._window.geometry("+{0}+{1}".format(-9999, -9999))
        self._build_ui()
        self._window.update()
        self._window.withdraw()

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self):
        if self._window is None:
            # Prebuild hasn't completed yet — do a synchronous build
            self._labels = {}
            self._window = tk.Toplevel(self._root)
            self._window.withdraw()
            self._window.overrideredirect(True)
            self._window.configure(bg=config.BG_COLOR)
            self._build_ui()
            self._window.update_idletasks()

        self._cancel_refresh()
        self._refresh_values()
        self._position_window()
        self._window.update_idletasks()
        self._window.deiconify()
        self._window.lift()
        self._window.attributes("-topmost", True)
        self._visible = True
        self._schedule_refresh()

    def _cancel_refresh(self):
        if self._refresh_id is not None:
            try:
                self._window.after_cancel(self._refresh_id)
            except (tk.TclError, ValueError):
                pass
            self._refresh_id = None

    def _position_window(self):
        state = config.load_state()
        saved_x = state.get("popup_x")
        saved_y = state.get("popup_y")

        if saved_x is not None and saved_y is not None:
            work_area = get_work_area()
            if work_area:
                saved_x = max(work_area[0], min(saved_x, work_area[2] - 100))
                saved_y = max(work_area[1], min(saved_y, work_area[3] - 100))
            x, y = saved_x, saved_y
        else:
            work_area = get_work_area()
            win_w = self._window.winfo_reqwidth()
            win_h = self._window.winfo_reqheight()
            if work_area:
                x = work_area[2] - win_w - 10
                y = work_area[3] - win_h - 10
            else:
                screen_w = self._window.winfo_screenwidth()
                screen_h = self._window.winfo_screenheight()
                x = screen_w - win_w - 10
                y = screen_h - win_h - 50

        self._window.geometry(f"+{x}+{y}")

    def hide(self):
        self._cancel_refresh()
        if self._window is not None and self._visible:
            try:
                state = config.load_state()
                state["popup_x"] = self._window.winfo_x()
                state["popup_y"] = self._window.winfo_y()
                config.save_state(state)
            except Exception:
                pass
            self._window.withdraw()
        self._visible = False

    @property
    def is_visible(self):
        return self._visible

    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        x = self._window.winfo_x() + (event.x - self._drag_x)
        y = self._window.winfo_y() + (event.y - self._drag_y)
        self._window.geometry(f"+{x}+{y}")

    def _make_draggable(self, widget):
        widget.bind("<Button-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)

    def _build_ui(self):
        container = tk.Frame(self._window, bg=config.BG_COLOR, padx=10, pady=8)
        container.pack(fill="both", expand=True)

        # Title bar — draggable
        title_row = tk.Frame(container, bg=config.BG_COLOR)
        title_row.pack(fill="x", pady=(0, 6))

        title_label = tk.Label(
            title_row, text="PC Monitor", bg=config.BG_COLOR,
            fg=config.ACCENT_COLOR,
            font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
            cursor="fleur",
        )
        title_label.pack(side="left")
        self._make_draggable(title_label)
        self._make_draggable(title_row)

        close_btn = tk.Label(
            title_row, text="X", bg=config.BG_COLOR,
            fg="#888888", cursor="hand2",
            font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
        )
        close_btn.pack(side="right", padx=(0, 2))
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=config.COLOR_RED))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#888888"))

        tk.Frame(container, bg="#444444", height=1).pack(fill="x", pady=(0, 6))

        data = self._engine.get_data()
        storage_names = self._engine.get_storage_names()

        # Filter out sensors with no value
        filtered = {}
        for category, readings in data.items():
            valid = [r for r in readings if r.value is not None]
            if valid:
                filtered[category] = valid

        # Two-column layout with fixed assignment
        columns_frame = tk.Frame(container, bg=config.BG_COLOR)
        columns_frame.pack(fill="x")

        left_col = tk.Frame(columns_frame, bg=config.BG_COLOR)
        right_col = tk.Frame(columns_frame, bg=config.BG_COLOR)
        left_col.pack(side="left", fill="both", expand=True, anchor="n", padx=(0, 4))
        right_col.pack(side="left", fill="both", expand=True, anchor="n", padx=(4, 0))

        # Left: CPU, RAM, Fans / Voltages
        for cat in LEFT_COLUMN:
            if cat in filtered:
                self._build_section(left_col, cat, filtered[cat])

        # Right: GPU, Motherboard, then each storage drive
        for cat in RIGHT_COLUMN:
            if cat in filtered:
                self._build_section(right_col, cat, filtered[cat])

        for drive_name in storage_names:
            if drive_name in filtered:
                self._build_section(right_col, drive_name, filtered[drive_name])

        # Any remaining categories not assigned
        assigned = set(LEFT_COLUMN) | set(RIGHT_COLUMN) | set(storage_names)
        for cat in filtered:
            if cat not in assigned:
                self._build_section(left_col, cat, filtered[cat])

        if not filtered:
            tk.Label(
                container, text="No sensor data available.\nNorton may be blocking the driver.",
                bg=config.BG_COLOR, fg=config.COLOR_YELLOW,
                font=(config.FONT_FAMILY, config.FONT_SIZE_VALUE),
                justify="left",
            ).pack(anchor="w", pady=10)

    def _build_section(self, parent, category, readings):
        if not readings:
            return

        section = tk.Frame(parent, bg=config.BG_SECTION, padx=8, pady=6)
        section.pack(fill="x", pady=2)

        tk.Label(
            section, text=category, bg=config.BG_SECTION,
            fg=config.ACCENT_COLOR,
            font=(config.FONT_FAMILY, config.FONT_SIZE_VALUE, "bold"),
        ).pack(anchor="w")

        by_type = {}
        for r in readings:
            type_name = self._sensor_type_label(r.sensor_type)
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(r)

        type_order = ["Temperature", "Fan", "Clock", "Load", "Power", "Data"]
        displayed = set()
        for tn in type_order:
            if tn in by_type:
                self._build_type_group(section, by_type[tn])
                displayed.add(tn)
        for tn, rs in by_type.items():
            if tn not in displayed:
                self._build_type_group(section, rs)

    def _build_type_group(self, parent, readings):
        for r in readings:
            row = tk.Frame(parent, bg=config.BG_SECTION)
            row.pack(fill="x", padx=(8, 0), pady=1)

            tk.Label(
                row, text=r.name, bg=config.BG_SECTION,
                fg=config.FG_LABEL,
                font=(config.FONT_FAMILY, config.FONT_SIZE_LABEL),
                anchor="w", width=20,
            ).pack(side="left")

            color = temp_color(r.value, r.sensor_type)
            value_label = tk.Label(
                row, text=r.formatted(), bg=config.BG_SECTION,
                fg=color,
                font=(config.FONT_FAMILY, config.FONT_SIZE_VALUE),
                anchor="e", width=10,
            )
            value_label.pack(side="right")

            self._labels[r.sensor_id] = value_label

    def _sensor_type_label(self, sensor_type):
        mapping = {
            SensorType.Temperature: "Temperature",
            SensorType.Fan: "Fan",
            SensorType.Clock: "Clock",
            SensorType.Load: "Load",
            SensorType.Power: "Power",
            SensorType.Data: "Data",
            SensorType.SmallData: "Data",
        }
        return mapping.get(sensor_type, "Other")

    def _schedule_refresh(self):
        if not self._visible or self._window is None:
            return
        self._refresh_values()
        try:
            self._refresh_id = self._window.after(config.POLL_INTERVAL_MS, self._schedule_refresh)
        except tk.TclError:
            self._refresh_id = None

    def _refresh_values(self):
        data = self._engine.get_data()
        for readings in data.values():
            for r in readings:
                label = self._labels.get(r.sensor_id)
                if label is not None:
                    try:
                        color = temp_color(r.value, r.sensor_type)
                        label.configure(text=r.formatted(), fg=color)
                    except tk.TclError:
                        pass
