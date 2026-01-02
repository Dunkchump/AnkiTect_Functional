"""Cache management."""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from ..config import Config


class CacheManager:
    """Manage build cache for already processed files."""
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize cache manager.
        
        Args:
            cache_file: Path to cache JSON file (defaults to data/cache/build_cache.json)
        """
        if cache_file is None:
            cache_file = os.path.join(Config.CACHE_DIR, "build_cache.json")
        
        self.cache_file = cache_file
        self.cache: Dict = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save(self) -> None:
        """Save cache to file."""
        try:
            Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass
    
    def is_cached(self, filename: str, min_size: int = 500) -> bool:
        """
        Check if file is in cache and exists on disk.
        
        Args:
            filename: Filename to check
            min_size: Minimum file size in bytes
            
        Returns:
            True if file is cached and valid, False otherwise
        """
        if filename not in self.cache:
            return False
        
        # Check if file still exists
        file_path = os.path.join(Config.MEDIA_DIR, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > min_size:
            return True
        
        # Clean up stale cache entry
        del self.cache[filename]
        self.save()
        return False
    
    def mark_cached(self, filename: str) -> None:
        """Mark file as cached."""
        self.cache[filename] = datetime.now().isoformat()
        self.save()
    
    def clear(self) -> None:
        """Clear all cache."""
        self.cache = {}
        self.save()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'total_cached_files': len(self.cache),
            'cache_file': self.cache_file
        }
