# nd75-screen

Push custom screens to Chilkey ND75 keyboard LCD (135x240, RGB565). Open-source replacement for the Windows-only Chilkey configurator.

## Quick Reference

```bash
uv run pytest tests/ -v          # Run all tests
uv run nd75-screen --help         # CLI help
uv run nd75-screen --image a.png  # Push image to LCD
uv run nd75-screen --once -s KIAH # Push weather once
uv run nd75-screen -s KIAH -i 300 # Start daemon
```

## Project Structure

```
nd75_screen/
  __init__.py      # Constants (dimensions, VID/PID, chunk sizes), exception classes
  __main__.py      # CLI (argparse): --station, --interval, --units, --once, --image
  hid.py           # ND75Device class — USB HID protocol orchestration
  renderer.py      # PIL Image -> RGB565-LE bytes -> 16 wire-ready chunks
  daemon.py        # Background loop: fetch -> render -> upload, with caching
  widgets/
    weather.py     # METAR fetch, icon parsing, PIL rendering, error screen
tests/
  conftest.py      # Fixtures: sample_metar, sample_metar_bad_weather, MockHIDDevice
  test_renderer.py # RGB565 conversion + chunking (14 tests)
  test_hid.py      # HID protocol with mocked hidapi (12 tests)
  test_weather.py  # METAR fetch + render with mocked HTTP (18 tests)
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
| `NUM_CHUNKS` | 16 | Chunks per frame |
| `HEADER_SIZE` | 256 | Header in chunk 0 |
| `ALLOWED_COMMANDS` | {0x18, 0x72, 0x02} | Whitelisted command bytes |

## Module Boundaries

| Module | Owns | Depends On |
|--------|------|------------|
| `renderer.py` | Image -> RGB565 -> chunks | Pillow, `__init__` constants |
| `hid.py` | USB protocol (ND75Device) | `hidapi`, `__init__` constants/exceptions |
| `widgets/weather.py` | METAR fetch + PIL rendering | `requests`, Pillow, `__init__` |
| `daemon.py` | Glue loop with caching | All three above |
| `__main__.py` | CLI, signal handling | `daemon`, `hid`, `renderer` |

## Lessons Learned

### Daemon do-while pattern
`while not stop_event.is_set()` skips the body if event is pre-set (e.g. `--once`). Use `while True` + `if stop_event.wait(timeout): break` at end to guarantee at least one iteration.

### HID mocking
Mock at `hid.enumerate` and `hid.Device` level, not `ND75Device` internals. `conftest.MockHIDDevice` tracks `.written` and `.features_sent` lists.

### RGB565 byte order
Little-endian: red (255,0,0) = 0xF800 -> bytes `[0x00, 0xF8]`. If colors look swapped on hardware, flip byte order.

### Parallel agent coordination
Scaffolding phase commits `__init__.py` with all constants/exceptions before agents fork into worktrees. Each agent touches only its module + test file, never shared files.

## Deep Dives

- **[docs/protocol.md](docs/protocol.md)** — USB HID wire protocol: device identification, feature report format, upload flow, safety
- **[docs/rendering.md](docs/rendering.md)** — RGB565 bit layout, reference color values, chunk structure, image preprocessing
- **[docs/weather-widget.md](docs/weather-widget.md)** — METAR API endpoint, response fields, icon mapping rules, screen layout, error display

## Adding a New Widget

1. Create `nd75_screen/widgets/your_widget.py` with `render_*(data) -> Image`
2. Create `tests/test_your_widget.py` with mocked external calls
3. Wire into `daemon.py` and `__main__.py` with a CLI flag
4. Reuse the pipeline: `render_to_chunks(your_image)` -> `device.upload_image(chunks)`
