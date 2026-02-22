"""Fetchers module - Media fetching with Strategy pattern."""

from .base import BaseFetcher
from .audio import AudioFetcher
from .images import ImageFetcher

__all__ = [
    'BaseFetcher',
    'AudioFetcher',
    'ImageFetcher',
]
