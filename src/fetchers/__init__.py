"""Fetchers module - Media fetching with Strategy pattern."""

from .base import BaseFetcher
from .factory import MediaFetcher, FetcherFactory
from .registry import FetcherRegistry
from .audio import AudioFetcher
from .images import ImageFetcher

# Register fetchers with factory (legacy support)
FetcherFactory.register_class(ImageFetcher, "pollinations", "image")
FetcherFactory.register_class(AudioFetcher, "edge_tts", "audio")

__all__ = [
    'BaseFetcher',
    'MediaFetcher',
    'FetcherFactory',
    'FetcherRegistry',
    'AudioFetcher',
    'ImageFetcher'
]
