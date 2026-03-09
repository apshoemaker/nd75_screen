"""nd75-weather — fetch METAR data and output animated GIF to stdout."""

from __future__ import annotations

import argparse
import sys

from nd75_screen.renderer import frames_to_gif
from nd75_screen.widgets.weather import detect_station, fetch_metar, render_weather_frames


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nd75-weather",
        description="Fetch aviation weather and output animated GIF to stdout.",
    )
    parser.add_argument(
        "-s", "--station", default=None, help="ICAO station code (auto-detected if omitted)"
    )
    parser.add_argument(
        "-u", "--units", default="imperial", choices=("imperial", "metric"),
        help="Temperature units (default: imperial)",
    )
    parser.add_argument(
        "--frames", type=int, default=8, help="Number of animation frames (default: 8)"
    )
    args = parser.parse_args(argv)

    station = args.station or detect_station()
    metar = fetch_metar(station)
    frames = render_weather_frames(metar, args.units, num_frames=args.frames)
    frames_to_gif(frames, sys.stdout.buffer)


if __name__ == "__main__":
    main()
