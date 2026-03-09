"""nd75-llm-gif — generate animated GIF bytes from a text prompt."""

from __future__ import annotations

import argparse
import sys

from nd75_screen.llm_gif import DEFAULT_MODEL, build_anthropic_client, generate_gif_bytes_from_prompt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nd75-llm-gif",
        description="Generate an ND75-ready animated GIF from a text prompt using Anthropic Sonnet.",
    )
    parser.add_argument("prompt", help="Description of the animation to generate")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (defaults to ANTHROPIC_API_KEY)")

    args = parser.parse_args(argv)

    client = build_anthropic_client(args.api_key)
    gif_data = generate_gif_bytes_from_prompt(args.prompt, model=args.model, client=client)
    sys.stdout.buffer.write(gif_data)


if __name__ == "__main__":
    main()
