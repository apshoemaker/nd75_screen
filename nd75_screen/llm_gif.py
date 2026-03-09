"""Generate ND75-ready animated GIFs from text prompts via Anthropic."""

from __future__ import annotations

import io
import json
from typing import Any

from PIL import Image, ImageDraw

from nd75_screen import SCREEN_HEIGHT, SCREEN_WIDTH
from nd75_screen.renderer import frames_to_gif

DEFAULT_MODEL = "claude-3-7-sonnet-latest"

SYSTEM_PROMPT = (
    "You create concise storyboard JSON for tiny keyboard LCD animations. "
    "Respond with JSON only using this shape: "
    '{"frames": ["frame description", "frame description"]}. '
    "Return 1-8 short frame descriptions."
)


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        if isinstance(block, dict):
            if block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
        else:
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                parts.append(block.text)
    return "\n".join(parts).strip()


def _extract_json_payload(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ValueError("LLM response did not contain JSON text")

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text, i)
            return payload
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not find valid JSON payload in LLM response text")


def _parse_storyboard(raw: str) -> list[str]:
    payload = _extract_json_payload(raw)

    if isinstance(payload, dict):
        frames = payload.get("frames", [])
    elif isinstance(payload, list):
        frames = payload
    else:
        raise ValueError("Storyboard JSON must be an object or array")

    cleaned = [str(frame).strip() for frame in frames if str(frame).strip()]
    if not cleaned:
        raise ValueError("Storyboard JSON must contain at least one frame")
    return cleaned[:8]


def _render_frame(text: str) -> Image.Image:
    image = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (8, 8, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1), outline=(255, 80, 180), width=2)
    draw.text((8, 12), text[:120], fill=(210, 245, 255))
    return image


def generate_gif_bytes_from_prompt(prompt: str, model: str = DEFAULT_MODEL, client: Any = None) -> bytes:
    """Generate an animated GIF from *prompt* using an Anthropic client."""
    if client is None:
        from anthropic import Anthropic

        client = Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=600,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    storyboard = _parse_storyboard(_extract_text(response))
    frames = [_render_frame(frame_text) for frame_text in storyboard]

    buf = io.BytesIO()
    frames_to_gif(frames, buf)
    return buf.getvalue()
