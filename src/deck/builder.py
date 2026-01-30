"""Main Anki deck builder."""

import asyncio
import json
import hashlib
import os
import re
import shutil
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import genanki
import pandas as pd

from ..config import (
    Config,
    SettingsManager,
    get_default_enabled,
    get_default_order,
    validate_sections_config,
    get_default_card_types_enabled,
    get_default_card_types_order,
    validate_card_types_config,
    get_active_card_types,
)
from ..models import CardData
from ..templates import CardTemplates
from ..fetchers import AudioFetcher, ImageFetcher
from ..services import VocabularyService
from ..utils import clean_text_for_display, format_analogues_html, ensure_dir, get_file_size_mb
from ..utils.parsing import TextParser
from ..utils.paths import MediaPathGenerator
from .cache import CacheManager


class ThreadSafeStats:
    """Thread-safe statistics counter for concurrent updates."""
    
    def __init__(self):
        self._lock = Lock()
        self._counters = Counter()
        self._start_time = time.time()
        self._failed_words: List[str] = []
    
    def increment(self, key: str, value: int = 1) -> None:
        """Increment a counter atomically."""
        with self._lock:
            self._counters[key] += value
    
    def get(self, key: str, default: Any = 0) -> Any:
        """Get a counter value with optional default."""
        with self._lock:
            return self._counters.get(key, default)
    
    def add_failed_word(self, word: str) -> None:
        """Track a failed word for reporting."""
        with self._lock:
            self._failed_words.append(word)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all statistics as a dictionary."""
        with self._lock:
            return {
                **dict(self._counters),
                'start_time': self._start_time,
                'failed_words': self._failed_words.copy()
            }
    
    def set(self, key: str, value: Any) -> None:
        """Set a value (for non-counter items)."""
        with self._lock:
            self._counters[key] = value


class AnkiDeckBuilder:
    """Main class for building Anki decks."""
    
    # Minimum disk space required (in bytes) - 500MB safety margin
    MIN_DISK_SPACE_BYTES = 500 * 1024 * 1024
    
    def __init__(
        self,
        language: str = "EN",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """
        Initialize deck builder.
        
        Args:
            language: Language code ('EN', 'DE', etc.)
            progress_callback: Optional callback for progress updates.
                              Payload schema: {"event": "log"|"progress", "message": str, "value": float}
        """
        self.language = language
        self.progress_callback = progress_callback or self._default_callback
        self._ensure_dirs()
        
        # Load card sections configuration from settings
        # Force reload to get fresh settings from disk
        self._settings = SettingsManager()
        self._settings.reload()  # Ensure we have the latest settings from disk
        
        self._sections_enabled: Dict[str, bool] = self._settings.get(
            "CARD_SECTIONS_ENABLED",
            get_default_enabled()
        )
        self._sections_order: List[str] = self._settings.get(
            "CARD_SECTIONS_ORDER",
            get_default_order()
        )
        # Validate sections config
        self._sections_enabled, self._sections_order = validate_sections_config(
            self._sections_enabled,
            self._sections_order
        )

        # Load card types configuration
        self._card_types_enabled: Dict[str, bool] = self._settings.get(
            "CARD_TYPES_ENABLED",
            get_default_card_types_enabled()
        )
        self._card_types_order: List[str] = self._settings.get(
            "CARD_TYPES_ORDER",
            get_default_card_types_order()
        )
        # Validate card types config
        self._card_types_enabled, self._card_types_order = validate_card_types_config(
            self._card_types_enabled,
            self._card_types_order
        )
        
        # Log sections configuration for debugging
        enabled_list = [sid for sid, en in self._sections_enabled.items() if en]
        disabled_list = [sid for sid, en in self._sections_enabled.items() if not en]
        self._emit("log", f"📋 Enabled sections: {', '.join(enabled_list)}")
        if disabled_list:
            self._emit("log", f"🚫 Disabled sections: {', '.join(disabled_list)}")
        self._emit("log", f"📐 Section order: {' → '.join(self._sections_order)}")

        # Log card types configuration
        enabled_types = [tid for tid, en in self._card_types_enabled.items() if en]
        disabled_types = [tid for tid, en in self._card_types_enabled.items() if not en]
        self._emit("log", f"🧩 Enabled card types: {', '.join(enabled_types)}")
        if disabled_types:
            self._emit("log", f"🚫 Disabled card types: {', '.join(disabled_types)}")
        self._emit("log", f"🧭 Card type order: {' → '.join(self._card_types_order)}")
        
        self.model = self._create_model()
        self.deck = genanki.Deck(Config.DECK_ID, Config.DECK_NAME)
        self.media_files: List[str] = []
        self._media_files_lock = Lock()  # Protect media_files list
        
        self.semaphore = asyncio.Semaphore(Config.CONCURRENCY)
        self.current_concurrency = Config.CONCURRENCY
        self._concurrency_lock = Lock()  # Protect concurrency adjustments
        
        self.cache = CacheManager()
        # Dependency injection: Pass callback to AudioFetcher for adaptive rate limiting
        self.audio_fetcher = AudioFetcher(concurrency_callback=self._adjust_concurrency)
        self.image_fetcher = ImageFetcher(concurrency_callback=self._adjust_concurrency)
        
        # Thread-safe statistics
        self.stats = ThreadSafeStats()
        
        # Adaptive parallelization (protected by _concurrency_lock)
        self.adaptive_stats = {
            'consecutive_success': 0,
            'consecutive_failures': 0,
            'last_status_429': False,
            'concurrency_adjustments': 0
        }
        
        # Progress tracking for callback
        self._total_items: int = 0
        self._processed_items: int = 0
        self._log_every: int = 1
        self._progress_every: int = 1

    @staticmethod
    def _row_get(row: Any, field: str, default: Any = "") -> Any:
        """Get field value from a pandas Series or namedtuple row."""
        try:
            if hasattr(row, "_asdict"):
                if hasattr(row, field):
                    return getattr(row, field)
                safe_field = field.replace(" ", "_")
                if hasattr(row, safe_field):
                    return getattr(row, safe_field)
                return default
            if hasattr(row, "get"):
                return row.get(field, default)
        except Exception:
            return default
        return default
    
    @staticmethod
    def _default_callback(payload: Dict[str, Any]) -> None:
        """Default callback that prints to console (for CLI compatibility)."""
        if payload.get("event") == "log":
            print(payload.get("message", ""))
        elif payload.get("event") == "progress":
            # Simple progress output for CLI
            value = payload.get("value", 0)
            message = payload.get("message", "")
            if message:
                print(f"[{value:.1f}%] {message}")
    
    def _emit(self, event: str, message: str = "", value: float = 0.0) -> None:
        """
        Emit a progress event via the callback.
        
        Args:
            event: Event type ('log' or 'progress')
            message: Human-readable message
            value: Progress value (0-100 for progress events)
        """
        payload: Dict[str, Any] = {
            "event": event,
            "message": message,
            "value": value
        }
        self.progress_callback(payload)
    
    def _ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        ensure_dir(Config.MEDIA_DIR)
        ensure_dir(Config.CACHE_DIR)
        ensure_dir(Config.OUTPUT_DIR)
        ensure_dir(Config.INPUT_DIR)
    
    def _check_disk_space(self, estimated_words: int) -> bool:
        """
        Check if there's enough disk space for the build.
        
        Args:
            estimated_words: Number of words to process
            
        Returns:
            True if enough space, False otherwise
        """
        try:
            disk_usage = shutil.disk_usage(Config.MEDIA_DIR)
            # Estimate ~500KB per word (image + audio files)
            estimated_bytes = estimated_words * 500 * 1024
            required_bytes = estimated_bytes + self.MIN_DISK_SPACE_BYTES
            
            if disk_usage.free < required_bytes:
                free_mb = disk_usage.free / (1024 * 1024)
                required_mb = required_bytes / (1024 * 1024)
                self._emit("log", f"⚠️ Low disk space: {free_mb:.0f}MB free, {required_mb:.0f}MB recommended")
                return False
            return True
        except Exception:
            return True  # Proceed if we can't check
    
    def _adjust_concurrency(self, status_code: Optional[int] = None, is_success: Optional[bool] = None) -> None:
        """
        Track API response patterns for monitoring (thread-safe).
        
        Note: We no longer dynamically replace the semaphore as this is unsafe
        with concurrent tasks. Instead, we just track statistics and add delays.
        """
        with self._concurrency_lock:
            if status_code == 429:  # Too Many Requests
                self.adaptive_stats['last_status_429'] = True
                self.adaptive_stats['consecutive_success'] = 0
                self.adaptive_stats['consecutive_failures'] += 1
                self.adaptive_stats['concurrency_adjustments'] += 1
                self._emit("log", f"[WARN] 429 Too Many Requests! Adding backoff delay...")
            
            elif status_code and status_code < 400:
                self.adaptive_stats['consecutive_failures'] = 0
                self.adaptive_stats['consecutive_success'] += 1
            
            elif is_success is False:
                self.adaptive_stats['consecutive_success'] = 0
                self.adaptive_stats['consecutive_failures'] += 1
    
    def _get_backoff_delay(self) -> float:
        """Get current backoff delay based on failure count."""
        with self._concurrency_lock:
            failures = self.adaptive_stats['consecutive_failures']
            if failures == 0:
                return 0.0
            # Exponential backoff: 0.5s, 1s, 2s, 4s, max 10s
            return min(10.0, 0.5 * (2 ** min(failures, 4)))
    
    def _add_media_file(self, path: str) -> None:
        """Add a media file to the list (thread-safe)."""
        with self._media_files_lock:
            self.media_files.append(path)
    
    def _generate_model_id(self) -> int:
        """
        Generate a unique model ID based on sections configuration.
        
        This ensures that when section configuration changes, a NEW model
        is created in Anki instead of reusing the cached old model with
        outdated templates.
        
        Returns:
            Unique model ID (int) based on base model ID + sections hash
        """
        # Create a stable hash from sections configuration
        # Include both enabled state and order
        style = self._settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        style_str = json.dumps(style, sort_keys=True)

        config_str = (
            str(sorted([(k, v) for k, v in self._sections_enabled.items()])) +
            str(self._sections_order) +
            str(sorted([(k, v) for k, v in self._card_types_enabled.items()])) +
            str(self._card_types_order) +
            style_str
        )
        
        # Use hashlib for deterministic hash (Python's hash() varies between sessions)
        config_hash = int(hashlib.md5(config_str.encode()).hexdigest()[:6], 16) % 1000000
        
        # Combine with base model ID
        # Base ID: 1607393148 (DE) or 1607393149 (EN)
        # We add the hash to create unique IDs like 1607393148000001, etc.
        base_id = Config.MODEL_ID
        unique_id = base_id * 1000000 + config_hash
        
        self._emit("log", f"🔑 Model ID: {unique_id} (config hash: {config_hash})")
        
        return unique_id
    
    def _create_model(self) -> genanki.Model:
        """Create Anki card model with dynamic template based on sections config."""
        # Build dynamic back template based on user's section configuration
        back_rec = CardTemplates.build_dynamic_back_template(
            sections_enabled=self._sections_enabled,
            sections_order=self._sections_order,
            forvo_code=Config.FORVO_CODE
        )
        
        # Generate unique model ID based on sections config
        # This forces Anki to create a new model when sections change
        model_id = self._generate_model_id()
        
        fields = [
            {'name': 'TargetWord'}, {'name': 'Meaning'}, {'name': 'IPA'}, {'name': 'Part_of_Speech'}, 
            {'name': 'Gender'}, {'name': 'Morphology'}, {'name': 'Nuance'}, 
            {'name': 'Sentence_1'}, {'name': 'Sentence_2'}, {'name': 'Sentence_3'},
            {'name': 'ContextTranslation'}, {'name': 'Etymology'}, {'name': 'Mnemonic'}, {'name': 'Analogues'}, 
            {'name': 'Image'}, {'name': 'Tags'}, 
            {'name': 'AudioWord'}, 
            {'name': 'Audio_Sent_1'}, {'name': 'Audio_Sent_2'}, {'name': 'Audio_Sent_3'},
            {'name': 'Audio_Path_Word'}, 
            {'name': 'ContextSentences'}, 
            {'name': 'UUID'}
        ]

        active_card_types = get_active_card_types(
            self._card_types_enabled,
            self._card_types_order
        )
        templates = []
        for idx, card_type in enumerate(active_card_types):
            front = CardTemplates.get_front_template_for_type(card_type.id, Config.LABEL)
            templates.append({
                'name': f"{idx + 1}. {card_type.name}",
                'qfmt': front,
                'afmt': back_rec,
            })
        
        style = self._settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return genanki.Model(
            model_id,
            f'AnkiTect {self.language}',
            fields=fields,
            templates=templates,
            css=CardTemplates.get_css(style)
        )
    
    async def _download_confetti(self) -> None:
        """Download confetti library."""
        filename = "_confetti.js"
        path = os.path.join(Config.MEDIA_DIR, filename)
        
        if not os.path.exists(path):
            try:
                await self.image_fetcher.fetch(Config.CONFETTI_URL, path)
            except Exception:
                pass
        
        if os.path.exists(path):
            self._add_media_file(path)
    
    async def process_row(self, index: int, row: pd.Series) -> None:
        """Process single vocabulary row."""
        # Apply backoff delay if we've been hitting rate limits
        backoff = self._get_backoff_delay()
        if backoff > 0:
            await asyncio.sleep(backoff)
        else:
            await asyncio.sleep(0)  # Yield without throttling
        
        async with self.semaphore:
            try:
                raw_word = str(self._row_get(row, 'TargetWord', '')).strip()
                if not raw_word:
                    self._update_progress()
                    return
                
                # Unicode normalization to prevent encoding inconsistencies
                raw_word = TextParser.normalize_unicode(raw_word)
                clean_word = re.sub(Config.STRIP_REGEX, '', raw_word, flags=re.IGNORECASE).strip()
                clean_word = TextParser.normalize_unicode(clean_word)
                
                # Generate UUID using MediaPathGenerator (DRY + collision resistant)
                meaning_full = TextParser.normalize_unicode(str(self._row_get(row, 'Meaning', '')).strip())
                pos = str(self._row_get(row, 'Part_of_Speech', '')).strip()
                card_uuid = MediaPathGenerator.generate_card_uuid(
                    clean_word, pos, meaning_full, index, self.language
                )
                
                self.stats.increment('words_processed')
                if self._should_log_progress(index):
                    self._emit("log", f"[{index+1}/{self._total_items}] Processing: {clean_word}...")
                
                # Process sentences using centralized TextParser (DRY)
                raw_context = str(self._row_get(row, 'ContextSentences', ''))
                sentences = TextParser.split_sentences(raw_context, max_count=3, pad=True)
                
                # Process translations
                raw_translation = str(self._row_get(row, 'ContextTranslation', ''))
                clean_trans = TextParser.clean_for_display(raw_translation)
                
                # Process analogues
                raw_analogues = str(self._row_get(row, 'Analogues', ''))
                clean_analogues = TextParser.format_analogues_html(raw_analogues)
                
                cloze_context = raw_context if raw_context else (sentences[0] if sentences[0] else "")
                
                # Generate file names using MediaPathGenerator (DRY)
                media_files = MediaPathGenerator.get_all_media_files(card_uuid)
                f_img = media_files['image']
                f_word = media_files['word']
                f_s1 = media_files['sent_1']
                f_s2 = media_files['sent_2']
                f_s3 = media_files['sent_3']
                
                # Check cache and download/generate
                tasks: Dict[str, Any] = {}
                
                # Image
                if self.cache.is_cached(f_img):
                    has_img = True
                else:
                    tasks["img"] = self.image_fetcher.fetch(
                        str(self._row_get(row, 'ImagePrompt', '')),
                        os.path.join(Config.MEDIA_DIR, f_img)
                    )
                    has_img = False
                
                # Word audio
                if self.cache.is_cached(f_word):
                    has_w = True
                else:
                    tasks["word"] = self.audio_fetcher.fetch(
                        raw_word,
                        os.path.join(Config.MEDIA_DIR, f_word),
                        volume="+40%"
                    )
                    has_w = False
                
                # Sentence audio
                sentence_results: Dict[int, bool] = {0: False, 1: False, 2: False}
                sentence_files = [(f_s1, sentences[0]), (f_s2, sentences[1]), (f_s3, sentences[2])]
                for idx, (fname, sentence) in enumerate(sentence_files):
                    if not sentence:
                        continue
                    if self.cache.is_cached(fname):
                        sentence_results[idx] = True
                    else:
                        tasks[f"sent_{idx}"] = self.audio_fetcher.fetch(
                            sentence,
                            os.path.join(Config.MEDIA_DIR, fname)
                        )

                task_results: Dict[str, bool] = {}
                if tasks:
                    task_keys = list(tasks.keys())
                    task_values = await asyncio.gather(*tasks.values(), return_exceptions=True)
                    for key, value in zip(task_keys, task_values):
                        task_results[key] = bool(value) if not isinstance(value, Exception) else False

                has_img_result = task_results.get("img", False)
                has_w_result = task_results.get("word", False)
                has_s1 = task_results.get("sent_0", sentence_results[0])
                has_s2 = task_results.get("sent_1", sentence_results[1])
                has_s3 = task_results.get("sent_2", sentence_results[2])
                
                has_img = has_img or has_img_result
                has_w = has_w or has_w_result
                
                # Update stats (thread-safe)
                if has_img:
                    self.stats.increment('images_success')
                    self.cache.mark_cached(f_img)
                else:
                    self.stats.increment('images_failed')
                
                if has_w:
                    self.stats.increment('audio_word_success')
                    self.cache.mark_cached(f_word)
                else:
                    self.stats.increment('audio_word_failed')
                
                # Track sentence audio statistics
                for has_s, sent_idx in [(has_s1, 0), (has_s2, 1), (has_s3, 2)]:
                    if has_s:
                        self.stats.increment('audio_sent_success')
                        self.cache.mark_cached([f_s1, f_s2, f_s3][sent_idx])
                    elif sent_idx < len(sentences) and sentences[sent_idx]:
                        self.stats.increment('audio_sent_failed')
                
                # Add media files (thread-safe)
                if has_img:
                    self._add_media_file(os.path.join(Config.MEDIA_DIR, f_img))
                if has_w:
                    self._add_media_file(os.path.join(Config.MEDIA_DIR, f_word))
                if has_s1:
                    self._add_media_file(os.path.join(Config.MEDIA_DIR, f_s1))
                if has_s2:
                    self._add_media_file(os.path.join(Config.MEDIA_DIR, f_s2))
                if has_s3:
                    self._add_media_file(os.path.join(Config.MEDIA_DIR, f_s3))
                
                # Determine gender
                gender = "en" if self.language == "EN" else str(self._row_get(row, 'Gender', '')).strip().lower()
                if not gender or gender == "nan":
                    gender = "none"
                
                self._update_progress(clean_word)
                
                # Create note with card_uuid
                note = genanki.Note(
                    model=self.model,
                    fields=[
                        str(self._row_get(row, 'TargetWord', '')),
                        str(self._row_get(row, 'Meaning', '')),
                        str(self._row_get(row, 'IPA', '')),
                        str(self._row_get(row, 'Part_of_Speech', '')),
                        gender,
                        str(self._row_get(row, 'Morphology', '')),
                        str(self._row_get(row, 'Nuance', '')),
                        sentences[0], sentences[1], sentences[2],
                        clean_trans,
                        str(self._row_get(row, 'Etymology', '')),
                        str(self._row_get(row, 'Mnemonic', '')),
                        clean_analogues,
                        f'<img src="{f_img}">' if has_img else "",
                        str(self._row_get(row, 'Tags', '')),
                        f"[sound:{f_word}]" if has_w else "",
                        f_s1 if has_s1 else "",
                        f_s2 if has_s2 else "",
                        f_s3 if has_s3 else "",
                        f_word if has_w else "",
                        cloze_context,
                        card_uuid
                    ],
                    tags=str(self._row_get(row, 'Tags', '')).split(),
                    guid=card_uuid
                )
                
                self.deck.add_note(note)
            
            except Exception as e:
                # Log detailed error for skipped rows and track for summary
                self.stats.increment('rows_failed')
                self.stats.add_failed_word(str(self._row_get(row, 'TargetWord', f'Row {index+1}'))[:50])
                self._emit("log", f"⚠️ Row {index+1} skipped due to error: {str(e)[:100]}")
                self._update_progress()
    
    def _update_progress(self, word: str = "") -> None:
        """Update and emit progress."""
        self._processed_items += 1
        if self._total_items > 0:
            percentage = (self._processed_items / self._total_items) * 100
            if self._should_emit_progress() or self._processed_items == self._total_items:
                self._emit("progress", word, percentage)
    
    async def build(self, csv_file: str) -> bool:
        """
        Build deck from CSV file.
        
        Args:
            csv_file: Path to vocabulary CSV
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(csv_file):
            self._emit("log", f"ERROR: {csv_file} not found!")
            return False
        
        try:
            self._emit("log", f"Voice: {Config.VOICE}")
            self._emit("log", f"Language: {self.language}")
            
            # Load vocabulary via VocabularyService (single source of truth)
            vocab_service = VocabularyService.load_from_csv(csv_file)
            df = vocab_service.get_shuffled_dataframe(shuffle=True)
            
            if df.empty:
                self._emit("log", "ERROR: No vocabulary data found!")
                return False
            
            self._emit("log", f"Loaded {len(df)} rows from CSV")
            
            # Check disk space before proceeding
            if not self._check_disk_space(len(df)):
                self._emit("log", "⚠️ Proceeding with low disk space warning...")
        
        except Exception as e:
            self._emit("log", f"CSV Error: {e}")
            return False
        
        await self._download_confetti()
        
        # Initialize progress tracking
        self._total_items = len(df)
        self._processed_items = 0
        # Log at most ~50 progress lines across the build
        self._log_every = max(1, self._total_items // 50)
        # Emit at most ~100 progress updates across the build
        self._progress_every = max(1, self._total_items // 100)
        
        self._emit("log", f"Processing {len(df)} words...")
        self._emit("progress", "Starting build...", 0.0)
        
        try:
            # Process in batches to avoid memory spike from creating all coroutines at once
            # This prevents OOM with large vocabularies (5000+ words)
            batch_size = 50
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                tasks = [self.process_row(row.Index, row) for row in batch_df.itertuples(index=True, name="Row")]
                await asyncio.gather(*tasks)
                
                # Allow event loop to process other events between batches
                await asyncio.sleep(0)
        finally:
            # Ensure fetchers are properly closed
            await self.image_fetcher.close()
            await self.audio_fetcher.close()
            # Flush any pending cache writes
            self.cache.flush()
        
        self._emit("progress", "Build complete", 100.0)
        return True

    def _should_log_progress(self, index: int) -> bool:
        """Return True when a row-level progress log should be emitted."""
        if self._total_items <= 0:
            return True
        if index == 0 or index + 1 == self._total_items:
            return True
        return (index + 1) % self._log_every == 0

    def _should_emit_progress(self) -> bool:
        """Return True when progress event should be emitted."""
        if self._total_items <= 0:
            return True
        if self._processed_items == 1 or self._processed_items == self._total_items:
            return True
        return self._processed_items % self._progress_every == 0
    
    def export(self, output_file: Optional[str] = None) -> None:
        """
        Export deck to APKG file.
        
        Args:
            output_file: Output filename (defaults to ankitect_<lang>.apkg)
        """
        if output_file is None:
            output_file = os.path.join(Config.OUTPUT_DIR, f"ankitect_{self.language.lower()}.apkg")
        
        with self._media_files_lock:
            valid_media = list(set([f for f in self.media_files if os.path.exists(f)]))
        
        # Calculate total size
        total_size = sum(os.path.getsize(f) for f in valid_media if os.path.exists(f))
        self.stats.set('total_bytes', total_size)
        
        # Backup old file
        if os.path.exists(output_file):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = output_file.replace(".apkg", f"_{timestamp}.apkg")
            os.rename(output_file, backup_file)
            self._emit("log", f"[*] Backup created: {backup_file}")
        
        # Create package
        package = genanki.Package(self.deck)
        package.media_files = valid_media
        package.write_to_file(output_file)
        
        self._print_statistics(output_file, total_size)
        self._cleanup_old_backups(output_file)
    
    def _print_statistics(self, filename: str, total_size: int) -> None:
        """Emit build statistics via callback."""
        stats = self.stats.get_all()
        elapsed = time.time() - stats.get('start_time', time.time())
        minutes, seconds = divmod(int(elapsed), 60)
        
        img_success = stats.get('images_success', 0)
        img_failed = stats.get('images_failed', 0)
        audio_w_success = stats.get('audio_word_success', 0)
        audio_w_failed = stats.get('audio_word_failed', 0)
        audio_s_success = stats.get('audio_sent_success', 0)
        audio_s_failed = stats.get('audio_sent_failed', 0)
        rows_failed = stats.get('rows_failed', 0)
        failed_words = stats.get('failed_words', [])
        
        img_total = img_success + img_failed
        audio_w_total = audio_w_success + audio_w_failed
        audio_s_total = audio_s_success + audio_s_failed
        
        img_pct = (img_success / img_total * 100) if img_total > 0 else 0
        audio_w_pct = (audio_w_success / audio_w_total * 100) if audio_w_total > 0 else 0
        audio_s_pct = (audio_s_success / audio_s_total * 100) if audio_s_total > 0 else 0
        
        size_mb = total_size / (1024 * 1024)
        file_size_mb = get_file_size_mb(filename)
        
        self._emit("log", "\n" + "="*60)
        self._emit("log", "BUILD STATISTICS")
        self._emit("log", "="*60)
        self._emit("log", f"[OK] Words processed:          {stats.get('words_processed', 0)}")
        self._emit("log", f"[IMG] Images downloaded:        {img_success}/{img_total} ({img_pct:.1f}%)")
        self._emit("log", f"[AUDIO] Word audio generated:     {audio_w_success}/{audio_w_total} ({audio_w_pct:.1f}%)")
        self._emit("log", f"[AUDIO] Sentence audio generated: {audio_s_success}/{audio_s_total} ({audio_s_pct:.1f}%)")
        self._emit("log", f"[TIME] Execution time:           {minutes}m {seconds}s")
        self._emit("log", f"[SIZE] Media size:               {size_mb:.1f} MB")
        self._emit("log", f"[FILE] Output file:              {file_size_mb:.1f} MB -> {filename}")
        
        # Report failed rows if any
        if rows_failed > 0:
            self._emit("log", f"\n[WARN] Rows failed:              {rows_failed}")
            if failed_words:
                self._emit("log", f"[WARN] Failed words:             {', '.join(failed_words[:10])}{'...' if len(failed_words) > 10 else ''}")
        
        if self.adaptive_stats['concurrency_adjustments'] > 0:
            self._emit("log", "\n[ADAPTIVE RATE LIMITING]:")
            self._emit("log", f"[ADJ] Rate limit events:        {self.adaptive_stats['concurrency_adjustments']}")
        
        self._emit("log", "="*60)
    
    def _cleanup_old_backups(self, current_file: str, keep_count: int = 3) -> None:
        """Clean up old backup files."""
        base_name = current_file.replace(".apkg", "")
        pattern = f"{base_name}_*.apkg"
        backups = sorted(Path('.').glob(os.path.basename(pattern)), key=os.path.getmtime, reverse=True)
        
        for old_backup in backups[keep_count:]:
            try:
                old_backup.unlink()
            except Exception:
                pass
