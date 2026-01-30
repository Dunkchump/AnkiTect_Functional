"""
Fetcher Registry - Strategy Pattern Implementation for Extensible Providers.

Enables runtime selection of image/audio providers without modifying core code.
Designed for plugin-style extensibility.
"""

from typing import Callable, Dict, Optional, Type

from .base import BaseFetcher


class FetcherRegistry:
    """
    Registry for image and audio fetchers using Strategy Pattern.
    
    Allows:
    - Registration of multiple providers (Pollinations, DALL-E, local SD, etc.)
    - Runtime provider selection
    - Plugin-style extensibility
    
    Usage:
        # Register a fetcher
        FetcherRegistry.register_image("pollinations", PollinationsImageFetcher)
        
        # Get a fetcher instance
        fetcher = FetcherRegistry.get_image_fetcher("pollinations")
    """
    
    _image_fetchers: Dict[str, Type[BaseFetcher]] = {}
    _audio_fetchers: Dict[str, Type[BaseFetcher]] = {}
    
    # Store factory functions for fetchers that need constructor args
    _image_factories: Dict[str, Callable[..., BaseFetcher]] = {}
    _audio_factories: Dict[str, Callable[..., BaseFetcher]] = {}
    
    # Default providers
    _default_image: str = "pollinations"
    _default_audio: str = "edge-tts"
    
    @classmethod
    def register_image(
        cls, 
        name: str, 
        fetcher_class: Type[BaseFetcher],
        factory: Optional[Callable[..., BaseFetcher]] = None,
        set_default: bool = False
    ) -> None:
        """
        Register an image fetcher provider.
        
        Args:
            name: Provider name (e.g., "pollinations", "dalle", "stable-diffusion")
            fetcher_class: Class implementing BaseFetcher
            factory: Optional factory function for custom instantiation
            set_default: If True, set this as the default provider
        """
        cls._image_fetchers[name] = fetcher_class
        if factory:
            cls._image_factories[name] = factory
        if set_default:
            cls._default_image = name
    
    @classmethod
    def register_audio(
        cls, 
        name: str, 
        fetcher_class: Type[BaseFetcher],
        factory: Optional[Callable[..., BaseFetcher]] = None,
        set_default: bool = False
    ) -> None:
        """
        Register an audio fetcher provider.
        
        Args:
            name: Provider name (e.g., "edge-tts", "google-tts", "piper")
            fetcher_class: Class implementing BaseFetcher
            factory: Optional factory function for custom instantiation
            set_default: If True, set this as the default provider
        """
        cls._audio_fetchers[name] = fetcher_class
        if factory:
            cls._audio_factories[name] = factory
        if set_default:
            cls._default_audio = name
    
    @classmethod
    def get_image_fetcher(
        cls, 
        name: Optional[str] = None,
        concurrency_callback: Optional[Callable] = None
    ) -> BaseFetcher:
        """
        Get an image fetcher instance.
        
        Args:
            name: Provider name (uses default if None)
            concurrency_callback: Callback for adaptive rate limiting
            
        Returns:
            Configured fetcher instance
            
        Raises:
            KeyError: If provider not found
        """
        provider = name or cls._default_image
        
        if provider not in cls._image_fetchers:
            available = list(cls._image_fetchers.keys())
            raise KeyError(f"Image provider '{provider}' not found. Available: {available}")
        
        # Use factory if available, otherwise direct instantiation
        if provider in cls._image_factories:
            return cls._image_factories[provider](concurrency_callback=concurrency_callback)
        
        fetcher_class = cls._image_fetchers[provider]
        return fetcher_class(concurrency_callback=concurrency_callback)
    
    @classmethod
    def get_audio_fetcher(
        cls, 
        name: Optional[str] = None,
        concurrency_callback: Optional[Callable] = None
    ) -> BaseFetcher:
        """
        Get an audio fetcher instance.
        
        Args:
            name: Provider name (uses default if None)
            concurrency_callback: Callback for adaptive rate limiting
            
        Returns:
            Configured fetcher instance
            
        Raises:
            KeyError: If provider not found
        """
        provider = name or cls._default_audio
        
        if provider not in cls._audio_fetchers:
            available = list(cls._audio_fetchers.keys())
            raise KeyError(f"Audio provider '{provider}' not found. Available: {available}")
        
        # Use factory if available, otherwise direct instantiation
        if provider in cls._audio_factories:
            return cls._audio_factories[provider](concurrency_callback=concurrency_callback)
        
        fetcher_class = cls._audio_fetchers[provider]
        return fetcher_class(concurrency_callback=concurrency_callback)
    
    @classmethod
    def list_image_providers(cls) -> list:
        """List all registered image providers."""
        return list(cls._image_fetchers.keys())
    
    @classmethod
    def list_audio_providers(cls) -> list:
        """List all registered audio providers."""
        return list(cls._audio_fetchers.keys())
    
    @classmethod
    def get_default_image_provider(cls) -> str:
        """Get the default image provider name."""
        return cls._default_image
    
    @classmethod
    def get_default_audio_provider(cls) -> str:
        """Get the default audio provider name."""
        return cls._default_audio
    
    @classmethod
    def set_default_image_provider(cls, name: str) -> None:
        """Set the default image provider."""
        if name not in cls._image_fetchers:
            raise KeyError(f"Image provider '{name}' not registered")
        cls._default_image = name
    
    @classmethod
    def set_default_audio_provider(cls, name: str) -> None:
        """Set the default audio provider."""
        if name not in cls._audio_fetchers:
            raise KeyError(f"Audio provider '{name}' not registered")
        cls._default_audio = name


def _register_default_fetchers() -> None:
    """Register built-in fetchers on module load."""
    # Import here to avoid circular imports
    from .images import ImageFetcher
    from .audio import AudioFetcher
    
    FetcherRegistry.register_image("pollinations", ImageFetcher, set_default=True)
    FetcherRegistry.register_audio("edge-tts", AudioFetcher, set_default=True)


# Auto-register default fetchers when module is imported
_register_default_fetchers()
