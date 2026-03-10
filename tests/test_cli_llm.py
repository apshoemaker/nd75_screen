"""Tests for nd75_screen.cli.llm."""

import io
from unittest.mock import patch

from nd75_screen.cli.llm import main


def test_cli_llm_writes_gif_to_stdout():
    """CLI should write generated GIF bytes to stdout.buffer."""
    out = io.BytesIO()

    with patch("nd75_screen.cli.llm.generate_gif_bytes_from_prompt", return_value=b"GIF89aDATA") as mock_gen:
        with patch("nd75_screen.cli.llm.sys") as mock_sys:
            mock_sys.stdout.buffer = out
            main(["neon synthwave sunset over a city"])

    assert out.getvalue() == b"GIF89aDATA"
    mock_gen.assert_called_once()


def test_cli_llm_uses_anthropic_client_and_model_override():
    """CLI should create an Anthropic client and pass --model to generation."""
    with patch("nd75_screen.cli.llm.Anthropic") as mock_anthropic:
        with patch("nd75_screen.cli.llm.generate_gif_bytes_from_prompt", return_value=b"GIF89a") as mock_gen:
            with patch("nd75_screen.cli.llm.sys") as mock_sys:
                mock_sys.stdout.buffer = io.BytesIO()
                main(["sunset", "--model", "claude-custom"]) 

    mock_anthropic.assert_called_once()
    assert mock_gen.call_args.kwargs["model"] == "claude-custom"
