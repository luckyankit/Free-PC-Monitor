import pystray
from PIL import Image, ImageDraw, ImageFont
import config
from sensor_engine import SensorEngine

# Cache fonts to avoid filesystem lookup every poll cycle
_font_cache = {}


def _get_font(size):
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for name in ("segoeuib.ttf", "arialbd.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def create_temp_icon(temp_value):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if temp_value is None:
        text = "--"
        color = config.FG_COLOR
    else:
        text = str(int(temp_value))
        if temp_value < config.TEMP_GREEN_MAX:
            color = config.COLOR_GREEN
        elif temp_value < config.TEMP_YELLOW_MAX:
            color = config.COLOR_YELLOW
        else:
            color = config.COLOR_RED

    font_size = 38 if len(text) >= 3 else 52
    font = _get_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=color, font=font)

    return img


class TrayIcon:
    def __init__(self, engine: SensorEngine, on_click, on_quit):
        self._engine = engine
        self._on_click = on_click
        self._on_quit = on_quit
        self._icon = None

    def create(self):
        temp = self._engine.get_cpu_temp()
        icon_image = create_temp_icon(temp)

        menu = pystray.Menu(
            pystray.MenuItem("Open Monitor", self._on_left_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit_click),
        )

        self._icon = pystray.Icon(
            name="pc-monitor",
            icon=icon_image,
            title=self._get_tooltip(temp),
            menu=menu,
        )
        return self._icon

    def stop(self):
        if self._icon is not None:
            self._icon.stop()

    def update_icon(self):
        if self._icon is None:
            return
        temp = self._engine.get_cpu_temp()
        self._icon.icon = create_temp_icon(temp)
        self._icon.title = self._get_tooltip(temp)

    def _get_tooltip(self, temp):
        if temp is None:
            return "PC Monitor - No data"
        return f"CPU: {temp:.0f}\u00b0C"

    def _on_left_click(self, icon, item):
        self._on_click()

    def _on_quit_click(self, icon, item):
        self._on_quit()
