"""Tests for nd75_screen.cli.push — device push CLI."""

import io

from PIL import Image
from unittest.mock import MagicMock, patch

from nd75_screen import CHUNK_SIZE, NUM_CHUNKS, SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.cli.push import main
from nd75_screen.renderer import frames_to_gif


def _png_bytes():
    """Create a 135x240 PNG as bytes."""
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _gif_bytes(num_frames=4):
    """Create a multi-frame GIF as bytes."""
    frames = [
        Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (i * 50, 0, 0))
        for i in range(num_frames)
    ]
    buf = io.BytesIO()
    frames_to_gif(frames, buf)
    return buf.getvalue()


def _mock_device():
    dev = MagicMock()
    dev.__enter__ = MagicMock(return_value=dev)
    dev.__exit__ = MagicMock(return_value=False)
    return dev


@patch("nd75_screen.cli.push.ND75Device")
def test_push_reads_png_from_stdin(MockDevice):
    """Piping a PNG should call upload_image with 16 chunks."""
    dev = _mock_device()
    MockDevice.return_value = dev

    png_data = _png_bytes()
    stdin_buf = io.BytesIO(png_data)

    with patch("nd75_screen.cli.push.sys") as mock_sys:
        mock_sys.stdin.isatty = MagicMock(return_value=False)
        mock_sys.stdin.buffer = stdin_buf
        mock_sys.stderr = io.StringIO()
        main([])

    dev.upload_image.assert_called_once()
    chunks = dev.upload_image.call_args[0][0]
    assert len(chunks) == NUM_CHUNKS
    for chunk in chunks:
        assert len(chunk) == CHUNK_SIZE


@patch("nd75_screen.cli.push.ND75Device")
def test_push_reads_gif_from_stdin(MockDevice):
    """Piping a 4-frame GIF should produce more chunks than a single frame."""
    dev = _mock_device()
    MockDevice.return_value = dev

    gif_data = _gif_bytes(4)
    stdin_buf = io.BytesIO(gif_data)

    with patch("nd75_screen.cli.push.sys") as mock_sys:
        mock_sys.stdin.isatty = MagicMock(return_value=False)
        mock_sys.stdin.buffer = stdin_buf
        mock_sys.stderr = io.StringIO()
        main([])

    dev.upload_image.assert_called_once()
    chunks = dev.upload_image.call_args[0][0]
    assert len(chunks) > NUM_CHUNKS
    assert chunks[0][0] == 4  # header frame count


@patch("nd75_screen.cli.push.ND75Device")
def test_push_reads_file_arg(MockDevice, tmp_path):
    """Passing a file path should read from that file."""
    dev = _mock_device()
    MockDevice.return_value = dev

    png_file = tmp_path / "test.png"
    png_file.write_bytes(_png_bytes())

    main([str(png_file)])

    dev.upload_image.assert_called_once()
    chunks = dev.upload_image.call_args[0][0]
    assert len(chunks) == NUM_CHUNKS


@patch("nd75_screen.cli.push.ND75Device")
def test_push_with_sync_time(MockDevice):
    """--sync-time should call device.sync_time() before upload."""
    dev = _mock_device()
    MockDevice.return_value = dev

    png_data = _png_bytes()
    stdin_buf = io.BytesIO(png_data)

    with patch("nd75_screen.cli.push.sys") as mock_sys:
        mock_sys.stdin.isatty = MagicMock(return_value=False)
        mock_sys.stdin.buffer = stdin_buf
        mock_sys.stderr = io.StringIO()
        main(["--sync-time"])

    dev.sync_time.assert_called_once()
    dev.upload_image.assert_called_once()


@patch("nd75_screen.cli.push.sys")
def test_push_shows_usage_on_tty(mock_sys):
    """No stdin and no file arg should exit with usage message."""
    mock_sys.stdin.isatty = MagicMock(return_value=True)
    mock_sys.stderr = io.StringIO()
    mock_sys.exit = MagicMock(side_effect=SystemExit(1))

    try:
        main([])
        assert False, "Should have called sys.exit"
    except SystemExit as e:
        assert e.code == 1

    mock_sys.exit.assert_called_once_with(1)
