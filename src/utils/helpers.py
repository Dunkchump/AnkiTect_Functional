"""Utility functions."""

import re
from pathlib import Path
from typing import Optional


def clean_text_for_display(text: str) -> str:
    """Clean translation text for card display."""
    if not text:
        return ""
    
    lines = re.split(r'(<br>|\n)', str(text))
    cleaned_lines = []
    
    for line in lines:
        if line in ['<br>', '\n']:
            cleaned_lines.append(line)
        else:
            cleaned_lines.append(re.sub(r'^\s*\d+[\.\)]\s*', '', line))
    
    return "".join(cleaned_lines)


def format_analogues_html(text: str) -> str:
    """Format analogues table from text."""
    if not text or str(text).lower() == 'nan':
        return ""
    
    lines = re.split(r'\n|<br\s*/?>', str(text))
    html_out = '<table class="analogues-table">'
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(':', 1)
        if len(parts) == 2:
            code = parts[0].strip()
            word = parts[1].strip()
            html_out += f'<tr class="ana-row"><td class="ana-lang">{code}</td><td class="ana-word">{word}</td></tr>'
        else:
            html_out += f'<tr class="ana-row"><td colspan="2" class="ana-word">{line}</td></tr>'
    
    html_out += '</table>'
    return html_out


def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_file_size_mb(path: str) -> float:
    """Get file size in megabytes."""
    if not Path(path).exists():
        return 0.0
    return Path(path).stat().st_size / (1024 * 1024)
