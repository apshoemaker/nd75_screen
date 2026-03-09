"""nd75-llm-gif — generate animated GIF from a natural language prompt."""

from __future__ import annotations

import argparse
import os
import sys

from anthropic import Anthropic

from nd75_screen.llm_gif import DEFAULT_MODEL, generate_gif_bytes_from_prompt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nd75-llm-gif",
        description="Generate an animated GIF via Anthropic and write it to stdout.",
    )
    parser.add_argument("prompt", help="Natural language prompt for the animation")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model (default: {DEFAULT_MODEL})")
    args = parser.parse_args(argv)

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    gif_data = generate_gif_bytes_from_prompt(args.prompt, model=args.model, client=client)
    sys.stdout.buffer.write(gif_data)


if __name__ == "__main__":
    main()
