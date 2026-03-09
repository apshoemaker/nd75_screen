"""Background refresh loop for nd75-screen."""

from __future__ import annotations

import logging
import threading

from nd75_screen import ND75Error, WeatherFetchError
from nd75_screen.hid import ND75Device
from nd75_screen.renderer import render_to_chunks, render_frames_to_chunks
from nd75_screen.widgets.weather import fetch_metar, render_weather_frames, render_error_screen, detect_station

log = logging.getLogger(__name__)


def run_loop(
    station: str | None,
    interval: int,
    units: str,
    stop_event: threading.Event,
) -> None:
    """Run the weather refresh loop until *stop_event* is set.

    Args:
        station: ICAO airport code, or None to auto-detect.
        interval: Seconds between refreshes.
        units: "imperial" or "metric".
        stop_event: Set this to stop the loop.
    """
    if station is None:
        station = detect_station()
        log.info("Using auto-detected station: %s", station)
    else:
        log.info("Using station: %s", station)

    cached_chunks: list[bytes] | None = None

    with ND75Device() as device:
        while True:
            chunks = None

            # Fetch and render
            try:
                metar = fetch_metar(station)
                frames = render_weather_frames(metar, units)
                chunks = render_frames_to_chunks(frames)
                cached_chunks = chunks
            except WeatherFetchError as exc:
                log.warning("Weather fetch failed: %s", exc)
                if cached_chunks is not None:
                    chunks = cached_chunks
                else:
                    img = render_error_screen(str(exc))
                    chunks = render_to_chunks(img)

            # Upload
            if chunks is not None:
                try:
                    device.upload_image(chunks)
                except ND75Error as exc:
                    log.warning("Upload failed: %s", exc)

            # Wait for next interval or stop signal
            if stop_event.wait(timeout=interval):
                break
