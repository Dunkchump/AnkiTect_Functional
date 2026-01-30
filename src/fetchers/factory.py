"""
Fetcher Factory - Strategy Pattern Implementation for Media Fetchers.

Provides a centralized factory for creating fetchers based on configuration,
enabling easy switching between different providers (Pollinations, DALL-E, etc.)
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Type


class MediaFetcher(ABC):
    """
    Abstract base class for all media fetchers.
    
    Implements the Strategy pattern - each fetcher is a different strategy
    for obtaining media (images, audio, etc.)
    """
    
    def __init__(self, concurrency_callback: Optional[Callable] = None):
        """
        Initialize the fetcher.
        
        Args:
            concurrency_callback: Function to call for adaptive concurrency adjustments
        """
        self.concurrency_callback = concurrency_callback
    
    @abstractmethod
    async def fetch(self, source: str, output_path: str, **kwargs) -> bool:
        """
        Fetch media from source to output_path.
        
        Args:
            source: Source identifier (URL, text for TTS, prompt for AI)
            output_path: Path to save the output file
            **kwargs: Additional fetcher-specific options
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Cleanup resources (connections, sessions, etc.)"""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure cleanup."""
        await self.close()
    
    def report_success(self, status_code: int = 200) -> None:
        """Report successful operation to concurrency callback."""
        if self.concurrency_callback:
            self.concurrency_callback(status_code=status_code, is_success=True)
    
    def report_failure(self, status_code: int = 0) -> None:
        """Report failed operation to concurrency callback."""
        if self.concurrency_callback:
            self.concurrency_callback(status_code=status_code, is_success=False)


class FetcherFactory:
    """
    Factory for creating fetchers based on configuration.
    
    Supports registration of custom fetchers for extensibility.
    
    Usage:
        # Register a fetcher
        @FetcherFactory.register("pollinations", "image")
        class PollinationsImageFetcher(MediaFetcher):
            ...
        
        # Create a fetcher
        fetcher = FetcherFactory.create("image", "pollinations")
    """
    
    # Registry: {media_type: {provider_name: fetcher_class}}
    _registry: Dict[str, Dict[str, Type[MediaFetcher]]] = {
        "image": {},
        "audio": {},
    }
    
    @classmethod
    def register(cls, provider: str, media_type: str = "image"):
        """
        Decorator to register a fetcher class.
        
        Args:
            provider: Provider name (e.g., "pollinations", "edge_tts")
            media_type: Type of media ("image" or "audio")
            
        Returns:
            Decorator function
        """
        def decorator(fetcher_cls: Type[MediaFetcher]) -> Type[MediaFetcher]:
            if media_type not in cls._registry:
                cls._registry[media_type] = {}
            cls._registry[media_type][provider] = fetcher_cls
            return fetcher_cls
        return decorator
    
    @classmethod
    def create(
        cls,
        media_type: str,
        provider: str,
        concurrency_callback: Optional[Callable] = None,
        **kwargs
    ) -> MediaFetcher:
        """
        Create a fetcher instance.
        
        Args:
            media_type: Type of media ("image" or "audio")
            provider: Provider name
            concurrency_callback: Optional callback for rate limiting
            **kwargs: Additional arguments for fetcher constructor
            
        Returns:
            Fetcher instance
            
        Raises:
            ValueError: If provider not found
        """
        if media_type not in cls._registry:
            raise ValueError(f"Unknown media type: {media_type}")
        
        if provider not in cls._registry[media_type]:
            available = list(cls._registry[media_type].keys())
            raise ValueError(
                f"Unknown {media_type} provider: {provider}. "
                f"Available: {available}"
            )
        
        fetcher_cls = cls._registry[media_type][provider]
        return fetcher_cls(concurrency_callback=concurrency_callback, **kwargs)
    
    @classmethod
    def get_available_providers(cls, media_type: str) -> list:
        """Get list of available providers for a media type."""
        return list(cls._registry.get(media_type, {}).keys())
    
    @classmethod
    def register_class(
        cls,
        fetcher_cls: Type[MediaFetcher],
        provider: str,
        media_type: str
    ) -> None:
        """
        Register a fetcher class programmatically (non-decorator).
        
        Args:
            fetcher_cls: The fetcher class to register
            provider: Provider name
            media_type: Media type
        """
        if media_type not in cls._registry:
            cls._registry[media_type] = {}
        cls._registry[media_type][provider] = fetcher_cls
