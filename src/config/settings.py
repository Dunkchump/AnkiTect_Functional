"""Global settings and configuration."""

from dataclasses import dataclass
from datetime import datetime
from .languages import LANG_CONFIG

# Поточна обрана мова
CURRENT_LANG = "EN"


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
    
    # URLs
    CONFETTI_URL: str = "https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"
    
    # Асинхронні налаштування
    CONCURRENCY: int = 4
    RETRIES: int = 5
    TIMEOUT: int = 60
    IMAGE_TIMEOUT: int = 90
    REQUEST_DELAY_MIN: float = 0.5
    REQUEST_DELAY_MAX: float = 3.5
    
    # Шляхи до файлів
    MEDIA_DIR: str = "media"
    CSV_FILE: str = "vocabulary.csv"
    CACHE_DIR: str = "data/cache"
    OUTPUT_DIR: str = "data/output"
    INPUT_DIR: str = "data/input"
