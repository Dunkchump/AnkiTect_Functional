"""
Repository Pattern - Abstract data access layer.

Enables switching between CSV and SQLite backends without changing business logic.
Designed for future extensibility (PostgreSQL, cloud storage, etc.)
"""

import hashlib
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import pandas as pd

from ..config import Config
from ..utils.parsing import TextParser


class BaseRepository(ABC):
    """
    Abstract base class for vocabulary data repositories.
    
    Defines the contract for all data access operations.
    Implementations can use CSV, SQLite, PostgreSQL, etc.
    """
    
    @abstractmethod
    def load(self) -> bool:
        """Load data from storage. Returns True if successful."""
        pass
    
    @abstractmethod
    def save(self) -> bool:
        """Save data to storage. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_all(self) -> pd.DataFrame:
        """Get all vocabulary entries as DataFrame."""
        pass
    
    @abstractmethod
    def get_row(self, index: int) -> Optional[pd.Series]:
        """Get single row by index."""
        pass
    
    @abstractmethod
    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get row by UUID."""
        pass
    
    @abstractmethod
    def update_row(self, index: int, data: Dict[str, Any]) -> bool:
        """Update row at index with data."""
        pass
    
    @abstractmethod
    def add_row(self, data: Dict[str, Any]) -> int:
        """Add new row. Returns index or -1 on error."""
        pass
    
    @abstractmethod
    def delete_row(self, index: int) -> bool:
        """Delete row at index."""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Get total row count."""
        pass
    
    @abstractmethod
    def search(self, query: str, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Search rows matching query."""
        pass


class CSVRepository(BaseRepository):
    """
    CSV-based repository implementation.
    
    Uses pandas for CSV operations. This is the legacy storage format.
    """
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize CSV repository.
        
        Args:
            csv_path: Path to CSV file
        """
        self.csv_path = Path(csv_path or Config.CSV_FILE)
        self._df: Optional[pd.DataFrame] = None
        self._dirty: bool = False
    
    @property
    def is_dirty(self) -> bool:
        """Check for unsaved changes."""
        return self._dirty
    
    def load(self) -> bool:
        """Load vocabulary from CSV file."""
        if not self.csv_path.exists():
            self._df = pd.DataFrame()
            return False
        
        try:
            self._df = pd.read_csv(
                self.csv_path,
                sep='|',
                encoding='utf-8-sig',
                quoting=3,  # csv.QUOTE_NONE
                on_bad_lines='warn',
                engine='python'
            ).fillna('')
            
            self._df.columns = self._df.columns.str.strip()
            self._dirty = False
            return True
            
        except Exception as e:
            print(f"Error loading CSV: {e}")
            self._df = pd.DataFrame()
            return False
    
    def save(self) -> bool:
        """Save vocabulary to CSV file."""
        if self._df is None:
            return False
        
        try:
            self._df.to_csv(
                self.csv_path,
                sep='|',
                index=False,
                encoding='utf-8-sig'
            )
            self._dirty = False
            return True
        except Exception as e:
            print(f"Error saving CSV: {e}")
            return False
    
    def get_all(self) -> pd.DataFrame:
        """Get all rows as DataFrame."""
        if self._df is None:
            self.load()
        return self._df.copy() if self._df is not None else pd.DataFrame()
    
    def get_row(self, index: int) -> Optional[pd.Series]:
        """Get single row by index."""
        if self._df is None or index < 0 or index >= len(self._df):
            return None
        return self._df.iloc[index].copy()
    
    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get row by UUID field."""
        if self._df is None or 'UUID' not in self._df.columns:
            return None
        
        matches = self._df[self._df['UUID'] == uuid]
        if matches.empty:
            return None
        return matches.iloc[0].to_dict()
    
    def update_row(self, index: int, data: Dict[str, Any]) -> bool:
        """Update row at index."""
        if self._df is None or index < 0 or index >= len(self._df):
            return False
        
        try:
            for field, value in data.items():
                if field in self._df.columns:
                    if isinstance(value, str):
                        value = TextParser.normalize_unicode(value)
                    self._df.at[index, field] = value
            self._dirty = True
            return True
        except Exception:
            return False
    
    def add_row(self, data: Dict[str, Any]) -> int:
        """Add new row."""
        if self._df is None:
            self._df = pd.DataFrame()
        
        try:
            normalized = {
                k: TextParser.normalize_unicode(v) if isinstance(v, str) else v
                for k, v in data.items()
            }
            self._df = pd.concat([self._df, pd.DataFrame([normalized])], ignore_index=True)
            self._dirty = True
            return len(self._df) - 1
        except Exception:
            return -1
    
    def delete_row(self, index: int) -> bool:
        """Delete row at index."""
        if self._df is None or index < 0 or index >= len(self._df):
            return False
        
        try:
            self._df = self._df.drop(index).reset_index(drop=True)
            self._dirty = True
            return True
        except Exception:
            return False
    
    def count(self) -> int:
        """Get total row count."""
        return len(self._df) if self._df is not None else 0
    
    def search(self, query: str, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Search rows matching query."""
        if self._df is None or not query:
            return pd.DataFrame()
        
        columns = columns or ["TargetWord", "Meaning"]
        query = query.lower()
        
        mask = pd.Series([False] * len(self._df))
        for col in columns:
            if col in self._df.columns:
                mask |= self._df[col].astype(str).str.lower().str.contains(query, na=False)
        
        return self._df[mask].copy()


class SQLiteRepository(BaseRepository):
    """
    SQLite-based repository implementation.
    
    Provides:
    - Transactional updates (no full-file rewrites)
    - Build history tracking
    - Media file metadata
    - Sync status for incremental deck updates
    """
    
    # Schema version for migrations
    SCHEMA_VERSION = 1
    
    # Default columns matching CSV structure
    VOCABULARY_COLUMNS = [
        "TargetWord", "Meaning", "IPA", "Part_of_Speech", "Gender",
        "Morphology", "Nuance", "ContextSentences", "ContextTranslation",
        "Etymology", "Mnemonic", "Analogues", "ImagePrompt", "Tags"
    ]
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite repository.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = str(Path(Config.CACHE_DIR) / "ankitect.db")
        
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_db_dir()
    
    def _ensure_db_dir(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Schema versioning table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            
            # Main vocabulary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE,
                    target_word TEXT NOT NULL,
                    meaning TEXT,
                    ipa TEXT,
                    part_of_speech TEXT,
                    gender TEXT,
                    morphology TEXT,
                    nuance TEXT,
                    context_sentences TEXT,
                    context_translation TEXT,
                    etymology TEXT,
                    mnemonic TEXT,
                    analogues TEXT,
                    image_prompt TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    synced_to_deck INTEGER DEFAULT 0
                )
            """)
            
            # Media files tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vocabulary_id INTEGER REFERENCES vocabulary(id) ON DELETE CASCADE,
                    media_type TEXT CHECK(media_type IN ('image', 'audio_word', 'audio_sent_1', 'audio_sent_2', 'audio_sent_3')),
                    file_path TEXT NOT NULL,
                    file_hash TEXT,
                    source_prompt TEXT,
                    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(vocabulary_id, media_type)
                )
            """)
            
            # Build history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS build_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    built_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    language TEXT,
                    word_count INTEGER,
                    images_generated INTEGER,
                    audio_generated INTEGER,
                    duration_seconds REAL,
                    output_file TEXT,
                    success INTEGER DEFAULT 1
                )
            """)
            
            # Indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_target ON vocabulary(target_word)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_uuid ON vocabulary(uuid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_synced ON vocabulary(synced_to_deck)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_vocab ON media_files(vocabulary_id)")
            
            # Record schema version
            cursor.execute("INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
                          (self.SCHEMA_VERSION, datetime.now().isoformat()))
            
            conn.commit()
    
    def load(self) -> bool:
        """Initialize database and schema."""
        try:
            self._init_schema()
            return True
        except Exception as e:
            print(f"Error initializing SQLite: {e}")
            return False
    
    def save(self) -> bool:
        """SQLite auto-saves, so this is a no-op."""
        return True
    
    def get_all(self) -> pd.DataFrame:
        """Get all vocabulary entries as DataFrame."""
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM vocabulary ORDER BY id", conn)
                return self._sql_to_csv_columns(df)
        except Exception as e:
            print(f"Error reading vocabulary: {e}")
            return pd.DataFrame()
    
    def get_row(self, index: int) -> Optional[pd.Series]:
        """Get row by index (0-based offset)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vocabulary ORDER BY id LIMIT 1 OFFSET ?", (index,))
                row = cursor.fetchone()
                if row:
                    return pd.Series(dict(row))
                return None
        except Exception:
            return None
    
    def get_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get row by UUID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vocabulary WHERE uuid = ?", (uuid,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception:
            return None
    
    def update_row(self, index: int, data: Dict[str, Any]) -> bool:
        """Update row at index."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get row ID from index
                cursor.execute("SELECT id FROM vocabulary ORDER BY id LIMIT 1 OFFSET ?", (index,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                row_id = result['id']
                
                # Build update query
                columns = self._csv_to_sql_columns(data)
                columns['updated_at'] = datetime.now().isoformat()
                
                set_clause = ", ".join(f"{k} = ?" for k in columns.keys())
                values = list(columns.values()) + [row_id]
                
                cursor.execute(f"UPDATE vocabulary SET {set_clause} WHERE id = ?", values)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating row: {e}")
            return False
    
    def add_row(self, data: Dict[str, Any]) -> int:
        """Add new row. Returns the new row's index."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                columns = self._csv_to_sql_columns(data)
                columns['created_at'] = datetime.now().isoformat()
                
                # Generate UUID if not provided
                if 'uuid' not in columns or not columns['uuid']:
                    word = columns.get('target_word', '')
                    meaning = columns.get('meaning', '')
                    columns['uuid'] = hashlib.sha256(f"{word}|{meaning}|{datetime.now().isoformat()}".encode()).hexdigest()[:32]
                
                placeholders = ", ".join("?" for _ in columns)
                column_names = ", ".join(columns.keys())
                
                cursor.execute(
                    f"INSERT INTO vocabulary ({column_names}) VALUES ({placeholders})",
                    list(columns.values())
                )
                conn.commit()
                
                # Return index (row count - 1)
                cursor.execute("SELECT COUNT(*) FROM vocabulary")
                return cursor.fetchone()[0] - 1
        except Exception as e:
            print(f"Error adding row: {e}")
            return -1
    
    def delete_row(self, index: int) -> bool:
        """Delete row at index."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM vocabulary ORDER BY id LIMIT 1 OFFSET ?", (index,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                cursor.execute("DELETE FROM vocabulary WHERE id = ?", (result['id'],))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def count(self) -> int:
        """Get total row count."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM vocabulary")
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def search(self, query: str, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Search rows matching query."""
        if not query:
            return pd.DataFrame()
        
        try:
            with self._get_connection() as conn:
                search_cols = ["target_word", "meaning"] if not columns else [
                    self._csv_to_sql_column_name(c) for c in columns
                ]
                
                conditions = " OR ".join(f"{col} LIKE ?" for col in search_cols)
                params = [f"%{query}%" for _ in search_cols]
                
                df = pd.read_sql_query(
                    f"SELECT * FROM vocabulary WHERE {conditions} ORDER BY id",
                    conn,
                    params=params
                )
                return self._sql_to_csv_columns(df)
        except Exception:
            return pd.DataFrame()
    
    # ==================== SQLite-specific methods ====================
    
    def get_unsynced_words(self) -> pd.DataFrame:
        """Get words not yet synced to a deck."""
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM vocabulary WHERE synced_to_deck = 0 ORDER BY id",
                    conn
                )
                return self._sql_to_csv_columns(df)
        except Exception:
            return pd.DataFrame()
    
    def mark_synced(self, uuids: List[str]) -> int:
        """Mark words as synced to deck."""
        if not uuids:
            return 0
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" for _ in uuids)
                cursor.execute(
                    f"UPDATE vocabulary SET synced_to_deck = 1, updated_at = ? WHERE uuid IN ({placeholders})",
                    [datetime.now().isoformat()] + uuids
                )
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0
    
    def add_build_history(self, language: str, word_count: int, images: int, audio: int,
                         duration: float, output_file: str, success: bool = True) -> int:
        """Record a build in history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO build_history 
                    (language, word_count, images_generated, audio_generated, duration_seconds, output_file, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (language, word_count, images, audio, duration, output_file, 1 if success else 0))
                conn.commit()
                return cursor.lastrowid
        except Exception:
            return -1
    
    def get_build_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent build history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM build_history ORDER BY built_at DESC LIMIT ?",
                    (limit,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []
    
    def import_from_csv(self, csv_path: str) -> int:
        """
        Import vocabulary from CSV file.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Number of rows imported
        """
        csv_repo = CSVRepository(csv_path)
        if not csv_repo.load():
            return 0
        
        df = csv_repo.get_all()
        if df.empty:
            return 0
        
        imported = 0
        for _, row in df.iterrows():
            data = row.to_dict()
            if self.add_row(data) >= 0:
                imported += 1
        
        return imported
    
    def export_to_csv(self, csv_path: str) -> bool:
        """Export vocabulary to CSV file."""
        try:
            df = self.get_all()
            df.to_csv(csv_path, sep='|', index=False, encoding='utf-8-sig')
            return True
        except Exception:
            return False
    
    # ==================== Column mapping helpers ====================
    
    @staticmethod
    def _csv_to_sql_column_name(csv_name: str) -> str:
        """Convert CSV column name to SQL column name."""
        mapping = {
            "TargetWord": "target_word",
            "Meaning": "meaning",
            "IPA": "ipa",
            "Part_of_Speech": "part_of_speech",
            "Gender": "gender",
            "Morphology": "morphology",
            "Nuance": "nuance",
            "ContextSentences": "context_sentences",
            "ContextTranslation": "context_translation",
            "Etymology": "etymology",
            "Mnemonic": "mnemonic",
            "Analogues": "analogues",
            "ImagePrompt": "image_prompt",
            "Tags": "tags",
            "UUID": "uuid",
        }
        return mapping.get(csv_name, csv_name.lower())
    
    @staticmethod
    def _sql_to_csv_column_name(sql_name: str) -> str:
        """Convert SQL column name to CSV column name."""
        mapping = {
            "target_word": "TargetWord",
            "meaning": "Meaning",
            "ipa": "IPA",
            "part_of_speech": "Part_of_Speech",
            "gender": "Gender",
            "morphology": "Morphology",
            "nuance": "Nuance",
            "context_sentences": "ContextSentences",
            "context_translation": "ContextTranslation",
            "etymology": "Etymology",
            "mnemonic": "Mnemonic",
            "analogues": "Analogues",
            "image_prompt": "ImagePrompt",
            "tags": "Tags",
            "uuid": "UUID",
        }
        return mapping.get(sql_name, sql_name)
    
    def _csv_to_sql_columns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert CSV column names to SQL column names in dict."""
        return {
            self._csv_to_sql_column_name(k): (
                TextParser.normalize_unicode(v) if isinstance(v, str) else v
            )
            for k, v in data.items()
        }
    
    def _sql_to_csv_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert SQL DataFrame columns to CSV column names."""
        rename_map = {col: self._sql_to_csv_column_name(col) for col in df.columns}
        return df.rename(columns=rename_map)
