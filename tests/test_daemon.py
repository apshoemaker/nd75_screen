"""Tests for the background refresh daemon."""

import threading
from unittest.mock import MagicMock, patch, call

import pytest
from PIL import Image

from nd75_screen import SCREEN_WIDTH, SCREEN_HEIGHT, WeatherFetchError
from nd75_screen.daemon import run_loop


@pytest.fixture
def mock_deps():
    """Patch weather and HID dependencies, return mocks."""
    metar = {
        "icaoId": "KIAH",
        "temp": 22,
        "dewp": 16,
        "wdir": 270,
        "wspd": 12,
        "wgst": None,
        "visib": 10,
        "fltcat": "VFR",
        "name": "George Bush Intercontinental",
        "clouds": [{"cover": "FEW", "base": 5000}],
        "wxString": None,
        "rawOb": "KIAH 091453Z 27012KT 10SM FEW050 22/16 A3012",
        "reportTime": "2026-03-09T14:53:00Z",
        "altim": 30.12,
    }

    with (
        patch("nd75_screen.daemon.fetch_metar", return_value=metar) as m_fetch,
        patch("nd75_screen.daemon.render_weather_frames") as m_render,
        patch("nd75_screen.daemon.render_error_screen") as m_render_err,
        patch("nd75_screen.daemon.render_frames_to_chunks", return_value=[b"\x00" * 4096] * 16) as m_chunks,
        patch("nd75_screen.daemon.render_to_chunks", return_value=[b"\x00" * 4096] * 16),
        patch("nd75_screen.daemon.ND75Device") as m_device_cls,
    ):
        m_render.return_value = [Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT))]
        m_render_err.return_value = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT))
        m_device = MagicMock()
        m_device_cls.return_value.__enter__ = MagicMock(return_value=m_device)
        m_device_cls.return_value.__exit__ = MagicMock(return_value=False)

        yield {
            "fetch": m_fetch,
            "render": m_render,
            "render_err": m_render_err,
            "chunks": m_chunks,
            "device_cls": m_device_cls,
            "device": m_device,
        }


class TestDaemonLoop:
    def test_calls_fetch_render_upload_in_sequence(self, mock_deps):
        """Daemon calls fetch -> render -> chunks -> upload."""
        stop = threading.Event()
        stop.set()  # Stop immediately after one iteration

        run_loop("KIAH", 300, "imperial", stop)

        mock_deps["fetch"].assert_called_once_with("KIAH")
        mock_deps["render"].assert_called_once()
        mock_deps["chunks"].assert_called_once()
        mock_deps["device"].upload_image.assert_called_once()

    def test_caches_last_image_on_fetch_failure(self, mock_deps):
        """On second iteration, if fetch fails, use cached image."""
        stop = threading.Event()
        call_count = 0

        def stop_after_two(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop.set()
            return True

        # First call succeeds, second raises
        mock_deps["fetch"].side_effect = [
            mock_deps["fetch"].return_value,
            WeatherFetchError("network down"),
        ]
        mock_deps["device"].upload_image.side_effect = stop_after_two

        run_loop("KIAH", 0, "imperial", stop)

        # Upload called twice (once with fresh, once with cached)
        assert mock_deps["device"].upload_image.call_count == 2

    def test_shows_error_screen_when_no_cache_and_fetch_fails(self, mock_deps):
        """If fetch fails on first try with no cache, show error screen."""
        stop = threading.Event()
        stop.set()

        mock_deps["fetch"].side_effect = WeatherFetchError("network down")

        run_loop("KIAH", 300, "imperial", stop)

        mock_deps["render_err"].assert_called_once()
        mock_deps["device"].upload_image.assert_called_once()

    def test_rediscovers_device_on_hid_error(self, mock_deps):
        """On HID error, device is re-created on next iteration."""
        from nd75_screen import TransferError

        stop = threading.Event()
        call_count = 0

        def upload_side_effect(chunks):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TransferError("USB disconnected")
            stop.set()

        mock_deps["device"].upload_image.side_effect = upload_side_effect

        run_loop("KIAH", 0, "imperial", stop)

        # Should have attempted upload twice
        assert mock_deps["device"].upload_image.call_count >= 2

    def test_shutdown_event_stops_loop(self, mock_deps):
        """Setting the stop event stops the daemon loop."""
        stop = threading.Event()

        def set_stop(*args, **kwargs):
            stop.set()

        mock_deps["device"].upload_image.side_effect = set_stop

        # Should return without hanging
        run_loop("KIAH", 300, "imperial", stop)

        assert stop.is_set()
