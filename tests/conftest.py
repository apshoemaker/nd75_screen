"""Shared test fixtures for nd75-screen."""

import pytest


@pytest.fixture
def sample_metar():
    """Realistic METAR JSON response for KIAH (Houston Intercontinental)."""
    return {
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
        "clouds": [
            {"cover": "FEW", "base": 5000},
            {"cover": "SCT", "base": 8000},
        ],
        "wxString": None,
        "rawOb": "KIAH 091453Z 27012KT 10SM FEW050 SCT080 22/16 A3012 RMK AO2",
    }


@pytest.fixture
def sample_metar_bad_weather():
    """METAR with precipitation and low ceilings."""
    return {
        "icaoId": "KJFK",
        "reportTime": "2026-03-09T14:53:00Z",
        "temp": 2,
        "dewp": 1,
        "wdir": 30,
        "wspd": 18,
        "wgst": 25,
        "visib": 1.5,
        "altim": 29.85,
        "fltcat": "IFR",
        "name": "John F Kennedy Intl",
        "clouds": [
            {"cover": "BKN", "base": 400},
            {"cover": "OVC", "base": 800},
        ],
        "wxString": "RA BR",
        "rawOb": "KJFK 091453Z 03018G25KT 1 1/2SM RA BR BKN004 OVC008 02/01 A2985 RMK AO2",
    }


class MockHIDDevice:
    """Mock hidapi device for testing."""

    def __init__(self, ack_response=None, read_response=None):
        self.written = []
        self.features_sent = []
        self.closed = False
        self._ack_response = ack_response or b"\x00" * 64
        self._read_response = read_response or b"\x00" * 64

    def write(self, data):
        self.written.append(bytes(data))
        return len(data)

    def send_feature_report(self, data):
        self.features_sent.append(bytes(data))
        return len(data)

    def get_feature_report(self, report_id, length):
        return list(self._ack_response[:length])

    def read(self, length, timeout_ms=None):
        return list(self._read_response[:length])

    def close(self):
        self.closed = True


@pytest.fixture
def mock_hid_device():
    """Factory for MockHIDDevice instances."""
    def factory(**kwargs):
        return MockHIDDevice(**kwargs)
    return factory
