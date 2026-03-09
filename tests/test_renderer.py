"""Tests for nd75_screen.renderer — RGB565 conversion and chunking."""

import io

import pytest
from PIL import Image

from nd75_screen import (
    CHUNK_SIZE,
    FRAME_SIZE,
    HEADER_SIZE,
    NUM_CHUNKS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from nd75_screen.renderer import (
    image_to_rgb565,
    frames_to_gif,
    read_frames,
    render_to_chunks,
    rgb565_to_chunks,
    render_frames_to_chunks,
)


# ---- RGB565 known-value tests ----


def test_pure_red_rgb565():
    """Pure red (255,0,0) -> 0xF800 LE -> [0x00, 0xF8]."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (255, 0, 0))
    data = image_to_rgb565(img)
    assert data[0] == 0x00
    assert data[1] == 0xF8


def test_pure_green_rgb565():
    """Pure green (0,255,0) -> 0x07E0 LE -> [0xE0, 0x07]."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 255, 0))
    data = image_to_rgb565(img)
    assert data[0] == 0xE0
    assert data[1] == 0x07


def test_pure_blue_rgb565():
    """Pure blue (0,0,255) -> 0x001F LE -> [0x1F, 0x00]."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 0, 255))
    data = image_to_rgb565(img)
    assert data[0] == 0x1F
    assert data[1] == 0x00


# ---- Output size ----


def test_output_length_exact():
    """Output must be exactly 64,800 bytes (135 * 240 * 2)."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 0, 0))
    data = image_to_rgb565(img)
    assert len(data) == FRAME_SIZE


def test_output_length_for_oversized_input():
    """Any input image should be resized; output is still 64,800 bytes."""
    img = Image.new("RGB", (800, 600), (128, 128, 128))
    data = image_to_rgb565(img)
    assert len(data) == FRAME_SIZE


def test_output_length_for_undersized_input():
    """Small images are also resized to 135x240."""
    img = Image.new("RGB", (10, 10), (64, 64, 64))
    data = image_to_rgb565(img)
    assert len(data) == FRAME_SIZE


# ---- Resize behaviour ----


def test_image_resized_to_screen_dimensions():
    """image_to_rgb565 must resize to 135x240 regardless of input."""
    img = Image.new("RGB", (500, 500), (0, 0, 0))
    data = image_to_rgb565(img)
    # Correct pixel count implies correct resize
    assert len(data) == SCREEN_WIDTH * SCREEN_HEIGHT * 2


# ---- Chunking ----


def test_chunk_count_is_16():
    """rgb565_to_chunks must return exactly 16 chunks."""
    pixel_data = b"\x00" * FRAME_SIZE
    chunks = rgb565_to_chunks(pixel_data)
    assert len(chunks) == NUM_CHUNKS


def test_each_chunk_is_4096_bytes():
    """Every chunk must be exactly 4096 bytes."""
    pixel_data = b"\x00" * FRAME_SIZE
    chunks = rgb565_to_chunks(pixel_data)
    for i, chunk in enumerate(chunks):
        assert len(chunk) == CHUNK_SIZE, f"Chunk {i} has length {len(chunk)}"


def test_chunk0_header_byte0_is_frame_count():
    """Chunk 0, byte 0 must be the frame_count (default 1)."""
    pixel_data = b"\x00" * FRAME_SIZE
    chunks = rgb565_to_chunks(pixel_data)
    assert chunks[0][0] == 1


def test_chunk0_header_bytes_1_to_255_are_0xff():
    """Chunk 0, bytes 1..255 must all be 0xFF."""
    pixel_data = b"\x00" * FRAME_SIZE
    chunks = rgb565_to_chunks(pixel_data)
    assert chunks[0][1:HEADER_SIZE] == b"\xFF" * (HEADER_SIZE - 1)


def test_pixel_data_starts_at_chunk0_byte_256():
    """First pixel byte should appear at chunk 0, offset 256."""
    pixel_data = bytes(range(256)) * (FRAME_SIZE // 256)  # recognizable pattern
    pixel_data = pixel_data[:FRAME_SIZE]
    chunks = rgb565_to_chunks(pixel_data)
    assert chunks[0][HEADER_SIZE] == pixel_data[0]
    assert chunks[0][HEADER_SIZE + 1] == pixel_data[1]


def test_last_chunk_padded_with_0xff():
    """Unused trailing bytes in the last chunk must be 0xFF."""
    pixel_data = b"\x00" * FRAME_SIZE
    chunks = rgb565_to_chunks(pixel_data)
    last = chunks[-1]
    # Total payload = HEADER_SIZE + FRAME_SIZE = 256 + 64800 = 65056
    # 16 chunks * 4096 = 65536 total capacity
    # Padding = 65536 - 65056 = 480 bytes at end of last chunk
    total_payload = HEADER_SIZE + FRAME_SIZE
    used_in_last = total_payload - (NUM_CHUNKS - 1) * CHUNK_SIZE
    assert last[used_in_last:] == b"\xFF" * (CHUNK_SIZE - used_in_last)


# ---- Convenience wrapper ----


def test_render_to_chunks_returns_16_chunks():
    """render_to_chunks should produce 16 chunks of 4096 bytes."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (255, 255, 255))
    chunks = render_to_chunks(img)
    assert len(chunks) == NUM_CHUNKS
    for chunk in chunks:
        assert len(chunk) == CHUNK_SIZE


# ---- Multi-frame ----


def test_multi_frame_chunk_count_scales():
    """Multiple frames should produce more chunks than a single frame."""
    pixel_data = b"\x00" * (FRAME_SIZE * 4)
    chunks = rgb565_to_chunks(pixel_data, frame_count=4)
    expected = -(-((HEADER_SIZE + FRAME_SIZE * 4)) // CHUNK_SIZE)
    assert len(chunks) == expected
    for chunk in chunks:
        assert len(chunk) == CHUNK_SIZE


def test_multi_frame_header_has_correct_count():
    """Header byte[0] should reflect the frame count."""
    pixel_data = b"\x00" * (FRAME_SIZE * 8)
    chunks = rgb565_to_chunks(pixel_data, frame_count=8)
    assert chunks[0][0] == 8


def test_render_frames_to_chunks():
    """render_frames_to_chunks packs multiple images into wire chunks."""
    frames = [Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (i * 30, 0, 0)) for i in range(4)]
    chunks = render_frames_to_chunks(frames)
    # Header byte should be 4
    assert chunks[0][0] == 4
    # All chunks should be 4096 bytes
    for chunk in chunks:
        assert len(chunk) == CHUNK_SIZE


# ---- GIF helpers ----


def test_frames_to_gif_produces_valid_gif():
    """Encoding frames should produce data with GIF magic bytes that PIL can reopen."""
    frames = [Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (i * 60, 0, 0)) for i in range(4)]
    buf = io.BytesIO()
    frames_to_gif(frames, buf)
    data = buf.getvalue()
    assert data[:4] == b"GIF8"
    # PIL should be able to reopen it
    buf.seek(0)
    img = Image.open(buf)
    assert img.n_frames == 4


def test_read_frames_gif_roundtrip():
    """Encode frames to GIF, decode back, verify count and dimensions."""
    original = [Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (i * 30, 0, 0)) for i in range(6)]
    buf = io.BytesIO()
    frames_to_gif(original, buf)
    buf.seek(0)
    decoded = read_frames(buf)
    assert len(decoded) == 6
    for frame in decoded:
        assert frame.size == (SCREEN_WIDTH, SCREEN_HEIGHT)
        assert frame.mode == "RGB"


def test_read_frames_single_png():
    """A single PNG should return a list with one RGB frame."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    frames = read_frames(buf)
    assert len(frames) == 1
    assert frames[0].size == (SCREEN_WIDTH, SCREEN_HEIGHT)
    assert frames[0].mode == "RGB"
