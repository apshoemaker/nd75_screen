# ⌨️ nd75-screen

Push custom screens to the **Chilkey ND75** keyboard's tiny LCD — and keep its clock in sync too! 🕐

The ND75 has a 135×240 color LCD hidden between the keys. This tool takes it over with live weather data, custom images, and animated icons — all from the command line.

## ✨ Features

- 🌤️ **Live aviation weather** — pulls real-time METAR data and renders animated weather icons
- 📍 **Auto-detect your location** — finds the nearest airport via IP geolocation, no config needed
- 🕐 **Clock sync** — sets the keyboard's built-in RTC to your system time
- 🖼️ **Custom images** — push any PNG/JPG to the screen
- 🎞️ **Animated icons** — 8 weather types with smooth multi-frame animations (the firmware animates them natively, like a GIF!)
- 🔄 **Daemon mode** — refreshes weather on a schedule, survives USB reconnects
- 🔗 **Unix pipes** — composable producer/consumer commands for flexible workflows
- 🤖 **LLM GIF generation** — create ND75-ready GIFs from a text prompt with Anthropic Sonnet

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/your-username/nd75-screen.git
cd nd75-screen
uv sync

# Push weather to the screen (auto-detects your nearest airport)
uv run python -m nd75_screen --once -v

# Just sync the clock
uv run python -m nd75_screen --sync-time

# Run as a daemon (refreshes every 5 minutes)
uv run python -m nd75_screen

# Use a specific airport
uv run python -m nd75_screen --once -s KJFK

# Push a custom image
uv run python -m nd75_screen --image my_photo.png

# Unix pipes — composable producer/consumer commands
uv run python -m nd75_screen.cli.weather | uv run python -m nd75_screen.cli.push
cat photo.png | uv run python -m nd75_screen.cli.push
uv run python -m nd75_screen.cli.push photo.png
uv run python -m nd75_screen.cli.weather > /tmp/weather.gif
uv run nd75-llm-gif "neon synthwave sunset over a city" | uv run python -m nd75_screen.cli.push
```

## 🛠️ CLI Options

| Flag | Description |
|------|-------------|
| `-s`, `--station ICAO` | Airport code (auto-detected if omitted) |
| `-i`, `--interval SEC` | Refresh interval in seconds (default: 300) |
| `-u`, `--units` | `imperial` or `metric` (default: imperial) |
| `--once` | Push one screen and exit |
| `--image FILE` | Push a raw image file |
| `--sync-time` | Sync keyboard clock and exit |
| `--no-time-sync` | Skip auto time sync on startup |
| `-v`, `--verbose` | Show debug logging |

## 🔗 Unix Pipes

Content production is decoupled from device push — any program that outputs a PNG or GIF can pipe into the push command:

```
PRODUCER (stdout)              PIPE         CONSUMER (stdin)
─────────────────              ────         ────────────────
nd75_screen.cli.weather ──→ GIF bytes ──→ nd75_screen.cli.push ──→ HID upload
cat photo.png           ──→ PNG bytes ──→ nd75_screen.cli.push ──→ HID upload
```

**`nd75_screen.cli.weather`** (producer) options:

| Flag | Description |
|------|-------------|
| `-s`, `--station ICAO` | Airport code (auto-detected if omitted) |
| `-u`, `--units` | `imperial` or `metric` (default: imperial) |
| `--frames N` | Number of animation frames (default: 8) |

**`nd75_screen.cli.push`** (consumer) options:

| Flag | Description |
|------|-------------|
| `[file]` | Image file path (reads stdin if omitted) |
| `--sync-time` | Sync keyboard clock before pushing |

**`nd75-llm-gif`** (producer) options:

| Flag | Description |
|------|-------------|
| `prompt` | Natural-language animation description |
| `--model MODEL` | Anthropic model name (default: `claude-sonnet-4-5`) |
| `--api-key KEY` | Anthropic API key (defaults to `ANTHROPIC_API_KEY`) |

## 🌡️ Weather Display

The weather widget shows:

```
    KIAH
 George Bush Intl
   ☀️ (animated!)
     72°F
   270° @ 12kt
     10 SM
      VFR
  KIAH 091453Z 27012KT...
```

Eight animated icon types: ☀️ sunny, 🌤️ partly cloudy, ☁️ mostly cloudy, 🌫️ overcast, 🌧️ rain, ❄️ snow, ⛈️ thunderstorm, 🌁 fog

## 🔌 How It Works

Communication happens over USB HID with two interfaces:

- **Command channel** (usage page `0xFF13`) — 64-byte feature reports for session management, time sync
- **Data channel** (usage page `0xFF68`) — 4096-byte chunks of RGB565 pixel data

The LCD is a 135×240 ST7789-style SPI TFT. Images are converted to RGB565 (little-endian), chunked into 16 packets, and streamed with per-chunk ACKs. Multi-frame animations are packed sequentially and the firmware handles playback.

Time sync was reverse-engineered from the [official web configurator](https://nd75.chilkey.com/) 🕵️

## 📋 Requirements

- Python 3.14+
- macOS (tested) — needs **Input Monitoring** permission for HID access
- [uv](https://docs.astral.sh/uv/) for package management

## 🧪 Development

```bash
uv run pytest tests/ -v    # 76 tests, all mocked — no hardware needed
```

## 📄 License

[Unlicense](LICENSE) — public domain. Do whatever you want with it. 🎉
