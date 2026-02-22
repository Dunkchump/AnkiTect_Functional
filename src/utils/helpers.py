"""Utility functions.

Note: clean_text_for_display and format_analogues_html delegate to
TextParser (src.utils.parsing) which is the canonical source.
These wrappers are kept for backward compatibility.
"""

from pathlib import Path

from .parsing import TextParser


def clean_text_for_display(text: str) -> str:
    """Clean translation text for card display. Delegates to TextParser.clean_for_display()."""
    return TextParser.clean_for_display(text)


def format_analogues_html(text: str) -> str:
    """Format analogues table from text. Delegates to TextParser.format_analogues_html()."""
    return TextParser.format_analogues_html(text)


def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_file_size_mb(path: str) -> float:
    """Get file size in megabytes."""
    if not Path(path).exists():
        return 0.0
    return Path(path).stat().st_size / (1024 * 1024)
