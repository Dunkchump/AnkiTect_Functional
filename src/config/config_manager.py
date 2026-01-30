"""Persistent settings manager with JSON storage and environment fallback."""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass


class SettingsManager:
    """
    Manages application settings with JSON persistence.
    
    Settings are loaded from a JSON file with fallback to environment variables.
    Changes are immediately persisted to disk.
    
    Usage:
        settings = SettingsManager()
        api_key = settings.get("POLLINATIONS_API_KEY", "")
        settings.set("CONCURRENCY", 8)
    """
    
    _instance: Optional["SettingsManager"] = None
    _lock: Lock = Lock()
    
    DEFAULT_SETTINGS_FILE: str = "settings.json"
    
    # Default values for all settings
    # NOTE: API keys should come from environment variables, not defaults!
    DEFAULTS: Dict[str, Any] = {
        # Language settings
        "CURRENT_LANG": "DE",
        
        # API Configuration - key loaded from environment
        "POLLINATIONS_API_KEY": os.environ.get("POLLINATIONS_API_KEY", ""),
        "POLLINATIONS_API_URL": "https://gen.pollinations.ai/image",
        "POLLINATIONS_IMAGE_MODEL": "zimage",
        
        # Performance settings
        "CONCURRENCY": 4,
        "RETRIES": 5,
        "TIMEOUT": 60,
        "IMAGE_TIMEOUT": 90,
        "PERFORMANCE_MODE": False,
        
        # Paths
        "MEDIA_DIR": "media",
        "CSV_FILE": "vocabulary.csv",
        "CACHE_DIR": "data/cache",
        "OUTPUT_DIR": "data/output",
        "INPUT_DIR": "data/input",
        
        # Card Sections Configuration
        # Which sections are enabled (shown) on the card
        "CARD_SECTIONS_ENABLED": {
            "header": True,
            "meaning": True,
            "morphology": True,
            "context": True,
            "mnemonic": True,
            "analogues": True,
            "image": True,
            "footer": True,
            "tags": True,
        },
        # Order of sections on the card (top to bottom)
        "CARD_SECTIONS_ORDER": [
            "header",
            "meaning",
            "morphology",
            "context",
            "mnemonic",
            "analogues",
            "image",
            "footer",
            "tags",
        ],

        # Card Types Configuration
        "CARD_TYPES_ENABLED": {
            "recognition": True,
            "production": True,
            "listening": True,
            "context": True,
        },
        "CARD_TYPES_ORDER": [
            "recognition",
            "production",
            "listening",
            "context",
        ],

        # Card Style Configuration
        "CARD_STYLE": {
            "card_bg": "#f4f6f9",
            "container_bg": "#ffffff",
            "text_color": "#333333",
            "header_text": "#ffffff",
            "label_color": "#adb5bd",
            "definition_color": "#212529",
            "section_border": "#f2f2f2",
            "card_radius": "12px",
            "card_shadow": "0 2px 10px rgba(0,0,0,0.05)",

            "der_start": "#2980b9",
            "der_end": "#3498db",
            "die_start": "#c0392b",
            "die_end": "#e74c3c",
            "das_start": "#27ae60",
            "das_end": "#2ecc71",
            "none_start": "#8e44ad",
            "none_end": "#9b59b6",
            "en_start": "#2c3e50",
            "en_end": "#4ca1af",
        },
    }
    
    def __new__(cls, settings_file: Optional[str] = None) -> "SettingsManager":
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self, settings_file: Optional[str] = None) -> None:
        """
        Initialize the settings manager.
        
        Args:
            settings_file: Path to the settings JSON file.
                          Defaults to 'settings.json' in current directory.
        """
        if getattr(self, "_initialized", False):
            return
            
        self._settings_file: Path = Path(settings_file or self.DEFAULT_SETTINGS_FILE)
        self._settings: Dict[str, Any] = {}
        self._file_lock: Lock = Lock()
        
        self._load_settings()
        self._initialized = True
    
    def _load_settings(self) -> None:
        """Load settings from JSON file with environment variable fallback."""
        # Start with defaults
        self._settings = self.DEFAULTS.copy()
        
        # Load from file if exists
        if self._settings_file.exists():
            try:
                with open(self._settings_file, "r", encoding="utf-8") as f:
                    file_settings = json.load(f)
                    self._settings.update(file_settings)
            except (json.JSONDecodeError, IOError) as e:
                # Log error but continue with defaults
                print(f"Warning: Could not load settings file: {e}")
        
        # Override with environment variables (highest priority)
        for key in self.DEFAULTS:
            env_value = os.environ.get(key)
            if env_value is not None:
                self._settings[key] = self._parse_env_value(env_value, key)
        
        # Ensure file exists with current settings
        self._save_settings()
    
    def _parse_env_value(self, value: str, key: str) -> Any:
        """
        Parse environment variable value to appropriate type.
        
        Args:
            value: The string value from environment
            key: The setting key (used to infer expected type)
            
        Returns:
            Parsed value in appropriate type
        """
        default = self.DEFAULTS.get(key)
        
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes", "on")
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        else:
            return value
    
    def _save_settings(self) -> None:
        """Save current settings to JSON file."""
        with self._file_lock:
            try:
                # Ensure parent directory exists
                self._settings_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self._settings_file, "w", encoding="utf-8") as f:
                    json.dump(self._settings, f, indent=2, ensure_ascii=False)
            except IOError as e:
                print(f"Warning: Could not save settings file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Returns a deep copy for mutable objects (dict, list) to prevent
        accidental modification of internal state.
        
        Args:
            key: The setting key
            default: Default value if key not found
            
        Returns:
            The setting value (copy for mutable types), or default if not found
        """
        import copy
        value = self._settings.get(key, default)
        # Return deep copy for mutable types to prevent external modification
        if isinstance(value, (dict, list)):
            return copy.deepcopy(value)
        return value
    
    def set(self, key: str, value: Any, persist: bool = True) -> None:
        """
        Set a setting value and immediately persist to disk.
        
        Args:
            key: The setting key
            value: The value to set
        """
        self._settings[key] = value
        if persist:
            self._save_settings()
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get a copy of all current settings.
        
        Returns:
            Dictionary containing all settings
        """
        return self._settings.copy()
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset settings to defaults.
        
        Args:
            key: Specific key to reset. If None, resets all settings.
        """
        if key is not None:
            if key in self.DEFAULTS:
                self._settings[key] = self.DEFAULTS[key]
        else:
            self._settings = self.DEFAULTS.copy()
        
        self._save_settings()
    
    def reload(self) -> None:
        """Reload settings from disk."""
        self._load_settings()
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        with cls._lock:
            cls._instance = None
