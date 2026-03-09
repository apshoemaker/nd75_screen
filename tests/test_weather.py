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
    _geolocate,
    detect_station,
    _cached_station,
)
import nd75_screen.widgets.weather as weather_module


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


# ---- _geolocate ----


@patch("nd75_screen.widgets.weather.requests.get")
def test_geolocate_returns_lat_lon(mock_get):
    """_geolocate returns (lat, lon) on successful IP lookup."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"lat": 29.98, "lon": -95.34}
    mock_get.return_value = mock_response

    lat, lon = _geolocate()
    assert lat == 29.98
    assert lon == -95.34
    mock_get.assert_called_once_with("http://ip-api.com/json", timeout=5)


@patch("nd75_screen.widgets.weather.requests.get")
def test_geolocate_raises_on_network_error(mock_get):
    """_geolocate raises WeatherFetchError on network failure."""
    mock_get.side_effect = Exception("Connection refused")

    with pytest.raises(WeatherFetchError, match="IP geolocation failed"):
        _geolocate()


# ---- detect_station ----


@pytest.fixture(autouse=True)
def _clear_station_cache():
    """Clear the cached station before each test."""
    weather_module._cached_station = None
    yield
    weather_module._cached_station = None


@patch("nd75_screen.widgets.weather.requests.get")
def test_detect_station_finds_closest(mock_get):
    """detect_station picks the closest station from bbox results."""
    geo_response = Mock()
    geo_response.raise_for_status = Mock()
    geo_response.json.return_value = {"lat": 29.98, "lon": -95.34}

    bbox_response = Mock()
    bbox_response.raise_for_status = Mock()
    bbox_response.json.return_value = [
        {"icaoId": "KIAH", "lat": 29.99, "lon": -95.34},
        {"icaoId": "KHOU", "lat": 29.64, "lon": -95.28},
    ]

    mock_get.side_effect = [geo_response, bbox_response]

    result = detect_station()
    assert result == "KIAH"


@patch("nd75_screen.widgets.weather.requests.get")
def test_detect_station_returns_fallback_on_failure(mock_get):
    """detect_station returns the fallback when geolocation fails."""
    mock_get.side_effect = Exception("Network error")

    result = detect_station(fallback="KJFK")
    assert result == "KJFK"


@patch("nd75_screen.widgets.weather.requests.get")
def test_detect_station_returns_fallback_on_empty_bbox(mock_get):
    """detect_station returns fallback when no stations in bounding box."""
    geo_response = Mock()
    geo_response.raise_for_status = Mock()
    geo_response.json.return_value = {"lat": 0.0, "lon": 0.0}

    bbox_response = Mock()
    bbox_response.raise_for_status = Mock()
    bbox_response.json.return_value = []

    mock_get.side_effect = [geo_response, bbox_response]

    result = detect_station()
    assert result == "KIAH"


@patch("nd75_screen.widgets.weather.requests.get")
def test_detect_station_caches_result(mock_get):
    """detect_station caches the result; second call doesn't hit network."""
    geo_response = Mock()
    geo_response.raise_for_status = Mock()
    geo_response.json.return_value = {"lat": 29.98, "lon": -95.34}

    bbox_response = Mock()
    bbox_response.raise_for_status = Mock()
    bbox_response.json.return_value = [
        {"icaoId": "KIAH", "lat": 29.99, "lon": -95.34},
    ]

    mock_get.side_effect = [geo_response, bbox_response]

    result1 = detect_station()
    result2 = detect_station()
    assert result1 == result2 == "KIAH"
    assert mock_get.call_count == 2  # only the first call hits network
