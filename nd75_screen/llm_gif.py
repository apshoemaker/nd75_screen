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
    f"You create JSON drawing commands for a tiny {SCREEN_WIDTH}x{SCREEN_HEIGHT} keyboard LCD. "
    "Return RAW JSON only — no code fences, no prose. Shape:\n"
    '{"frames": [{"bg": [r,g,b], "shapes": [...]}]}\n'
    "Shape types: rect, ellipse, line, text. Each has xy:[x1,y1,x2,y2], fill:[r,g,b]. "
    "Lines have width:N. Text has text:str and xy:[x,y].\n"
    "Return 2-4 frames. Keep each frame to 5-10 shapes MAX. Use vivid colors. "
    f"All coords must fit {SCREEN_WIDTH}x{SCREEN_HEIGHT}. Be concise."
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


def _parse_storyboard(raw: str) -> list[dict]:
    payload = _extract_json_payload(raw)

    frames: list = []
    if isinstance(payload, dict):
        # Try "frames" key first, then fall back to any list-valued key
        frames = payload.get("frames", [])
        if not frames:
            for v in payload.values():
                if isinstance(v, list) and v:
                    frames = v
                    break
        # If the dict itself looks like a single frame (has "bg" or "shapes"), wrap it
        if not frames and ("bg" in payload or "shapes" in payload):
            frames = [payload]
    elif isinstance(payload, list):
        frames = payload
    else:
        raise ValueError("Storyboard JSON must be an object or array")

    if not frames:
        raise ValueError(
            f"Storyboard JSON must contain at least one frame. Got: {raw[:300]}"
        )

    cleaned: list[dict] = []
    for frame in frames[:8]:
        if isinstance(frame, str):
            # Legacy text-only format: render as text on dark background
            cleaned.append({"bg": [8, 8, 20], "shapes": [
                {"type": "text", "xy": [8, 12], "text": frame[:120], "fill": [210, 245, 255]},
            ]})
        elif isinstance(frame, dict):
            cleaned.append(frame)
        else:
            continue
    if not cleaned:
        raise ValueError("Storyboard JSON must contain at least one frame")
    return cleaned


def _to_tuple(val: Any) -> tuple:
    """Convert a list/tuple to a tuple, for use as Pillow color/coord args."""
    if isinstance(val, (list, tuple)):
        return tuple(int(v) for v in val)
    return val


def _render_frame(frame: dict) -> Image.Image:
    bg = _to_tuple(frame.get("bg", [0, 0, 0]))
    image = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), bg)
    draw = ImageDraw.Draw(image)

    for shape in frame.get("shapes", []):
        stype = shape.get("type", "")
        xy = _to_tuple(shape.get("xy", [0, 0, 0, 0]))
        fill = _to_tuple(shape.get("fill", [255, 255, 255]))

        if stype == "rect":
            draw.rectangle(xy, fill=fill)
        elif stype == "ellipse":
            draw.ellipse(xy, fill=fill)
        elif stype == "line":
            width = int(shape.get("width", 1))
            draw.line(xy, fill=fill, width=width)
        elif stype == "text":
            draw.text(xy[:2] if len(xy) > 2 else xy, shape.get("text", ""), fill=fill)

    return image


def generate_gif_bytes_from_prompt(prompt: str, model: str = DEFAULT_MODEL, client: Any = None) -> bytes:
    """Generate an animated GIF from *prompt* using an Anthropic client."""
    if client is None:
        from anthropic import Anthropic

        client = Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    storyboard = _parse_storyboard(_extract_text(response))
    frames = [_render_frame(frame_text) for frame_text in storyboard]

    buf = io.BytesIO()
    frames_to_gif(frames, buf)
    return buf.getvalue()
