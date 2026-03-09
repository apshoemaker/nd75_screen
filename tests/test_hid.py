"""Tests for nd75_screen.hid — USB HID communication with ND75 keyboard."""

import datetime
from unittest.mock import patch, MagicMock, call
import pytest

from nd75_screen import (
    VID, PID, CMD_USAGE_PAGE, DATA_USAGE_PAGE,
    ALLOWED_COMMANDS, FEATURE_REPORT_SIZE, REPORT_PREFIX,
    CHUNK_SIZE, NUM_CHUNKS, ACK_TIMEOUT,
    DeviceNotFoundError, AckTimeoutError, TransferError,
)
from nd75_screen.hid import ND75Device


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_enum_entry(usage_page, path):
    """Build a minimal hid.enumerate() dict."""
    return {
        "vendor_id": VID,
        "product_id": PID,
        "usage_page": usage_page,
        "path": path,
    }


FAKE_CMD_PATH = b"/dev/hid-cmd"
FAKE_DATA_PATH = b"/dev/hid-data"


def _standard_enumerate_result():
    return [
        _make_enum_entry(CMD_USAGE_PAGE, FAKE_CMD_PATH),
        _make_enum_entry(DATA_USAGE_PAGE, FAKE_DATA_PATH),
        _make_enum_entry(0x0001, b"/dev/hid-other"),  # irrelevant interface
    ]


# ---------------------------------------------------------------------------
# 1. _discover() finds correct interfaces by usage_page
# ---------------------------------------------------------------------------

class TestDiscover:
    @patch("nd75_screen.hid.hid")
    def test_discover_finds_correct_interfaces(self, mock_hid):
        mock_hid.enumerate.return_value = _standard_enumerate_result()

        dev = ND75Device()
        dev._discover()

        mock_hid.enumerate.assert_called_once_with(VID, PID)
        assert dev._cmd_path == FAKE_CMD_PATH
        assert dev._data_path == FAKE_DATA_PATH

    # 2. _discover() raises DeviceNotFoundError when keyboard not found
    @patch("nd75_screen.hid.hid")
    def test_discover_raises_when_no_device(self, mock_hid):
        mock_hid.enumerate.return_value = []

        dev = ND75Device()
        with pytest.raises(DeviceNotFoundError):
            dev._discover()

    @patch("nd75_screen.hid.hid")
    def test_discover_raises_when_missing_data_interface(self, mock_hid):
        # Only CMD interface present, no DATA
        mock_hid.enumerate.return_value = [
            _make_enum_entry(CMD_USAGE_PAGE, FAKE_CMD_PATH),
        ]

        dev = ND75Device()
        with pytest.raises(DeviceNotFoundError):
            dev._discover()


# ---------------------------------------------------------------------------
# 3. _send_command() pads to 64 bytes
# ---------------------------------------------------------------------------

class TestSendCommand:
    @patch("nd75_screen.hid.hid")
    def test_send_command_pads_to_64_bytes(self, mock_hid):
        mock_hid.enumerate.return_value = _standard_enumerate_result()

        cmd_dev = MagicMock()
        cmd_dev.get_feature_report.return_value = [0] * FEATURE_REPORT_SIZE
        data_dev = MagicMock()

        mock_hid.device.side_effect = [cmd_dev, data_dev]

        dev = ND75Device()
        dev._discover()
        dev._open()

        dev._send_command(0x18)

        sent = cmd_dev.send_feature_report.call_args[0][0]
        assert len(sent) == FEATURE_REPORT_SIZE
        assert sent[0] == REPORT_PREFIX
        assert sent[1] == 0x18
        # Rest should be zero-padded
        assert all(b == 0 for b in sent[2:])

    # 4. _send_command() rejects non-whitelisted command bytes
    @patch("nd75_screen.hid.hid")
    def test_send_command_rejects_non_whitelisted(self, mock_hid):
        mock_hid.enumerate.return_value = _standard_enumerate_result()
        data_dev = MagicMock()
        mock_hid.device.side_effect = [MagicMock(), data_dev]

        dev = ND75Device()
        dev._discover()
        dev._open()

        with pytest.raises(ValueError, match="not allowed"):
            dev._send_command(0xFF)


# ---------------------------------------------------------------------------
# 5. upload_image() sends commands in correct sequence
# ---------------------------------------------------------------------------

class TestUploadImage:
    def _setup_device(self, mock_hid, cmd_dev=None, data_dev=None):
        """Wire up mock_hid so ND75Device._open() gets our mock devices."""
        mock_hid.enumerate.return_value = _standard_enumerate_result()

        if cmd_dev is None:
            cmd_dev = MagicMock()
            cmd_dev.get_feature_report.return_value = [0] * FEATURE_REPORT_SIZE
        if data_dev is None:
            data_dev = MagicMock()
            data_dev.read.return_value = [0] * 64  # ACK

        # hid.device() is called twice: first for cmd, then for data
        mock_hid.device.side_effect = [cmd_dev, data_dev]

        return cmd_dev, data_dev

    @patch("nd75_screen.hid.hid")
    def test_upload_correct_sequence(self, mock_hid):
        cmd_dev = MagicMock()
        # Finalize response: byte[3] == 1 means success
        finalize_resp = [0] * FEATURE_REPORT_SIZE
        finalize_resp[3] = 1
        cmd_dev.get_feature_report.return_value = finalize_resp

        data_dev = MagicMock()
        data_dev.read.return_value = [0] * 64  # ACK

        self._setup_device(mock_hid, cmd_dev, data_dev)

        dev = ND75Device()
        chunks = [b"\x00" * CHUNK_SIZE for _ in range(NUM_CHUNKS)]
        dev.upload_image(chunks)

        # Verify command sequence via send_feature_report calls
        feature_calls = cmd_dev.send_feature_report.call_args_list
        assert len(feature_calls) == 3  # start, initiate, finalize

        # First call: start session (0x18)
        assert feature_calls[0][0][0][1] == 0x18
        # Second call: initiate LCD (0x72)
        assert feature_calls[1][0][0][1] == 0x72
        # Third call: finalize (0x02)
        assert feature_calls[2][0][0][1] == 0x02

    # 6. upload_image() waits for ACK between each chunk
    @patch("nd75_screen.hid.hid")
    def test_upload_waits_for_ack(self, mock_hid):
        cmd_dev = MagicMock()
        finalize_resp = [0] * FEATURE_REPORT_SIZE
        finalize_resp[3] = 1
        cmd_dev.get_feature_report.return_value = finalize_resp

        data_dev = MagicMock()
        data_dev.read.return_value = [0] * 64

        self._setup_device(mock_hid, cmd_dev, data_dev)

        dev = ND75Device()
        chunks = [b"\xAB" * CHUNK_SIZE for _ in range(NUM_CHUNKS)]
        dev.upload_image(chunks)

        # data_dev.write called 16 times, data_dev.read called 16 times
        assert data_dev.write.call_count == NUM_CHUNKS
        assert data_dev.read.call_count == NUM_CHUNKS

    # 7. AckTimeoutError raised on ACK timeout
    @patch("nd75_screen.hid.hid")
    def test_ack_timeout_raises(self, mock_hid):
        cmd_dev = MagicMock()
        cmd_dev.get_feature_report.return_value = [0] * FEATURE_REPORT_SIZE

        data_dev = MagicMock()
        data_dev.read.return_value = []  # empty = timeout

        self._setup_device(mock_hid, cmd_dev, data_dev)

        dev = ND75Device()
        chunks = [b"\x00" * CHUNK_SIZE for _ in range(NUM_CHUNKS)]

        with pytest.raises(AckTimeoutError):
            dev.upload_image(chunks)

    # 8. upload_image() rejects empty chunks
    @patch("nd75_screen.hid.hid")
    def test_upload_rejects_empty_chunks(self, mock_hid):
        mock_hid.enumerate.return_value = _standard_enumerate_result()

        dev = ND75Device()
        with pytest.raises(ValueError, match="empty"):
            dev.upload_image([])

    # 9. Device re-discovery on HID errors
    @patch("nd75_screen.hid.hid")
    def test_rediscovery_on_hid_error(self, mock_hid):
        cmd_dev = MagicMock()
        cmd_dev.send_feature_report.side_effect = OSError("HID write failed")
        cmd_dev.get_feature_report.return_value = [0] * FEATURE_REPORT_SIZE

        data_dev = MagicMock()

        self._setup_device(mock_hid, cmd_dev, data_dev)

        dev = ND75Device()
        chunks = [b"\x00" * CHUNK_SIZE for _ in range(NUM_CHUNKS)]

        with pytest.raises(TransferError):
            dev.upload_image(chunks)

        # After error, devices should be closed (so next call re-discovers)
        assert dev._cmd_dev is None
        assert dev._data_dev is None


# ---------------------------------------------------------------------------
# 10. Context manager opens/closes correctly
# ---------------------------------------------------------------------------

class TestContextManager:
    @patch("nd75_screen.hid.hid")
    def test_context_manager(self, mock_hid):
        mock_hid.enumerate.return_value = _standard_enumerate_result()
        mock_dev = MagicMock()
        mock_hid.device.return_value = mock_dev

        with ND75Device() as dev:
            assert isinstance(dev, ND75Device)

        # close() should have been called
        # Verify internal state is reset
        assert dev._cmd_dev is None
        assert dev._data_dev is None


# ---------------------------------------------------------------------------
# 11. Finalize failure logged but doesn't crash
# ---------------------------------------------------------------------------

class TestFinalizeFailure:
    @patch("nd75_screen.hid.hid")
    def test_finalize_failure_logged_no_crash(self, mock_hid, caplog):
        cmd_dev = MagicMock()
        # Finalize response: byte[3] != 1 means failure
        bad_finalize = [0] * FEATURE_REPORT_SIZE
        bad_finalize[3] = 0  # failure indicator
        cmd_dev.get_feature_report.return_value = bad_finalize

        data_dev = MagicMock()
        data_dev.read.return_value = [0] * 64

        # Wire up
        mock_hid.enumerate.return_value = _standard_enumerate_result()
        mock_hid.device.side_effect = [cmd_dev, data_dev]

        dev = ND75Device()
        chunks = [b"\x00" * CHUNK_SIZE for _ in range(NUM_CHUNKS)]

        import logging
        with caplog.at_level(logging.WARNING):
            dev.upload_image(chunks)  # should NOT raise

        assert any("finalize" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 12. sync_time() sends correct protocol sequence
# ---------------------------------------------------------------------------

class TestSyncTime:
    def _setup_device(self, mock_hid, cmd_dev=None, data_dev=None):
        mock_hid.enumerate.return_value = _standard_enumerate_result()
        if cmd_dev is None:
            cmd_dev = MagicMock()
            cmd_dev.get_feature_report.return_value = [0] * FEATURE_REPORT_SIZE
        if data_dev is None:
            data_dev = MagicMock()
        mock_hid.device.side_effect = [cmd_dev, data_dev]
        return cmd_dev, data_dev

    @patch("nd75_screen.hid.hid")
    def test_sync_time_sends_correct_sequence(self, mock_hid):
        cmd_dev, _ = self._setup_device(mock_hid)

        dev = ND75Device()
        dt = datetime.datetime(2026, 3, 9, 14, 30, 45)  # Sunday
        dev.sync_time(dt)

        calls = cmd_dev.send_feature_report.call_args_list
        # 4 feature reports: start(0x18), initiate(0x28), time payload, finalize(0x02)
        assert len(calls) == 4

        # Start session
        assert calls[0][0][0][1] == 0x18
        # Initiate time command
        assert calls[1][0][0][1] == 0x28
        # Finalize
        assert calls[3][0][0][1] == 0x02

    @patch("nd75_screen.hid.hid")
    def test_sync_time_payload_format(self, mock_hid):
        cmd_dev, _ = self._setup_device(mock_hid)

        dev = ND75Device()
        # 2026-03-09 14:30:45, March 9 2026 is Monday
        dt = datetime.datetime(2026, 3, 9, 14, 30, 45)
        dev.sync_time(dt)

        # Third call is the raw time payload (65 bytes: report ID + 64 data)
        payload = cmd_dev.send_feature_report.call_args_list[2][0][0]
        assert len(payload) == FEATURE_REPORT_SIZE + 1
        assert payload[0] == 0x00    # report ID (stripped by hidapi on macOS)
        assert payload[1] == 0x00    # data byte 0
        assert payload[2] == 0x01    # data byte 1
        assert payload[3] == 0x5A    # time sync marker
        assert payload[4] == 26      # year % 100
        assert payload[5] == 3       # month
        assert payload[6] == 9       # day
        assert payload[7] == 14      # hour
        assert payload[8] == 30      # minute
        assert payload[9] == 45      # second
        assert payload[10] == 0x00
        # Monday: Python weekday()=0, firmware=(0+1)%7=1
        assert payload[11] == 1
        assert payload[63] == 0xAA
        assert payload[64] == 0x55

    @patch("nd75_screen.hid.hid")
    def test_sync_time_sunday_is_zero(self, mock_hid):
        """Sunday should map to 0 in firmware's day-of-week."""
        cmd_dev, _ = self._setup_device(mock_hid)

        dev = ND75Device()
        # 2026-03-08 is a Sunday (weekday()=6)
        dt = datetime.datetime(2026, 3, 8, 12, 0, 0)
        dev.sync_time(dt)

        payload = cmd_dev.send_feature_report.call_args_list[2][0][0]
        # Sunday: Python weekday()=6, firmware=(6+1)%7=0
        # payload[11] because payload[0] is the report ID byte
        assert payload[11] == 0

    @patch("nd75_screen.hid.hid")
    def test_sync_time_defaults_to_now(self, mock_hid):
        """sync_time() without args uses current time."""
        cmd_dev, _ = self._setup_device(mock_hid)

        dev = ND75Device()
        dev.sync_time()

        # Should have sent 4 feature reports without error
        assert cmd_dev.send_feature_report.call_count == 4

    @patch("nd75_screen.hid.hid")
    def test_sync_time_closes_on_os_error(self, mock_hid):
        """sync_time raises TransferError and closes devices on OSError."""
        cmd_dev, _ = self._setup_device(mock_hid)
        cmd_dev.send_feature_report.side_effect = OSError("HID write failed")

        dev = ND75Device()
        with pytest.raises(TransferError):
            dev.sync_time()

        assert dev._cmd_dev is None
        assert dev._data_dev is None
