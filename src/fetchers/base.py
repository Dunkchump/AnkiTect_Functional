"""Base fetcher class."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseFetcher(ABC):
    """
    Abstract base class for all fetchers.
    
    Provides lifecycle management and async context manager support.
    Subclasses should implement fetch() and optionally override close().
    """
    
    @abstractmethod
    async def fetch(self, source: str, output_path: str) -> bool:
        """
        Fetch resource and save to path.
        
        Args:
            source: Source URL or text to process
            output_path: Path where to save the result
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    async def close(self) -> None:
        """
        Close any open resources (sessions, connections, etc.).
        
        Subclasses should override this to clean up their resources.
        """
        pass
    
    async def __aenter__(self) -> "BaseFetcher":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensure resources are closed."""
        await self.close()
