"""nd75-push — read PNG/GIF from stdin or file and push to keyboard LCD."""

from __future__ import annotations

import argparse
import io
import sys

from nd75_screen.hid import ND75Device
from nd75_screen.renderer import read_frames, render_frames_to_chunks, render_to_chunks


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nd75-push",
        description="Push a PNG or animated GIF to the ND75 keyboard LCD.",
    )
    parser.add_argument(
        "file", nargs="?", default=None, help="Image file path (reads stdin if omitted)"
    )
    parser.add_argument(
        "--sync-time", action="store_true", help="Sync keyboard clock before pushing image"
    )
    args = parser.parse_args(argv)

    if args.file:
        fp: io.BufferedIOBase = open(args.file, "rb")  # noqa: SIM115
    elif not sys.stdin.isatty():
        fp = sys.stdin.buffer
    else:
        parser.print_usage(sys.stderr)
        print("error: no input — pipe an image or pass a file path", file=sys.stderr)
        sys.exit(1)

    data = fp.read()
    if args.file:
        fp.close()

    frames = read_frames(io.BytesIO(data))

    if len(frames) == 1:
        chunks = render_to_chunks(frames[0])
    else:
        chunks = render_frames_to_chunks(frames)

    with ND75Device() as device:
        if args.sync_time:
            device.sync_time()
        device.upload_image(chunks)


if __name__ == "__main__":
    main()
