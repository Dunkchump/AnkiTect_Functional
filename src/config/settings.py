"""Global settings and configuration."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load from project root
    _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly

from .languages import LANG_CONFIG

# Поточна обрана мова
CURRENT_LANG = "DE"  # Options: "DE", "EN"


@dataclass
class Config:
    """Application-wide configuration."""
    
    settings = LANG_CONFIG.get(CURRENT_LANG, LANG_CONFIG["DE"])
    
    # Мовні параметри
    CURRENT_LANG: str = CURRENT_LANG
    MODEL_ID: int = settings["model_id"]
    DECK_ID: int = 2059400400 if CURRENT_LANG == "EN" else 2059400410
    
    # Generate deck name dynamically with month and year
    _month_names = settings["month_names"]
    _current_month = datetime.now().month
    _current_year = datetime.now().year
    _month_name = _month_names[_current_month]
    DECK_NAME: str = f"{settings['deck_name']}::{_current_year}.{_current_month:02d} | {_month_name}"
    
    VOICE: str = settings["voice"]
    VOICE_ID: str = settings["voice_id"]
    LABEL: str = settings["label"]
    STRIP_REGEX: str = settings["strip_regex"]
    FORVO_CODE: str = settings["forvo_lang"]
    
    # URLs & API Keys
    CONFETTI_URL: str = "https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"
    
    # Pollinations API Configuration
    # Get your API key from https://enter.pollinations.ai/
    # Store in environment variable or .env file: POLLINATIONS_API_KEY
    # NEVER hardcode secret keys in source code!
    POLLINATIONS_API_KEY: str = os.environ.get("POLLINATIONS_API_KEY", "")
    POLLINATIONS_API_URL: str = "https://gen.pollinations.ai/image"
    POLLINATIONS_IMAGE_MODEL: str = "zimage"  # Options: zimage, flux, turbo, gptimage, seedream, nanobanana
    
    # Асинхронні налаштування
    CONCURRENCY: int = 4
    RETRIES: int = 5
    TIMEOUT: int = 60
    IMAGE_TIMEOUT: int = 90
    
    # Cross-platform paths using pathlib
    # BASE_DIR is the project root (parent of src/)
    BASE_DIR: Path = Path(__file__).parent.parent.parent.resolve()
    
    # Шляхи до файлів (cross-platform compatible)
    MEDIA_DIR: str = str(BASE_DIR / "media")
    CSV_FILE: str = str(BASE_DIR / "vocabulary.csv")
    CACHE_DIR: str = str(BASE_DIR / "data" / "cache")
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "output")
    INPUT_DIR: str = str(BASE_DIR / "data" / "input")
