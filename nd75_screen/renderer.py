"""Image to RGB565 chunked wire format for ND75 LCD."""

from __future__ import annotations

import struct

from PIL import Image

from nd75_screen import (
    CHUNK_SIZE,
    FRAME_SIZE,
    HEADER_SIZE,
    NUM_CHUNKS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


def image_to_rgb565(img: Image.Image) -> bytes:
    """Resize *img* to 135x240 and convert to RGB565 little-endian bytes.

    Returns exactly ``FRAME_SIZE`` (64 800) bytes.
    """
    img = img.convert("RGB").resize((SCREEN_WIDTH, SCREEN_HEIGHT))
    pixels = img.tobytes()
    buf = bytearray(FRAME_SIZE)
    out_idx = 0
    for in_idx in range(0, len(pixels), 3):
        r = pixels[in_idx]
        g = pixels[in_idx + 1]
        b = pixels[in_idx + 2]
        value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        struct.pack_into("<H", buf, out_idx, value)
        out_idx += 2
    return bytes(buf)


def rgb565_to_chunks(pixel_data: bytes, frame_count: int = 1) -> list[bytes]:
    """Build a 256-byte header, prepend it to *pixel_data*, and split into
    chunks of ``CHUNK_SIZE`` (4096) bytes each.

    For a single frame this produces ``NUM_CHUNKS`` (16) chunks.
    For multiple frames the chunk count scales with the data size.
    Unused trailing bytes in the last chunk are padded with 0xFF.
    """
    # Build header
    header = bytearray(HEADER_SIZE)
    header[0] = frame_count
    header[1:] = b"\xFF" * (HEADER_SIZE - 1)

    payload = bytes(header) + pixel_data

    # Calculate chunks needed (ceil division)
    num_chunks = -(-len(payload) // CHUNK_SIZE)

    # Pad to fill all chunks
    total = num_chunks * CHUNK_SIZE
    padded = payload + b"\xFF" * (total - len(payload))

    return [padded[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE] for i in range(num_chunks)]


def render_to_chunks(img: Image.Image) -> list[bytes]:
    """Convenience: convert a single image to RGB565 and return wire-ready chunks."""
    return rgb565_to_chunks(image_to_rgb565(img))


def render_frames_to_chunks(frames: list[Image.Image]) -> list[bytes]:
    """Convert multiple animation frames to RGB565 and return wire-ready chunks."""
    pixel_data = b"".join(image_to_rgb565(f) for f in frames)
    return rgb565_to_chunks(pixel_data, frame_count=len(frames))
