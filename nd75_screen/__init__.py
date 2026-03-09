"""nd75-screen: Push custom screens to Chilkey ND75 keyboard LCD."""

# Screen dimensions
SCREEN_WIDTH = 135
SCREEN_HEIGHT = 240
BYTES_PER_PIXEL = 2
FRAME_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * BYTES_PER_PIXEL  # 64,800

# Chunking
CHUNK_SIZE = 4096
HEADER_SIZE = 256
NUM_CHUNKS = 16

# USB HID identifiers
VID = 0x36B5
PID = 0x2BA7
CMD_USAGE_PAGE = 0xFF13
DATA_USAGE_PAGE = 0xFF68

# Command bytes (whitelisted)
CMD_START_SESSION = 0x18
CMD_INITIATE_LCD = 0x72
CMD_FINALIZE = 0x02
CMD_TIME_SYNC = 0x28
ALLOWED_COMMANDS = {CMD_START_SESSION, CMD_INITIATE_LCD, CMD_FINALIZE, CMD_TIME_SYNC}

# Protocol constants
FEATURE_REPORT_SIZE = 64
REPORT_PREFIX = 0x04
ACK_TIMEOUT = 5.0
MAX_RETRIES = 2


class ND75Error(Exception):
    """Base exception for nd75-screen."""


class DeviceNotFoundError(ND75Error):
    """Keyboard not found on USB bus."""


class AckTimeoutError(ND75Error):
    """Keyboard did not ACK a data chunk in time."""


class TransferError(ND75Error):
    """Image transfer failed."""


class WeatherFetchError(ND75Error):
    """Failed to fetch METAR data."""
