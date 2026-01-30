"""
Vocabulary Service - CRUD operations for vocabulary data.

Separates data access logic from UI layer, enabling:
- Clean architecture
- Swappable storage backends (CSV, SQLite)
- Testable business logic
"""

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, TYPE_CHECKING

import pandas as pd

from ..config import Config
from ..utils.parsing import TextParser

if TYPE_CHECKING:
    from .repository import BaseRepository


class StorageBackend(Enum):
    """Available storage backends."""
    CSV = "csv"
    SQLITE = "sqlite"


class VocabularyService:
    """
    Service for managing vocabulary data.
    
    Provides CRUD operations, validation, and data transformation.
    Supports multiple storage backends: CSV (legacy) and SQLite (recommended).
    
    Usage:
        # CSV backend (default, legacy)
        service = VocabularyService()
        
        # SQLite backend (recommended for new projects)
        service = VocabularyService(backend=StorageBackend.SQLITE)
        
        # Load and use
        service.load()
        df = service.get_all()
    """
    
    # Thread pool for blocking I/O operations
    _executor = ThreadPoolExecutor(max_workers=2)
    
    def __init__(
        self, 
        csv_path: Optional[str] = None,
        backend: StorageBackend = StorageBackend.CSV,
        db_path: Optional[str] = None
    ):
        """
        Initialize vocabulary service.
        
        Args:
            csv_path: Path to CSV file (for CSV backend)
            backend: Storage backend to use (CSV or SQLite)
            db_path: Path to SQLite database (for SQLite backend)
        """
        self.backend = backend
        self.csv_path = Path(csv_path or Config.CSV_FILE)
        self.db_path = db_path
        
        self._repository: Optional["BaseRepository"] = None
        self._df: Optional[pd.DataFrame] = None
        self._dirty: bool = False
        self._change_callbacks: List[Callable] = []
    
    def _get_repository(self) -> "BaseRepository":
        """Get or create the appropriate repository."""
        if self._repository is None:
            if self.backend == StorageBackend.SQLITE:
                from .repository import SQLiteRepository
                self._repository = SQLiteRepository(self.db_path)
            else:
                from .repository import CSVRepository
                self._repository = CSVRepository(str(self.csv_path))
        return self._repository
    
    @property
    def is_loaded(self) -> bool:
        """Check if data is loaded."""
        return self._df is not None
    
    @property
    def has_unsaved_changes(self) -> bool:
        """Check for unsaved changes."""
        return self._dirty
    
    @property
    def count(self) -> int:
        """Get total word count."""
        return len(self._df) if self._df is not None else 0
    
    def on_change(self, callback: Callable) -> None:
        """
        Register a callback for data changes.
        
        Args:
            callback: Function to call when data changes
        """
        self._change_callbacks.append(callback)
    
    def _notify_change(self) -> None:
        """Notify all registered callbacks of data change."""
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception:
                pass
    
    def load(self) -> bool:
        """
        Load vocabulary data from storage.
        
        Returns:
            True if loaded successfully
        """
        repo = self._get_repository()
        success = repo.load()
        
        if success:
            self._df = repo.get_all()
            self._dirty = False
        else:
            self._df = pd.DataFrame()
        
        return success
    
    async def load_async(self) -> bool:
        """
        Load vocabulary data asynchronously.
        
        Returns:
            True if loaded successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.load)
    
    def save(self) -> bool:
        """
        Save vocabulary data to storage.
        
        Returns:
            True if saved successfully
        """
        if self._df is None:
            return False
        
        repo = self._get_repository()
        success = repo.save()
        
        if success:
            self._dirty = False
        
        return success
    
    async def save_async(self) -> bool:
        """
        Save vocabulary data asynchronously.
        
        Returns:
            True if saved successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.save)
    
    def get_all(self) -> pd.DataFrame:
        """
        Get all vocabulary data.
        
        Returns:
            DataFrame with all words
        """
        if self._df is None:
            self.load()
        return self._df.copy() if self._df is not None else pd.DataFrame()
    
    def get_row(self, index: int) -> Optional[pd.Series]:
        """
        Get a single row by index.
        
        Args:
            index: Row index
            
        Returns:
            Row data or None
        """
        if self._df is None or index < 0 or index >= len(self._df):
            return None
        return self._df.iloc[index].copy()
    
    def update_row(self, index: int, data: Dict[str, Any]) -> bool:
        """
        Update a single row.
        
        Args:
            index: Row index
            data: Dictionary of field: value pairs
            
        Returns:
            True if updated successfully
        """
        if self._df is None or index < 0 or index >= len(self._df):
            return False
        
        try:
            for field, value in data.items():
                if field in self._df.columns:
                    # Normalize Unicode before saving
                    if isinstance(value, str):
                        value = TextParser.normalize_unicode(value)
                    self._df.at[index, field] = value
            
            self._dirty = True
            self._notify_change()
            return True
            
        except Exception as e:
            print(f"Error updating row: {e}")
            return False
    
    def add_row(self, data: Dict[str, Any]) -> int:
        """
        Add a new row.
        
        Args:
            data: Dictionary of field: value pairs
            
        Returns:
            Index of new row, or -1 on error
        """
        if self._df is None:
            self._df = pd.DataFrame()
        
        try:
            # Normalize all string values
            normalized_data = {}
            for field, value in data.items():
                if isinstance(value, str):
                    value = TextParser.normalize_unicode(value)
                normalized_data[field] = value
            
            new_row = pd.DataFrame([normalized_data])
            self._df = pd.concat([self._df, new_row], ignore_index=True)
            
            self._dirty = True
            self._notify_change()
            return len(self._df) - 1
            
        except Exception as e:
            print(f"Error adding row: {e}")
            return -1
    
    def delete_row(self, index: int) -> bool:
        """
        Delete a row by index.
        
        Args:
            index: Row index
            
        Returns:
            True if deleted successfully
        """
        if self._df is None or index < 0 or index >= len(self._df):
            return False
        
        try:
            self._df = self._df.drop(index).reset_index(drop=True)
            self._dirty = True
            self._notify_change()
            return True
            
        except Exception as e:
            print(f"Error deleting row: {e}")
            return False
    
    def search(self, query: str, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Search vocabulary by text query.
        
        Args:
            query: Search query
            columns: Columns to search (defaults to TargetWord, Meaning)
            
        Returns:
            Matching rows
        """
        if self._df is None or not query:
            return pd.DataFrame()
        
        columns = columns or ["TargetWord", "Meaning"]
        query = query.lower()
        
        mask = pd.Series([False] * len(self._df))
        for col in columns:
            if col in self._df.columns:
                mask |= self._df[col].astype(str).str.lower().str.contains(query, na=False)
        
        return self._df[mask].copy()
    
    def filter_by_tags(self, tags: List[str]) -> pd.DataFrame:
        """
        Filter vocabulary by tags.
        
        Args:
            tags: List of tags to filter by
            
        Returns:
            Matching rows
        """
        if self._df is None or not tags or "Tags" not in self._df.columns:
            return pd.DataFrame()
        
        def has_any_tag(row_tags: str) -> bool:
            row_tag_list = [t.strip().lower() for t in str(row_tags).split()]
            return any(t.lower() in row_tag_list for t in tags)
        
        mask = self._df["Tags"].apply(has_any_tag)
        return self._df[mask].copy()
    
    def get_unique_tags(self) -> List[str]:
        """
        Get all unique tags.
        
        Returns:
            List of unique tags
        """
        if self._df is None or "Tags" not in self._df.columns:
            return []
        
        all_tags = set()
        for tags_str in self._df["Tags"].dropna():
            for tag in str(tags_str).split():
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
        
        return sorted(all_tags)
    
    def compute_content_hash(self, index: int) -> Optional[str]:
        """
        Compute content hash for a row (for caching/change detection).
        
        Args:
            index: Row index
            
        Returns:
            SHA256 hash or None
        """
        row = self.get_row(index)
        if row is None:
            return None
        
        # Include fields that affect media generation
        content = f"{row.get('TargetWord', '')}|{row.get('Meaning', '')}|{row.get('ImagePrompt', '')}|{row.get('ContextSentences', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get vocabulary statistics.
        
        Returns:
            Dictionary with stats
        """
        if self._df is None:
            return {"total_words": 0}
        
        stats = {
            "total_words": len(self._df),
            "unique_tags": len(self.get_unique_tags()),
            "has_image_prompt": 0,
            "has_sentences": 0,
            "has_etymology": 0,
        }
        
        if "ImagePrompt" in self._df.columns:
            stats["has_image_prompt"] = (self._df["ImagePrompt"].astype(str).str.strip() != "").sum()
        
        if "ContextSentences" in self._df.columns:
            stats["has_sentences"] = (self._df["ContextSentences"].astype(str).str.strip() != "").sum()
        
        if "Etymology" in self._df.columns:
            stats["has_etymology"] = (self._df["Etymology"].astype(str).str.strip() != "").sum()
        
        return stats
    
    def get_shuffled_dataframe(self, shuffle: bool = True) -> pd.DataFrame:
        """
        Get a shuffled copy of the vocabulary for deck building.
        
        This is the primary interface for AnkiDeckBuilder to get vocabulary data.
        Ensures consistent loading and normalization.
        
        Args:
            shuffle: Whether to randomize order (default True)
            
        Returns:
            Shuffled DataFrame copy with stripped column names
        """
        if self._df is None:
            self.load()
        
        if self._df is None or self._df.empty:
            return pd.DataFrame()
        
        df = self._df.copy()
        df.columns = df.columns.str.strip()
        
        if shuffle:
            df = df.sample(frac=1).reset_index(drop=True)
        
        return df
    
    @classmethod
    def load_from_csv(cls, csv_path: str) -> "VocabularyService":
        """
        Factory method to create and load from a specific CSV.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Loaded VocabularyService instance
        """
        service = cls(csv_path, backend=StorageBackend.CSV)
        service.load()
        return service
    
    @classmethod
    def load_from_sqlite(cls, db_path: Optional[str] = None) -> "VocabularyService":
        """
        Factory method to create and load from SQLite database.
        
        Args:
            db_path: Path to SQLite database (uses default if None)
            
        Returns:
            Loaded VocabularyService instance
        """
        service = cls(backend=StorageBackend.SQLITE, db_path=db_path)
        service.load()
        return service
    
    def migrate_to_sqlite(self, db_path: Optional[str] = None) -> bool:
        """
        Migrate current CSV data to SQLite database.
        
        Args:
            db_path: Path to SQLite database
            
        Returns:
            True if migration successful
        """
        if self._df is None or self._df.empty:
            return False
        
        try:
            from .repository import SQLiteRepository
            
            sqlite_repo = SQLiteRepository(db_path)
            sqlite_repo.load()  # Initialize schema
            
            # Import from current CSV
            imported = sqlite_repo.import_from_csv(str(self.csv_path))
            
            if imported > 0:
                print(f"Migrated {imported} rows to SQLite")
                return True
            return False
            
        except Exception as e:
            print(f"Migration failed: {e}")
            return False
    
    def get_repository(self) -> "BaseRepository":
        """
        Get the underlying repository for advanced operations.
        
        Returns:
            The repository instance (CSVRepository or SQLiteRepository)
        """
        return self._get_repository()
