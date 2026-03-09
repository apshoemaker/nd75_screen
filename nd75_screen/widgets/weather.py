"""METAR aviation weather widget."""

import textwrap

import requests
from PIL import Image, ImageDraw

from nd75_screen import SCREEN_WIDTH, SCREEN_HEIGHT, WeatherFetchError


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
