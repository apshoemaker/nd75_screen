"""Tests for nd75_screen.llm_gif."""

import io
from types import SimpleNamespace

import pytest

from nd75_screen import SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.renderer import read_frames


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def test_generate_gif_parses_fenced_json_with_prose():
    """LLM responses wrapped in prose/code fences should still parse."""
    from nd75_screen.llm_gif import generate_gif_bytes_from_prompt

    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text=(
                    "Here you go!\n```json\n"
                    '{"frames": ['
                    '{"bg":[0,0,40],"shapes":[{"type":"rect","xy":[0,200,135,240],"fill":[255,80,180]}]},'
                    '{"bg":[20,0,60],"shapes":[{"type":"ellipse","xy":[40,30,95,85],"fill":[255,200,0]}]}'
                    "]}\n```"
                ),
            )
        ]
    )
    client = _FakeClient(response)

    gif_data = generate_gif_bytes_from_prompt("synthwave", client=client)

    assert gif_data[:4] == b"GIF8"
    frames = read_frames(io.BytesIO(gif_data))
    assert len(frames) == 2
    assert frames[0].size == (SCREEN_WIDTH, SCREEN_HEIGHT)


def test_generate_gif_uses_first_available_text_block():
    """Non-text blocks before text should be ignored when extracting storyboard JSON."""
    from nd75_screen.llm_gif import generate_gif_bytes_from_prompt

    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", text="internal"),
            SimpleNamespace(
                type="text",
                text='{"frames": [{"bg":[0,0,0],"shapes":[{"type":"rect","xy":[0,0,135,240],"fill":[255,0,0]}]}]}',
            ),
        ]
    )
    client = _FakeClient(response)

    gif_data = generate_gif_bytes_from_prompt("city", client=client)

    assert gif_data[:4] == b"GIF8"
    assert client.messages.calls[0]["model"] == "claude-3-7-sonnet-latest"


def test_generate_gif_raises_for_missing_json_payload():
    """Non-JSON text should raise a clear ValueError instead of raw JSONDecodeError."""
    from nd75_screen.llm_gif import generate_gif_bytes_from_prompt

    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="not json")])
    client = _FakeClient(response)

    with pytest.raises(ValueError, match="JSON"):
        generate_gif_bytes_from_prompt("city", client=client)
