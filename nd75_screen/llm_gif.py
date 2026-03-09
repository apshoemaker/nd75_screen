"""Generate ND75-sized animated GIFs from a natural language prompt using Anthropic."""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass

from anthropic import Anthropic
from PIL import Image, ImageDraw

from nd75_screen import SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.renderer import frames_to_gif

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_FRAMES = 8

_SYSTEM_PROMPT = """You design tiny LCD animations for a 135x240 screen.
Return strict JSON only with this schema:
{
  "frames": [
    {
      "background": "#RRGGBB",
      "text": "short text",
      "x": 0,
      "y": 0,
      "color": "#RRGGBB"
    }
  ]
}
Rules:
- Produce 2-8 frames.
- Keep text short and legible.
- Coordinates must stay on-screen.
- No markdown fences, no explanations, JSON only.
"""


@dataclass
class FrameSpec:
    background: str
    text: str
    x: int
    y: int
    color: str = "#FFFFFF"


def build_anthropic_client(api_key: str | None) -> Anthropic:
    """Construct an Anthropic client using explicit key or environment variable."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    return Anthropic(api_key=key)


def _extract_text(response) -> str:
    text_parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_parts).strip()


def _parse_storyboard(raw: str) -> list[FrameSpec]:
    payload = json.loads(raw)
    frames = payload.get("frames", [])
    out: list[FrameSpec] = []
    for frame in frames:
        out.append(
            FrameSpec(
                background=frame.get("background", "#000000"),
                text=frame.get("text", ""),
                x=max(0, min(SCREEN_WIDTH - 1, int(frame.get("x", 0)))),
                y=max(0, min(SCREEN_HEIGHT - 1, int(frame.get("y", 0)))),
                color=frame.get("color", "#FFFFFF"),
            )
        )
    return out


def _render_frames(specs: list[FrameSpec]) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for spec in specs:
        img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), spec.background)
        draw = ImageDraw.Draw(img)
        draw.text((spec.x, spec.y), spec.text, fill=spec.color)
        frames.append(img)
    return frames


def generate_gif_bytes_from_prompt(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_frames: int = DEFAULT_FRAMES,
    client: Anthropic | None = None,
) -> bytes:
    """Generate an ND75-compatible animated GIF from a prompt."""
    anthropic_client = client or build_anthropic_client(None)
    response = anthropic_client.messages.create(
        model=model,
        max_tokens=800,
        temperature=0.7,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Create a playful animation in {max_frames} frames or fewer: {prompt}",
            }
        ],
    )
    storyboard = _parse_storyboard(_extract_text(response))
    if not storyboard:
        storyboard = [FrameSpec(background="#000000", text=prompt[:20], x=8, y=8)]

    frames = _render_frames(storyboard)
    out = io.BytesIO()
    frames_to_gif(frames, out)
    return out.getvalue()
