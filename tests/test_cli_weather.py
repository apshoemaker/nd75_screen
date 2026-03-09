"""Tests for nd75_screen.cli.weather — weather producer CLI."""

import io

from PIL import Image
from unittest.mock import patch

from nd75_screen import SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.cli.weather import main
from nd75_screen.renderer import read_frames


def _make_metar(**overrides):
    """Minimal METAR dict for testing."""
    base = {
        "icaoId": "KIAH",
        "reportTime": "2026-03-09T14:53:00Z",
        "temp": 22,
        "dewp": 16,
        "wdir": 270,
        "wspd": 12,
        "wgst": None,
        "visib": 10,
        "altim": 30.12,
        "fltcat": "VFR",
        "name": "George Bush Intercontinental",
        "clouds": [{"cover": "FEW", "base": 5000}],
        "wxString": None,
        "rawOb": "KIAH 091453Z 27012KT 10SM FEW050 22/16 A3012",
    }
    base.update(overrides)
    return base


@patch("nd75_screen.cli.weather.fetch_metar")
@patch("nd75_screen.cli.weather.detect_station", return_value="KIAH")
def test_weather_outputs_gif_to_stdout(mock_detect, mock_fetch):
    """Captured stdout should be a valid animated GIF with 8 frames."""
    mock_fetch.return_value = _make_metar()

    buf = io.BytesIO()
    with patch("nd75_screen.cli.weather.sys") as mock_sys:
        mock_sys.stdout.buffer = buf
        main([])

    buf.seek(0)
    assert buf.read(4) == b"GIF8"  # GIF magic bytes

    buf.seek(0)
    frames = read_frames(buf)
    assert len(frames) == 8
    assert frames[0].size == (SCREEN_WIDTH, SCREEN_HEIGHT)


@patch("nd75_screen.cli.weather.fetch_metar")
@patch("nd75_screen.cli.weather.detect_station", return_value="KORD")
def test_weather_auto_detects_station(mock_detect, mock_fetch):
    """When no --station is given, detect_station should be called."""
    mock_fetch.return_value = _make_metar()

    buf = io.BytesIO()
    with patch("nd75_screen.cli.weather.sys") as mock_sys:
        mock_sys.stdout.buffer = buf
        main([])

    mock_detect.assert_called_once()
    mock_fetch.assert_called_once_with("KORD")


@patch("nd75_screen.cli.weather.fetch_metar")
@patch("nd75_screen.cli.weather.detect_station")
def test_weather_explicit_station(mock_detect, mock_fetch):
    """--station KJFK should bypass auto-detection."""
    mock_fetch.return_value = _make_metar(icaoId="KJFK")

    buf = io.BytesIO()
    with patch("nd75_screen.cli.weather.sys") as mock_sys:
        mock_sys.stdout.buffer = buf
        main(["--station", "KJFK"])

    mock_detect.assert_not_called()
    mock_fetch.assert_called_once_with("KJFK")
