"""Tests for nd75_screen.cli.llm — LLM GIF producer CLI."""

import io
from unittest.mock import patch

from nd75_screen import SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.renderer import read_frames


def test_llm_outputs_gif_to_stdout():
    """CLI should write GIF bytes from generated frames to stdout."""
    from nd75_screen.cli.llm import main

    buf = io.BytesIO()
    with patch("nd75_screen.cli.llm.generate_gif_bytes_from_prompt", return_value=b"GIF89a..."), patch(
        "nd75_screen.cli.llm.sys"
    ) as mock_sys:
        mock_sys.stdout.buffer = buf
        main(["a cat dancing"])  # positional prompt

    assert buf.getvalue() == b"GIF89a..."


def test_llm_uses_default_model_and_renders_valid_gif():
    """generate_gif_bytes_from_prompt should call Sonnet model and return ND75-sized GIF."""
    from nd75_screen.llm_gif import DEFAULT_MODEL, generate_gif_bytes_from_prompt

    storyboard = (
        '{"frames":[{"background":"#000000","text":"HI","x":8,"y":8},'
        '{"background":"#222244","text":"THERE","x":8,"y":24}]}'
    )

    class _Messages:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return type("Resp", (), {"content": [type("Blk", (), {"type": "text", "text": storyboard})()]})()

    class _Client:
        def __init__(self):
            self.messages = _Messages()

    client = _Client()
    gif_data = generate_gif_bytes_from_prompt("hello", client=client)

    assert client.messages.kwargs["model"] == DEFAULT_MODEL

    frames = read_frames(io.BytesIO(gif_data))
    assert len(frames) == 2
    assert frames[0].size == (SCREEN_WIDTH, SCREEN_HEIGHT)


def test_llm_reads_api_key_from_env(monkeypatch):
    """build_anthropic_client should read ANTHROPIC_API_KEY from environment."""
    from nd75_screen.llm_gif import build_anthropic_client

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with patch("nd75_screen.llm_gif.Anthropic") as mock_anthropic:
        build_anthropic_client(None)

    mock_anthropic.assert_called_once_with(api_key="test-key")
