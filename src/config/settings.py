"""Global settings and configuration."""

import os
import threading
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

# Default language when no settings are configured
_DEFAULT_LANG = "DE"

# Default sub-deck format (tokens: {year}, {month}, {month_name})
SUBDECK_FORMAT_DEFAULT = "{year}.{month} | {month_name}"


@dataclass
class Config:
    """Application-wide configuration."""
    
    settings = LANG_CONFIG.get(_DEFAULT_LANG, LANG_CONFIG["DE"])
    
    # Language parameters
    CURRENT_LANG: str = _DEFAULT_LANG
    MODEL_ID: int = settings["model_id"]
    DECK_ID: int = 2059400410
    
    # Generate deck name dynamically with current month and year
    @classmethod
    def _compute_deck_name(cls) -> str:
        """Compute deck name with current date. Called at reload time."""
        month_names = cls.settings.get("month_names", {})
        now = datetime.now()
        month_name = month_names.get(now.month, str(now.month))
        subdeck = SUBDECK_FORMAT_DEFAULT.format(
            year=now.year, month=f"{now.month:02d}", month_name=month_name
        )
        return f"{cls.settings['deck_name']}::{subdeck}"
    
    DECK_NAME: str = ""  # Set at reload time
    
    VOICE: str = settings["voice"]
    VOICE_ID: str = settings["voice_id"]
    LABEL: str = settings["label"]
    STRIP_REGEX: str = settings["strip_regex"]
    FORVO_CODE: str = settings["forvo_lang"]
    
    # Media fetch toggles (set at runtime by dashboard)
    FETCH_IMAGES: bool = True
    FETCH_AUDIO: bool = True
    
    # URLs & API Keys
    CONFETTI_URL: str = "https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"
    
    # Pollinations API Configuration
    # Get your API key from https://enter.pollinations.ai/
    # Store in environment variable or .env file: POLLINATIONS_API_KEY
    # NEVER hardcode secret keys in source code!
    POLLINATIONS_API_KEY: str = os.environ.get("POLLINATIONS_API_KEY", "")
    POLLINATIONS_API_URL: str = "https://gen.pollinations.ai/image"
    POLLINATIONS_IMAGE_MODEL: str = "flux"
    
    # Async settings
    CONCURRENCY: int = 4
    RETRIES: int = 5
    TIMEOUT: int = 60
    IMAGE_TIMEOUT: int = 90
    
    # Cross-platform paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent.resolve()
    
    # File paths (cross-platform compatible)
    MEDIA_DIR: str = str(BASE_DIR / "media")
    CSV_FILE: str = str(BASE_DIR / "vocabulary.csv")
    CACHE_DIR: str = str(BASE_DIR / "data" / "cache")
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "output")
    INPUT_DIR: str = str(BASE_DIR / "data" / "input")

    @classmethod
    def reload_from_settings(cls) -> None:
        """
        Reload all language-dependent Config fields from SettingsManager.
        
        Call this before each build to ensure Config reflects the latest
        saved settings without requiring an app restart.
        
        Thread-safe: uses a lock to prevent partial reads during reload.
        """
        if not hasattr(cls, '_reload_lock'):
            cls._reload_lock = threading.Lock()
        
        with cls._reload_lock:
            cls._reload_from_settings_unlocked()
    
    @classmethod
    def _reload_from_settings_unlocked(cls) -> None:
        """Internal reload logic (caller must hold _reload_lock)."""
        from .config_manager import SettingsManager
        sm = SettingsManager()
        sm.reload()
        
        lang = sm.get("CURRENT_LANG", "DE")
        lang_settings = LANG_CONFIG.get(lang, LANG_CONFIG["DE"])
        
        # Update class-level settings dict so AudioFetcher etc. see current language
        cls.settings = lang_settings
        
        cls.CURRENT_LANG = lang
        cls.MODEL_ID = lang_settings["model_id"]
        cls.DECK_ID = 2059400400 if lang == "EN" else 2059400410
        cls.VOICE = sm.get("VOICE", lang_settings["voice"])
        cls.VOICE_ID = lang_settings["voice_id"]
        cls.LABEL = lang_settings["label"]
        cls.STRIP_REGEX = lang_settings["strip_regex"]
        cls.FORVO_CODE = lang_settings["forvo_lang"]
        
        # Regenerate deck name with current month/year
        month_names = lang_settings["month_names"]
        now = datetime.now()
        month_name = month_names[now.month]
        
        # Custom deck name overrides language default
        custom_deck = sm.get("DECK_NAME", "")
        deck_base = custom_deck if custom_deck else lang_settings["deck_name"]
        
        # Custom sub-deck format overrides default
        custom_subdeck_fmt = sm.get("SUBDECK_FORMAT", "")
        subdeck_fmt = custom_subdeck_fmt if custom_subdeck_fmt else SUBDECK_FORMAT_DEFAULT
        try:
            subdeck = subdeck_fmt.format(
                year=now.year, month=f"{now.month:02d}", month_name=month_name
            )
        except (KeyError, ValueError):
            subdeck = SUBDECK_FORMAT_DEFAULT.format(
                year=now.year, month=f"{now.month:02d}", month_name=month_name
            )
        
        cls.DECK_NAME = f"{deck_base}::{subdeck}"
        
        # API & performance settings
        cls.POLLINATIONS_API_KEY = sm.get("POLLINATIONS_API_KEY", os.environ.get("POLLINATIONS_API_KEY", ""))
        cls.POLLINATIONS_API_URL = sm.get("POLLINATIONS_API_URL", cls.POLLINATIONS_API_URL)
        cls.POLLINATIONS_IMAGE_MODEL = sm.get("POLLINATIONS_IMAGE_MODEL", cls.POLLINATIONS_IMAGE_MODEL)
        cls.CONCURRENCY = sm.get("CONCURRENCY", cls.CONCURRENCY)
        cls.RETRIES = sm.get("RETRIES", cls.RETRIES)
        cls.TIMEOUT = sm.get("TIMEOUT", cls.TIMEOUT)
        cls.IMAGE_TIMEOUT = sm.get("IMAGE_TIMEOUT", cls.IMAGE_TIMEOUT)
        cls.FETCH_IMAGES = sm.get("FETCH_IMAGES", True)
        cls.FETCH_AUDIO = sm.get("FETCH_AUDIO", True)
