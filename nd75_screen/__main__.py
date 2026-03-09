"""CLI entry point for nd75-screen."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from PIL import Image

from nd75_screen.daemon import run_loop
from nd75_screen.hid import ND75Device
from nd75_screen.renderer import render_to_chunks


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nd75-screen",
        description="Push custom screens to Chilkey ND75 keyboard LCD",
    )
    parser.add_argument(
        "-s", "--station", default=None, help="ICAO station code (auto-detected if omitted)"
    )
    parser.add_argument(
        "-i", "--interval", type=int, default=300, help="Refresh interval in seconds (default: 300)"
    )
    parser.add_argument(
        "-u", "--units", choices=["imperial", "metric"], default="imperial",
        help="Temperature units (default: imperial)",
    )
    parser.add_argument(
        "--once", action="store_true", help="Push one screen and exit"
    )
    parser.add_argument(
        "--image", type=str, help="Push a raw image file (bypass widget)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.image:
        img = Image.open(args.image)
        chunks = render_to_chunks(img)
        with ND75Device() as device:
            device.upload_image(chunks)
        return

    stop_event = threading.Event()

    def handle_signal(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.once:
        stop_event.set()

    run_loop(args.station, args.interval, args.units, stop_event)


if __name__ == "__main__":
    main()
