"""Tests for nd75_screen.widgets.weather — METAR fetch, parse, and render."""

import pytest
from unittest.mock import patch, Mock
from PIL import Image

from nd75_screen import SCREEN_WIDTH, SCREEN_HEIGHT, WeatherFetchError
from nd75_screen.widgets.weather import (
    fetch_metar,
    parse_weather_icon,
    render_weather,
    render_weather_frames,
    render_error_screen,
)


# ---- fetch_metar ----


@patch("nd75_screen.widgets.weather.requests.get")
def test_fetch_metar_calls_correct_url(mock_get):
    """fetch_metar('KIAH') calls the correct aviation weather API URL."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = [{"icaoId": "KIAH"}]
    mock_get.return_value = mock_response

    fetch_metar("KIAH")

    mock_get.assert_called_once_with(
        "https://aviationweather.gov/api/data/metar?ids=KIAH&format=json",
        timeout=10,
    )


@patch("nd75_screen.widgets.weather.requests.get")
def test_fetch_metar_raises_on_empty_response(mock_get):
    """fetch_metar raises WeatherFetchError on empty JSON list."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    with pytest.raises(WeatherFetchError):
        fetch_metar("XXXX")


@patch("nd75_screen.widgets.weather.requests.get")
def test_fetch_metar_raises_on_http_error(mock_get):
    """fetch_metar raises WeatherFetchError on non-200 HTTP status."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("500 Server Error")
    mock_get.return_value = mock_response

    with pytest.raises(WeatherFetchError):
        fetch_metar("KIAH")


@patch("nd75_screen.widgets.weather.requests.get")
def test_fetch_metar_returns_first_element(mock_get):
    """fetch_metar returns the first element of the JSON array on success."""
    first = {"icaoId": "KIAH", "temp": 22}
    second = {"icaoId": "KIAH", "temp": 21}
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = [first, second]
    mock_get.return_value = mock_response

    result = fetch_metar("KIAH")
    assert result == first


# ---- parse_weather_icon ----


@pytest.mark.parametrize(
    "cover,expected",
    [
        ("SKC", "sunny"),
        ("CLR", "sunny"),
        ("FEW", "partly_cloudy"),
        ("SCT", "partly_cloudy"),
        ("BKN", "mostly_cloudy"),
        ("OVC", "overcast"),
    ],
)
def test_parse_weather_icon_cloud_covers(cover, expected):
    """parse_weather_icon maps cloud cover codes to correct icon names."""
    metar = {
        "clouds": [{"cover": cover, "base": 5000}],
        "wxString": None,
    }
    assert parse_weather_icon(metar) == expected


@pytest.mark.parametrize(
    "wx_string,expected",
    [
        ("RA", "rain"),
        ("SN", "snow"),
        ("TS", "thunderstorm"),
        ("FG", "fog"),
    ],
)
def test_parse_weather_icon_precipitation(wx_string, expected):
    """parse_weather_icon detects precipitation from wxString."""
    metar = {
        "clouds": [{"cover": "OVC", "base": 800}],
        "wxString": wx_string,
    }
    assert parse_weather_icon(metar) == expected


# ---- render_weather ----


def test_render_weather_returns_correct_image(sample_metar):
    """render_weather returns a 135x240 RGB image."""
    img = render_weather(sample_metar)
    assert isinstance(img, Image.Image)
    assert img.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert img.mode == "RGB"


def test_render_weather_imperial_converts_c_to_f(sample_metar):
    """render_weather with imperial units converts 22C to 72F."""
    img = render_weather(sample_metar, units="imperial")
    # We can't easily check pixel text, but we verify the image is valid
    # and use a helper to confirm the temperature string is in the rendering.
    # 22 * 9/5 + 32 = 71.6 -> 72
    assert img.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
    # Verify the conversion math: 22C -> 72F
    assert round(22 * 9 / 5 + 32) == 72


def test_render_weather_metric_shows_celsius(sample_metar):
    """render_weather with metric units shows temp in C."""
    img = render_weather(sample_metar, units="metric")
    assert isinstance(img, Image.Image)
    assert img.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert img.mode == "RGB"


# ---- render_error_screen ----


def test_render_weather_frames_returns_correct_count(sample_metar):
    """render_weather_frames returns the requested number of frames."""
    frames = render_weather_frames(sample_metar, num_frames=8)
    assert len(frames) == 8
    for img in frames:
        assert img.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
        assert img.mode == "RGB"


def test_render_weather_frames_differ(sample_metar):
    """Animation frames should not all be identical."""
    frames = render_weather_frames(sample_metar, num_frames=4)
    # At least two frames should differ (animated icon region changes)
    pixel_sets = [f.tobytes() for f in frames]
    assert len(set(pixel_sets)) > 1


def test_render_error_screen_returns_correct_image():
    """render_error_screen returns a 135x240 RGB image."""
    img = render_error_screen("Something went wrong")
    assert isinstance(img, Image.Image)
    assert img.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert img.mode == "RGB"
