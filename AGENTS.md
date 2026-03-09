# nd75-screen

Push custom screens to Chilkey ND75 keyboard LCD (135x240, RGB565). Open-source replacement for the Windows-only Chilkey configurator.

## Quick Reference

```bash
uv run pytest tests/ -v                    # Run all tests (54)
uv run python -m nd75_screen --help        # CLI help
uv run python -m nd75_screen --image a.png # Push image to LCD
uv run python -m nd75_screen --once -s KIAH # Push animated weather once
uv run python -m nd75_screen -s KIAH -i 300 # Start daemon
```

Note: use `python -m nd75_screen` to run (the `nd75-screen` script entry point requires `uv pip install -e .`).

## Project Structure

```
nd75_screen/
  __init__.py      # Constants (dimensions, VID/PID, chunk sizes), exception classes
  __main__.py      # CLI (argparse): --station, --interval, --units, --once, --image
  hid.py           # ND75Device class — USB HID protocol orchestration
  renderer.py      # PIL Image -> RGB565-LE bytes -> wire-ready chunks
  daemon.py        # Background loop: fetch -> render animated frames -> upload
  widgets/
    weather.py     # METAR fetch, icon parsing, animated PIL rendering, error screen
tests/
  conftest.py      # Fixtures: sample_metar, sample_metar_bad_weather, MockHIDDevice
  test_renderer.py # RGB565 conversion + chunking, multi-frame (17 tests)
  test_hid.py      # HID protocol with mocked hidapi (12 tests)
  test_weather.py  # METAR fetch + render + animation with mocked HTTP (20 tests)
  test_daemon.py   # Daemon lifecycle with all deps mocked (5 tests)
docs/
  protocol.md      # Full USB HID wire protocol spec
  rendering.md     # RGB565 format, chunk layout, byte-level details
  weather-widget.md # METAR API fields, icon mapping, screen layout
```

## Conventions

- **Package manager:** `uv` — all commands via `uv run`
- **TDD:** Write tests first, run (expect failures), implement until green
- **No hardware in tests:** All HID calls mocked; HTTP calls mocked
- **Imports:** `from nd75_screen import ...` for shared constants/exceptions
- **No external fonts:** Pillow's built-in default only
- **macOS:** May need Input Monitoring permission for HID access

## Key Constants (`__init__.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `SCREEN_WIDTH` / `HEIGHT` | 135 / 240 | LCD pixel dimensions |
| `VID` / `PID` | 0x36B5 / 0x2BA7 | USB device identifiers |
| `CMD_USAGE_PAGE` | 0xFF13 | HID interface for commands |
| `DATA_USAGE_PAGE` | 0xFF68 | HID interface for pixel data |
| `CHUNK_SIZE` | 4096 | Bytes per wire chunk |
| `NUM_CHUNKS` | 16 | Chunks per single frame |
| `HEADER_SIZE` | 256 | Header in chunk 0 |
| `ALLOWED_COMMANDS` | {0x18, 0x72, 0x02} | Whitelisted command bytes |

## Module Boundaries

| Module | Owns | Depends On |
|--------|------|------------|
| `renderer.py` | Image -> RGB565 -> chunks (single + multi-frame) | Pillow, `__init__` constants |
| `hid.py` | USB protocol (ND75Device) | `hidapi`, `__init__` constants/exceptions |
| `widgets/weather.py` | METAR fetch + animated PIL rendering | `requests`, Pillow, `__init__` |
| `daemon.py` | Glue loop with caching | All three above |
| `__main__.py` | CLI, signal handling | `daemon`, `hid`, `renderer` |

## Animation Support

The LCD firmware natively supports multi-frame images (GIF-like). The header byte[0] specifies frame count; pixel data for all frames is packed sequentially after the header. Chunk count scales dynamically (e.g., 8 frames = ~127 chunks).

Each weather icon has 8 animation frames (`NUM_ANIM_FRAMES`):
- **sunny** — rotating rays around sun
- **partly_cloudy** — cloud drifting over sun with rays
- **mostly_cloudy** — two cloud layers drifting opposite directions
- **overcast** — two clouds at different shades drifting in opposition
- **rain** — cloud with falling raindrops cycling downward
- **snow** — cloud with swaying, drifting snowflakes
- **thunderstorm** — dark cloud, lightning flash on every 3rd frame, rain
- **fog** — horizontal lines shifting and fading

Key functions: `render_weather_frames()` returns a list of PIL Images, `render_frames_to_chunks()` packs them into wire format.

## Lessons Learned

### hidapi Python API
The `hidapi` package uses `hid.device()` (lowercase) + `.open_path(path)`, not `hid.Device(path=...)`. Methods: `write`, `read`, `send_feature_report`, `get_feature_report`, `close`. Mock at `hid.enumerate` and `hid.device` level in tests.

### Daemon do-while pattern
`while not stop_event.is_set()` skips the body if event is pre-set (e.g. `--once`). Use `while True` + `if stop_event.wait(timeout): break` at end to guarantee at least one iteration.

### RGB565 byte order — confirmed on hardware
Little-endian: red (255,0,0) = 0xF800 -> bytes `[0x00, 0xF8]`. Verified with solid color uploads — no byte swapping needed.

### macOS quirks
- `timeout` command not available by default (use `sleep` + `kill` instead)
- HID device paths look like `b'DevSrvsID:4295283928'` (not /dev paths)
- Device paths change on USB reconnect — always re-enumerate

### Parallel agent coordination
Scaffolding phase commits `__init__.py` with all constants/exceptions before agents fork into worktrees. Each agent touches only its module + test file, never shared files.

## Deep Dives

- **[docs/protocol.md](docs/protocol.md)** — USB HID wire protocol: device identification, feature report format, upload flow, safety
- **[docs/rendering.md](docs/rendering.md)** — RGB565 bit layout, reference color values, chunk structure, image preprocessing
- **[docs/weather-widget.md](docs/weather-widget.md)** — METAR API endpoint, response fields, icon mapping rules, screen layout, error display

## Adding a New Widget

1. Create `nd75_screen/widgets/your_widget.py` with `render_*_frames(data) -> list[Image]`
2. Create `tests/test_your_widget.py` with mocked external calls
3. Wire into `daemon.py` and `__main__.py` with a CLI flag
4. Reuse the pipeline: `render_frames_to_chunks(frames)` -> `device.upload_image(chunks)`
5. For static widgets, `render_to_chunks(single_image)` still works
