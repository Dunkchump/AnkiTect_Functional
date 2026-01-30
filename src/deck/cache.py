"""Cache management with thread-safe operations."""

import asyncio
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Union

from ..config import Config


class CacheManager:
    """
    Manage build cache for already processed files.
    
    Thread-safe implementation using locks for concurrent access.
    Supports both sync and async operations.
    """
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize cache manager.
        
        Args:
            cache_file: Path to cache JSON file (defaults to data/cache/build_cache.json)
        """
        if cache_file is None:
            cache_file = os.path.join(Config.CACHE_DIR, "build_cache.json")
        
        self.cache_file = cache_file
        self._lock = Lock()  # Thread lock for sync operations
        self._async_lock: Optional[asyncio.Lock] = None  # Lazy init for async
        self.cache: Dict = self._load_cache()
        
        # Batch pending writes to reduce I/O
        self._pending_writes: List[str] = []
        self._batch_size = 10  # Write to disk every N entries
    
    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create async lock (lazy initialization)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
    
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
        """Save cache to file (thread-safe with atomic write)."""
        with self._lock:
            self._save_internal()
    
    def _save_internal(self) -> None:
        """Internal save without lock (caller must hold lock)."""
        try:
            Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: temp file + rename
            temp_file = f"{self.cache_file}.{uuid.uuid4().hex[:8]}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
            os.replace(temp_file, self.cache_file)
        except Exception:
            # Clean up temp file on failure
            if 'temp_file' in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
    
    async def save_async(self) -> None:
        """Save cache to file (async-safe)."""
        async with self._get_async_lock():
            # Run sync save in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_internal)
    
    def is_cached(self, filename: str, min_size: int = 500) -> bool:
        """
        Check if file is in cache and exists on disk.
        
        Args:
            filename: Filename to check
            min_size: Minimum file size in bytes
            
        Returns:
            True if file is cached and valid, False otherwise
        """
        with self._lock:
            if filename not in self.cache:
                return False
            
            # Check if file still exists
            file_path = os.path.join(Config.MEDIA_DIR, filename)
            if os.path.exists(file_path):
                try:
                    if os.path.getsize(file_path) > min_size:
                        return True
                except OSError:
                    pass
            
            # Clean up stale cache entry
            del self.cache[filename]
            self._pending_writes.append(filename)
            if len(self._pending_writes) >= self._batch_size:
                self._save_internal()
                self._pending_writes.clear()
            return False
    
    def mark_cached(self, filename: Union[str, List[str]]) -> None:
        """
        Mark file(s) as cached (thread-safe with batched writes).
        
        Args:
            filename: Single filename or list of filenames
        """
        with self._lock:
            if isinstance(filename, list):
                for f in filename:
                    self.cache[f] = datetime.now().isoformat()
                    self._pending_writes.append(f)
            else:
                self.cache[filename] = datetime.now().isoformat()
                self._pending_writes.append(filename)
            
            # Batch writes to reduce I/O pressure
            if len(self._pending_writes) >= self._batch_size:
                self._save_internal()
                self._pending_writes.clear()
    
    async def mark_cached_async(self, filename: Union[str, List[str]]) -> None:
        """Mark file(s) as cached (async-safe)."""
        async with self._get_async_lock():
            if isinstance(filename, list):
                for f in filename:
                    self.cache[f] = datetime.now().isoformat()
            else:
                self.cache[filename] = datetime.now().isoformat()
            
            # For async, always save immediately to prevent data loss
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_internal)
    
    def flush(self) -> None:
        """Flush any pending writes to disk."""
        with self._lock:
            if self._pending_writes:
                self._save_internal()
                self._pending_writes.clear()
    
    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self.cache = {}
            self._pending_writes.clear()
            self._save_internal()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            return {
                'total_cached_files': len(self.cache),
                'cache_file': self.cache_file,
                'pending_writes': len(self._pending_writes)
            }
