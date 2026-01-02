"""AnkiTect - Intelligent Anki Deck Generator"""

__version__ = "2.0.0"
__author__ = "AnkiTect Team"

from .deck import AnkiDeckBuilder, CacheManager
from .config import Config, LANG_CONFIG
from .models import CardData
from .templates import CardTemplates
from .fetchers import AudioFetcher, ImageFetcher

__all__ = [
    'AnkiDeckBuilder',
    'CacheManager',
    'Config',
    'LANG_CONFIG',
    'CardData',
    'CardTemplates',
    'AudioFetcher',
    'ImageFetcher',
]
