"""METAR aviation weather widget."""

import math
import textwrap

import requests
from PIL import Image, ImageDraw

from nd75_screen import SCREEN_WIDTH, SCREEN_HEIGHT, WeatherFetchError

NUM_ANIM_FRAMES = 8


def fetch_metar(station: str) -> dict:
    """Fetch current METAR data for an airport station.

    Args:
        station: ICAO airport code (e.g. "KIAH").

    Returns:
        First METAR dict from the API response.

    Raises:
        WeatherFetchError: On HTTP error, network error, or empty response.
    """
    url = f"https://aviationweather.gov/api/data/metar?ids={station}&format=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise WeatherFetchError(f"Failed to fetch METAR for {station}: {exc}") from exc

    if not data:
        raise WeatherFetchError(f"No METAR data returned for {station}")

    return data[0]


def parse_weather_icon(metar: dict) -> str:
    """Determine weather icon name from METAR data.

    Checks wxString for precipitation first, then falls back to cloud cover.

    Returns:
        Icon name string: sunny, partly_cloudy, mostly_cloudy, overcast,
        rain, snow, thunderstorm, or fog.
    """
    wx = metar.get("wxString") or ""

    # Precipitation takes priority
    if "TS" in wx:
        return "thunderstorm"
    if "SN" in wx:
        return "snow"
    if "RA" in wx:
        return "rain"
    if "FG" in wx:
        return "fog"

    # Cloud cover mapping
    cover_map = {
        "SKC": "sunny",
        "CLR": "sunny",
        "FEW": "partly_cloudy",
        "SCT": "partly_cloudy",
        "BKN": "mostly_cloudy",
        "OVC": "overcast",
    }

    clouds = metar.get("clouds") or []
    if not clouds:
        return "sunny"

    # Use the highest (last) cloud layer's cover
    highest_cover = clouds[-1].get("cover", "")
    return cover_map.get(highest_cover, "sunny")


def _draw_weather_icon(draw: ImageDraw.ImageDraw, icon: str, cx: int, cy: int):
    """Draw a simple weather icon centered at (cx, cy)."""
    r = 12  # base radius

    if icon == "sunny":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="yellow")
    elif icon == "partly_cloudy":
        draw.ellipse([cx - r, cy - r + 2, cx + r - 4, cy + r - 2], fill="yellow")
        draw.ellipse([cx - 8, cy - 4, cx + 14, cy + 10], fill="lightgray")
    elif icon == "mostly_cloudy":
        draw.ellipse([cx - 10, cy - 6, cx + 10, cy + 6], fill="gray")
        draw.ellipse([cx - 6, cy - 2, cx + 14, cy + 10], fill="lightgray")
    elif icon == "overcast":
        draw.ellipse([cx - 14, cy - 6, cx + 14, cy + 8], fill="gray")
    elif icon == "rain":
        draw.ellipse([cx - 12, cy - 8, cx + 12, cy + 4], fill="gray")
        for dx in (-6, 0, 6):
            draw.line([cx + dx, cy + 6, cx + dx - 2, cy + 12], fill="cyan", width=1)
    elif icon == "snow":
        draw.ellipse([cx - 12, cy - 8, cx + 12, cy + 4], fill="gray")
        for dx in (-6, 0, 6):
            draw.text((cx + dx - 2, cy + 5), "*", fill="white")
    elif icon == "thunderstorm":
        draw.ellipse([cx - 14, cy - 8, cx + 14, cy + 4], fill="darkgray")
        draw.polygon(
            [(cx - 2, cy + 4), (cx + 4, cy + 4), (cx, cy + 14)],
            fill="yellow",
        )
    elif icon == "fog":
        for dy in range(-4, 8, 4):
            draw.line([cx - 14, cy + dy, cx + 14, cy + dy], fill="lightgray", width=2)


def _draw_animated_icon(draw: ImageDraw.ImageDraw, icon: str, cx: int, cy: int, frame: int, total: int):
    """Draw an animated weather icon. *frame* is 0..total-1."""
    t = frame / total  # 0.0 .. ~1.0
    angle = t * 2 * math.pi

    if icon == "sunny":
        # Sun body
        draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill="yellow")
        # Rotating rays
        for i in range(8):
            ray_angle = angle + i * math.pi / 4
            x1 = cx + int(13 * math.cos(ray_angle))
            y1 = cy + int(13 * math.sin(ray_angle))
            x2 = cx + int(18 * math.cos(ray_angle))
            y2 = cy + int(18 * math.sin(ray_angle))
            draw.line([x1, y1, x2, y2], fill="yellow", width=2)

    elif icon == "partly_cloudy":
        # Sun peeks out, cloud drifts left/right
        offset = int(4 * math.sin(angle))
        draw.ellipse([cx - 10 + offset, cy - 8, cx + 6 + offset, cy + 6], fill="yellow")
        # Rotating sun rays (fewer, behind cloud)
        for i in range(5):
            ray_angle = angle + i * math.pi / 2.5
            sx = cx + offset - 2
            sy = cy - 1
            x1 = sx + int(10 * math.cos(ray_angle))
            y1 = sy + int(10 * math.sin(ray_angle))
            x2 = sx + int(14 * math.cos(ray_angle))
            y2 = sy + int(14 * math.sin(ray_angle))
            draw.line([x1, y1, x2, y2], fill="yellow", width=1)
        # Cloud on top
        draw.ellipse([cx - 8 - offset, cy - 2, cx + 14 - offset, cy + 12], fill="lightgray")

    elif icon == "mostly_cloudy":
        # Two cloud layers drifting opposite directions
        o1 = int(3 * math.sin(angle))
        o2 = int(3 * math.sin(angle + math.pi))
        draw.ellipse([cx - 12 + o1, cy - 6, cx + 8 + o1, cy + 6], fill="gray")
        draw.ellipse([cx - 6 + o2, cy - 2, cx + 14 + o2, cy + 10], fill="lightgray")

    elif icon == "overcast":
        # Two clouds drifting in opposite directions
        o1 = int(5 * math.sin(angle))
        o2 = int(5 * math.sin(angle + math.pi))
        draw.ellipse([cx - 14 + o1, cy - 8, cx + 6 + o1, cy + 4], fill=(130, 130, 130))
        draw.ellipse([cx - 6 + o2, cy - 3, cx + 14 + o2, cy + 10], fill=(170, 170, 170))

    elif icon == "rain":
        # Cloud
        draw.ellipse([cx - 12, cy - 8, cx + 12, cy + 2], fill="gray")
        # Falling raindrops — each drop cycles downward
        for i, dx in enumerate((-8, -3, 2, 7)):
            drop_y = cy + 4 + int((frame + i * 2) % total * 12 / total)
            draw.line([cx + dx, drop_y, cx + dx - 1, drop_y + 4], fill="cyan", width=1)

    elif icon == "snow":
        # Cloud
        draw.ellipse([cx - 12, cy - 8, cx + 12, cy + 2], fill="gray")
        # Drifting snowflakes — each flake drifts down and sways
        for i, dx_base in enumerate((-8, -2, 4, 9)):
            drift_x = int(3 * math.sin(angle + i * math.pi / 2))
            drop_y = cy + 4 + int((frame + i * 2) % total * 12 / total)
            draw.text((cx + dx_base + drift_x - 2, drop_y), "*", fill="white")

    elif icon == "thunderstorm":
        # Dark cloud
        draw.ellipse([cx - 14, cy - 8, cx + 14, cy + 2], fill="darkgray")
        # Lightning bolt flashes on alternating frames
        if frame % 3 == 0:
            draw.polygon(
                [(cx - 2, cy + 2), (cx + 3, cy + 2), (cx + 1, cy + 7),
                 (cx + 5, cy + 7), (cx - 3, cy + 16), (cx, cy + 10),
                 (cx - 4, cy + 10)],
                fill="yellow",
            )
        # Rain on non-flash frames
        for i, dx in enumerate((-8, 0, 8)):
            drop_y = cy + 4 + int((frame + i * 2) % total * 10 / total)
            draw.line([cx + dx, drop_y, cx + dx - 1, drop_y + 3], fill="cyan", width=1)

    elif icon == "fog":
        # Horizontal lines that fade/shift
        for j, dy in enumerate(range(-6, 10, 4)):
            offset = int(6 * math.sin(angle + j * 0.8))
            gray_val = 140 + int(40 * math.sin(angle + j))
            color = (gray_val, gray_val, gray_val)
            draw.line([cx - 16 + offset, cy + dy, cx + 16 + offset, cy + dy],
                      fill=color, width=2)


def _render_weather_base(metar: dict, units: str, draw: ImageDraw.ImageDraw) -> int:
    """Draw all static weather elements. Returns the y position of the icon center."""
    y = 4

    # Station code
    station = metar.get("icaoId", "????")
    bbox = draw.textbbox((0, 0), station)
    tw = bbox[2] - bbox[0]
    draw.text(((SCREEN_WIDTH - tw) // 2, y), station, fill="white")
    y += 14

    # Station name
    name = metar.get("name", "")
    if name:
        if len(name) > 20:
            name = name[:18] + ".."
        bbox = draw.textbbox((0, 0), name)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), name, fill="gray")
    y += 14

    icon_cy = y + 12
    y += 30

    # Temperature
    temp_c = metar.get("temp")
    if temp_c is not None:
        if units == "imperial":
            temp_val = round(temp_c * 9 / 5 + 32)
            temp_str = f"{temp_val}\u00b0F"
        else:
            temp_str = f"{temp_c}\u00b0C"
        bbox = draw.textbbox((0, 0), temp_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), temp_str, fill="white")
    y += 16

    # Wind
    wdir = metar.get("wdir")
    wspd = metar.get("wspd")
    if wdir is not None and wspd is not None:
        wind_str = f"{wdir}\u00b0 @ {wspd}kt"
        wgst = metar.get("wgst")
        if wgst:
            wind_str += f" G{wgst}"
        bbox = draw.textbbox((0, 0), wind_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), wind_str, fill="white")
    y += 14

    # Visibility
    visib = metar.get("visib")
    if visib is not None:
        vis_str = f"{visib} SM"
        bbox = draw.textbbox((0, 0), vis_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), vis_str, fill="white")
    y += 14

    # Flight category
    fltcat = metar.get("fltcat", "")
    cat_colors = {
        "VFR": "green",
        "MVFR": "blue",
        "IFR": "red",
        "LIFR": "magenta",
    }
    if fltcat:
        color = cat_colors.get(fltcat, "white")
        bbox = draw.textbbox((0, 0), fltcat)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), fltcat, fill=color)
    y += 16

    # Raw METAR text
    raw = metar.get("rawOb", "")
    if raw:
        wrapped = textwrap.fill(raw, width=22)
        draw.text((2, y), wrapped, fill="gray")

    return icon_cy


def render_weather_frames(metar: dict, units: str = "imperial", num_frames: int = NUM_ANIM_FRAMES) -> list[Image.Image]:
    """Render animated weather frames for the ND75 screen.

    Returns a list of *num_frames* 135x240 RGB images with animated icons.
    """
    icon = parse_weather_icon(metar)

    # Render the base (static text) once, then stamp animated icons per frame
    base = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), "black")
    base_draw = ImageDraw.Draw(base)
    icon_cy = _render_weather_base(metar, units, base_draw)
    icon_cx = SCREEN_WIDTH // 2

    frames = []
    for f in range(num_frames):
        img = base.copy()
        draw = ImageDraw.Draw(img)
        # Clear the icon region and redraw animated version
        draw.rectangle([icon_cx - 20, icon_cy - 14, icon_cx + 20, icon_cy + 18], fill="black")
        _draw_animated_icon(draw, icon, icon_cx, icon_cy, f, num_frames)
        frames.append(img)

    return frames


def render_weather(metar: dict, units: str = "imperial") -> Image.Image:
    """Render a weather display image for the ND75 screen.

    Args:
        metar: Parsed METAR dict from fetch_metar.
        units: "imperial" for Fahrenheit or "metric" for Celsius.

    Returns:
        135x240 RGB Pillow Image.
    """
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), "black")
    draw = ImageDraw.Draw(img)

    y = 4

    # Station code
    station = metar.get("icaoId", "????")
    bbox = draw.textbbox((0, 0), station)
    tw = bbox[2] - bbox[0]
    draw.text(((SCREEN_WIDTH - tw) // 2, y), station, fill="white")
    y += 14

    # Station name
    name = metar.get("name", "")
    if name:
        # Truncate long names
        if len(name) > 20:
            name = name[:18] + ".."
        bbox = draw.textbbox((0, 0), name)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), name, fill="gray")
    y += 14

    # Weather icon
    icon = parse_weather_icon(metar)
    _draw_weather_icon(draw, icon, SCREEN_WIDTH // 2, y + 12)
    y += 30

    # Temperature
    temp_c = metar.get("temp")
    if temp_c is not None:
        if units == "imperial":
            temp_val = round(temp_c * 9 / 5 + 32)
            temp_str = f"{temp_val}\u00b0F"
        else:
            temp_str = f"{temp_c}\u00b0C"
        bbox = draw.textbbox((0, 0), temp_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), temp_str, fill="white")
    y += 16

    # Wind
    wdir = metar.get("wdir")
    wspd = metar.get("wspd")
    if wdir is not None and wspd is not None:
        wind_str = f"{wdir}\u00b0 @ {wspd}kt"
        wgst = metar.get("wgst")
        if wgst:
            wind_str += f" G{wgst}"
        bbox = draw.textbbox((0, 0), wind_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), wind_str, fill="white")
    y += 14

    # Visibility
    visib = metar.get("visib")
    if visib is not None:
        vis_str = f"{visib} SM"
        bbox = draw.textbbox((0, 0), vis_str)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), vis_str, fill="white")
    y += 14

    # Flight category
    fltcat = metar.get("fltcat", "")
    cat_colors = {
        "VFR": "green",
        "MVFR": "blue",
        "IFR": "red",
        "LIFR": "magenta",
    }
    if fltcat:
        color = cat_colors.get(fltcat, "white")
        bbox = draw.textbbox((0, 0), fltcat)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_WIDTH - tw) // 2, y), fltcat, fill=color)
    y += 16

    # Raw METAR text
    raw = metar.get("rawOb", "")
    if raw:
        wrapped = textwrap.fill(raw, width=22)
        draw.text((2, y), wrapped, fill="gray")

    return img


def render_error_screen(message: str) -> Image.Image:
    """Render an error screen for the ND75 display.

    Args:
        message: Error message to display.

    Returns:
        135x240 RGB Pillow Image with red error text.
    """
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), "black")
    draw = ImageDraw.Draw(img)

    wrapped = textwrap.fill(message, width=20)
    bbox = draw.textbbox((0, 0), wrapped)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (SCREEN_WIDTH - tw) // 2
    y = (SCREEN_HEIGHT - th) // 2
    draw.text((x, y), wrapped, fill="red")

    return img
