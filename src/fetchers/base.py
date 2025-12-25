"""Base fetcher class."""

from abc import ABC, abstractmethod


class BaseFetcher(ABC):
    """Abstract base class for all fetchers."""
    
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
