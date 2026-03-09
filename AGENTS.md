# nd75-screen

Push custom screens to Chilkey ND75 keyboard LCD (135x240, RGB565).

> **For coding agents:** Treat this file as a table of contents. Dive into `docs/` for details as needed — don't load everything up front.

```bash
uv run pytest tests/ -v                     # Run all tests (54)
uv run python -m nd75_screen --help          # CLI help
uv run python -m nd75_screen --once -s KIAH  # Push weather once
uv run python -m nd75_screen -s KIAH -i 300  # Start daemon
```

## Project Structure

```
nd75_screen/
  __init__.py      # Constants, exception classes
  __main__.py      # CLI entry point (argparse)
  hid.py           # USB HID communication
  renderer.py      # Image -> RGB565 -> wire-ready chunks
  daemon.py        # Background refresh loop
  widgets/
    weather.py     # METAR weather widget
tests/
  conftest.py      # Shared fixtures
  test_*.py        # One test file per module
```

## Conventions

- `uv` for everything — `uv run`, `uv add`
- TDD: tests first, all HID/HTTP mocked, no hardware in tests
- Constants and exceptions live in `nd75_screen/__init__.py`

## Key Docs

- **[docs/protocol.md](docs/protocol.md)** — USB HID wire protocol, command format, upload flow
- **[docs/rendering.md](docs/rendering.md)** — RGB565 format, chunk layout, multi-frame animation
- **[docs/weather-widget.md](docs/weather-widget.md)** — METAR API, icon mapping, screen layout
- **[docs/lessons-learned.md](docs/lessons-learned.md)** — Pitfalls and hardware-verified findings
