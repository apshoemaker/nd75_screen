"""USB HID communication with the Chilkey ND75 keyboard."""

from __future__ import annotations

import logging

import hid

from nd75_screen import (
    VID,
    PID,
    CMD_USAGE_PAGE,
    DATA_USAGE_PAGE,
    ALLOWED_COMMANDS,
    FEATURE_REPORT_SIZE,
    REPORT_PREFIX,
    CHUNK_SIZE,
    NUM_CHUNKS,
    ACK_TIMEOUT,
    DeviceNotFoundError,
    AckTimeoutError,
    TransferError,
)

log = logging.getLogger(__name__)


class ND75Device:
    """Manages HID communication with a Chilkey ND75 keyboard."""

    def __init__(self) -> None:
        self._cmd_path: bytes | None = None
        self._data_path: bytes | None = None
        self._cmd_dev: hid.device | None = None
        self._data_dev: hid.device | None = None

    # -- Context manager -----------------------------------------------------

    def __enter__(self) -> ND75Device:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- Discovery & open ----------------------------------------------------

    def _discover(self) -> None:
        """Find CMD and DATA HID interface paths by usage_page."""
        devices = hid.enumerate(VID, PID)

        cmd_path = None
        data_path = None

        for info in devices:
            if info["usage_page"] == CMD_USAGE_PAGE:
                cmd_path = info["path"]
            elif info["usage_page"] == DATA_USAGE_PAGE:
                data_path = info["path"]

        if cmd_path is None or data_path is None:
            raise DeviceNotFoundError(
                "Could not find both CMD and DATA HID interfaces for ND75"
            )

        self._cmd_path = cmd_path
        self._data_path = data_path

    def _open(self) -> None:
        """Open both HID devices by path. Call _discover() first."""
        if self._cmd_path is None or self._data_path is None:
            self._discover()

        self._cmd_dev = hid.device()
        self._cmd_dev.open_path(self._cmd_path)
        self._data_dev = hid.device()
        self._data_dev.open_path(self._data_path)

    def close(self) -> None:
        """Close both HID devices and reset internal state."""
        for dev in (self._cmd_dev, self._data_dev):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        self._cmd_dev = None
        self._data_dev = None
        self._cmd_path = None
        self._data_path = None

    # -- Low-level protocol --------------------------------------------------

    def _send_command(self, cmd_byte: int, payload: bytes = b"") -> bytes:
        """Send a feature report command on the CMD interface.

        Returns the response bytes.
        """
        if cmd_byte not in ALLOWED_COMMANDS:
            raise ValueError(
                f"Command byte 0x{cmd_byte:02X} is not allowed. "
                f"Allowed: {', '.join(f'0x{c:02X}' for c in sorted(ALLOWED_COMMANDS))}"
            )

        report = bytearray(FEATURE_REPORT_SIZE)
        report[0] = REPORT_PREFIX
        report[1] = cmd_byte

        # Copy payload into report starting at byte 2
        for i, b in enumerate(payload):
            if 2 + i < FEATURE_REPORT_SIZE:
                report[2 + i] = b

        self._cmd_dev.send_feature_report(bytes(report))
        response = self._cmd_dev.get_feature_report(REPORT_PREFIX, FEATURE_REPORT_SIZE)
        return bytes(response)

    def _send_chunk(self, chunk: bytes) -> None:
        """Send a data chunk to the DATA interface, padded to CHUNK_SIZE."""
        padded = chunk.ljust(CHUNK_SIZE, b"\x00")
        # Report ID prefix 0x00
        self._data_dev.write(b"\x00" + padded)

    def _wait_ack(self) -> None:
        """Wait for an ACK from the DATA device."""
        timeout_ms = int(ACK_TIMEOUT * 1000)
        resp = self._data_dev.read(64, timeout_ms=timeout_ms)
        if not resp:
            raise AckTimeoutError("Keyboard did not ACK data chunk within timeout")

    # -- High-level transfer -------------------------------------------------

    def upload_image(self, chunks: list[bytes]) -> None:
        """Upload an image as *chunks* to the keyboard LCD.

        Args:
            chunks: Exactly NUM_CHUNKS (16) byte-strings of raw pixel data.
        """
        if not chunks:
            raise ValueError("chunks must not be empty")

        # Lazy open
        if self._cmd_dev is None or self._data_dev is None:
            self._discover()
            self._open()

        try:
            # Step 1: Start session
            self._send_command(0x18)

            # Step 2: Initiate LCD transfer
            chunk_count = len(chunks)
            payload = bytes([
                0x02, 0, 0, 0, 0, 0,
                chunk_count & 0xFF,
                (chunk_count >> 8) & 0xFF,
            ])
            self._send_command(0x72, payload)

            # Step 3: Stream chunks with ACK
            for chunk in chunks:
                self._send_chunk(chunk)
                self._wait_ack()

            # Step 4: Finalize
            response = self._send_command(0x02)
            if len(response) > 3 and response[3] != 1:
                log.warning(
                    "Finalize response indicates failure (byte[3]=%d)", response[3]
                )

        except OSError as exc:
            self.close()
            raise TransferError(f"HID transfer failed: {exc}") from exc
