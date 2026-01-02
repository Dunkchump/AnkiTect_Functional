"""Main Anki deck builder."""

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import genanki
import pandas as pd
from tqdm.asyncio import tqdm as atqdm

from ..config import Config
from ..models import CardData
from ..templates import CardTemplates
from ..fetchers import AudioFetcher, ImageFetcher
from ..utils import clean_text_for_display, format_analogues_html, ensure_dir, get_file_size_mb
from .cache import CacheManager


class AnkiDeckBuilder:
    """Main class for building Anki decks."""
    
    def __init__(self, language: str = "EN"):
        """
        Initialize deck builder.
        
        Args:
            language: Language code ('EN', 'DE', etc.)
        """
        self.language = language
        self._ensure_dirs()
        
        self.model = self._create_model()
        self.deck = genanki.Deck(Config.DECK_ID, Config.DECK_NAME)
        self.media_files: List[str] = []
        
        self.semaphore = asyncio.Semaphore(Config.CONCURRENCY)
        self.current_concurrency = Config.CONCURRENCY
        
        self.cache = CacheManager()
        self.audio_fetcher = AudioFetcher()
        self.image_fetcher = ImageFetcher(concurrency_callback=self._adjust_concurrency)
        
        # Statistics
        self.stats = {
            'words_processed': 0,
            'images_success': 0,
            'images_failed': 0,
            'audio_word_success': 0,
            'audio_word_failed': 0,
            'audio_sent_success': 0,
            'audio_sent_failed': 0,
            'total_bytes': 0,
            'start_time': time.time()
        }
        
        # Adaptive parallelization
        self.adaptive_stats = {
            'consecutive_success': 0,
            'consecutive_failures': 0,
            'last_status_429': False,
            'concurrency_adjustments': 0
        }
    
    def _ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        ensure_dir(Config.MEDIA_DIR)
        ensure_dir(Config.CACHE_DIR)
        ensure_dir(Config.OUTPUT_DIR)
        ensure_dir(Config.INPUT_DIR)
    
    def _adjust_concurrency(self, status_code: Optional[int] = None, is_success: Optional[bool] = None) -> None:
        """Adaptively adjust concurrency based on server response."""
        if status_code == 429:  # Too Many Requests
            self.adaptive_stats['last_status_429'] = True
            self.adaptive_stats['consecutive_success'] = 0
            self.adaptive_stats['consecutive_failures'] += 1
            
            if self.current_concurrency > 1:
                old = self.current_concurrency
                self.current_concurrency = max(1, int(self.current_concurrency * 0.5))
                if old != self.current_concurrency:
                    self.semaphore = asyncio.Semaphore(self.current_concurrency)
                    self.adaptive_stats['concurrency_adjustments'] += 1
                    print(f"[WARN] 429 Too Many Requests! Concurrency: {old} → {self.current_concurrency}")
        
        elif status_code and status_code < 400:
            self.adaptive_stats['consecutive_failures'] = 0
            self.adaptive_stats['consecutive_success'] += 1
            
            if (self.adaptive_stats['consecutive_success'] >= 5 and 
                self.current_concurrency < Config.CONCURRENCY * 2 and
                not self.adaptive_stats['last_status_429']):
                old = self.current_concurrency
                self.current_concurrency = min(Config.CONCURRENCY * 2, self.current_concurrency * 2)
                if old != self.current_concurrency:
                    self.semaphore = asyncio.Semaphore(self.current_concurrency)
                    self.adaptive_stats['concurrency_adjustments'] += 1
                    self.adaptive_stats['consecutive_success'] = 0
                    print(f"[OK] Server fast! Concurrency: {old} → {self.current_concurrency}")
        
        elif is_success is False:
            self.adaptive_stats['consecutive_success'] = 0
            self.adaptive_stats['consecutive_failures'] += 1
    
    def _create_model(self) -> genanki.Model:
        """Create Anki card model."""
        front_rec = CardTemplates.get_recognition_template(Config.LABEL)
        back_rec = CardTemplates.get_back_template(Config.FORVO_CODE)
        
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
        
        return genanki.Model(
            Config.MODEL_ID,
            f'AnkiTect {self.language}',
            fields=fields,
            templates=[
                {'name': '1. Recognition', 'qfmt': front_rec, 'afmt': back_rec},
                {'name': '2. Production', 'qfmt': CardTemplates.FRONT_PROD, 'afmt': back_rec},
                {'name': '3. Listening', 'qfmt': CardTemplates.FRONT_LIST, 'afmt': back_rec},
                {'name': '4. Context Cloze', 'qfmt': CardTemplates.FRONT_CLOZE, 'afmt': back_rec},
            ],
            css=CardTemplates.CSS
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
            self.media_files.append(path)
    
    async def process_row(self, index: int, row: pd.Series, total: int, pbar) -> None:
        """Process single vocabulary row."""
        await asyncio.sleep(0.05)  # Small stagger
        
        async with self.semaphore:
            try:
                raw_word = str(row.get('TargetWord', '')).strip()
                if not raw_word:
                    pbar.update(1)
                    return
                
                clean_word = re.sub(Config.STRIP_REGEX, '', raw_word, flags=re.IGNORECASE).strip()
                
                # Generate UUID
                base_hash = hashlib.md5((clean_word + str(row.get('Part_of_Speech', ''))).encode()).hexdigest()
                uuid = f"{base_hash}_{self.language}"
                
                self.stats['words_processed'] += 1
                print(f"[{index+1}/{total}] Processing: {clean_word}...")
                
                # Process sentences
                raw_context = str(row.get('ContextSentences', ''))
                sentences = [s.strip() for s in re.split(r'<br>|\n', raw_context) if s.strip()]
                while len(sentences) < 3:
                    sentences.append("")
                
                # Process translations
                raw_translation = str(row.get('ContextTranslation', ''))
                clean_trans = clean_text_for_display(raw_translation)
                
                # Process analogues
                raw_analogues = str(row.get('Analogues', ''))
                clean_analogues = format_analogues_html(raw_analogues)
                
                cloze_context = raw_context if raw_context else (sentences[0] if sentences[0] else "")
                
                # Generate file names
                vid = Config.VOICE_ID
                f_img = f"_img_{uuid}.jpg"
                f_word = f"_word_{uuid}_{vid}_v54.mp3"
                f_s1 = f"_sent_1_{uuid}_{vid}_v54.mp3"
                f_s2 = f"_sent_2_{uuid}_{vid}_v54.mp3"
                f_s3 = f"_sent_3_{uuid}_{vid}_v54.mp3"
                
                # Check cache and download/generate
                tasks = []
                
                # Image
                if self.cache.is_cached(f_img):
                    tasks.append(asyncio.sleep(0))
                    has_img = True
                else:
                    tasks.append(self.image_fetcher.fetch(str(row.get('ImagePrompt', '')), os.path.join(Config.MEDIA_DIR, f_img)))
                    has_img = False
                
                # Word audio
                if self.cache.is_cached(f_word):
                    tasks.append(asyncio.sleep(0))
                    has_w = True
                else:
                    tasks.append(self.audio_fetcher.fetch(raw_word, os.path.join(Config.MEDIA_DIR, f_word), volume="+40%"))
                    has_w = False
                
                # Sentence audio
                tasks.append(self.audio_fetcher.fetch(sentences[0], os.path.join(Config.MEDIA_DIR, f_s1)) if sentences[0] else asyncio.sleep(0))
                tasks.append(self.audio_fetcher.fetch(sentences[1], os.path.join(Config.MEDIA_DIR, f_s2)) if sentences[1] else asyncio.sleep(0))
                tasks.append(self.audio_fetcher.fetch(sentences[2], os.path.join(Config.MEDIA_DIR, f_s3)) if sentences[2] else asyncio.sleep(0))
                
                results = await asyncio.gather(*tasks)
                has_img_result, has_w_result, has_s1, has_s2, has_s3 = results
                
                has_img = has_img or has_img_result
                has_w = has_w or has_w_result
                
                # Update stats
                if has_img:
                    self.stats['images_success'] += 1
                    self.cache.mark_cached(f_img)
                else:
                    self.stats['images_failed'] += 1
                
                if has_w:
                    self.stats['audio_word_success'] += 1
                    self.cache.mark_cached(f_word)
                else:
                    self.stats['audio_word_failed'] += 1
                
                # Track sentence audio statistics
                for has_s, sent_idx in [(has_s1, 0), (has_s2, 1), (has_s3, 2)]:
                    if has_s:
                        self.stats['audio_sent_success'] += 1
                        self.cache.mark_cached([f_s1, f_s2, f_s3][sent_idx])
                    elif sent_idx < len(sentences) and sentences[sent_idx]:
                        self.stats['audio_sent_failed'] += 1
                
                # Add media files
                if has_img:
                    self.media_files.append(os.path.join(Config.MEDIA_DIR, f_img))
                if has_w:
                    self.media_files.append(os.path.join(Config.MEDIA_DIR, f_word))
                if has_s1:
                    self.media_files.append(os.path.join(Config.MEDIA_DIR, f_s1))
                if has_s2:
                    self.media_files.append(os.path.join(Config.MEDIA_DIR, f_s2))
                if has_s3:
                    self.media_files.append(os.path.join(Config.MEDIA_DIR, f_s3))
                
                # Determine gender
                gender = "en" if self.language == "EN" else str(row.get('Gender', '')).strip().lower()
                if not gender or gender == "nan":
                    gender = "none"
                
                pbar.update(1)
                
                # Create note
                note = genanki.Note(
                    model=self.model,
                    fields=[
                        str(row.get('TargetWord', '')),
                        str(row.get('Meaning', '')),
                        str(row.get('IPA', '')),
                        str(row.get('Part_of_Speech', '')),
                        gender,
                        str(row.get('Morphology', '')),
                        str(row.get('Nuance', '')),
                        sentences[0], sentences[1], sentences[2],
                        clean_trans,
                        str(row.get('Etymology', '')),
                        str(row.get('Mnemonic', '')),
                        clean_analogues,
                        f'<img src="{f_img}">' if has_img else "",
                        str(row.get('Tags', '')),
                        f"[sound:{f_word}]" if has_w else "",
                        f_s1 if has_s1 else "",
                        f_s2 if has_s2 else "",
                        f_s3 if has_s3 else "",
                        f_word if has_w else "",
                        cloze_context,
                        uuid
                    ],
                    tags=str(row.get('Tags', '')).split(),
                    guid=uuid
                )
                
                self.deck.add_note(note)
            
            except Exception as e:
                print(f"⚠️ Error processing row {index}: {e}")
    
    async def build(self, csv_file: str) -> bool:
        """
        Build deck from CSV file.
        
        Args:
            csv_file: Path to vocabulary CSV
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(csv_file):
            print(f"ERROR: {csv_file} not found!")
            return False
        
        try:
            print(f"Voice: {Config.VOICE}")
            print(f"Language: {self.language}")
            
            df = pd.read_csv(csv_file, sep='|', encoding='utf-8-sig').fillna('')
            print(f"Shuffling {len(df)} words...")
            df = df.sample(frac=1).reset_index(drop=True)
            df.columns = df.columns.str.strip()
        
        except Exception as e:
            print(f"CSV Error: {e}")
            return False
        
        await self._download_confetti()
        
        print(f"Processing {len(df)} words...\n")
        
        with atqdm(total=len(df), desc="Building deck", unit="word") as pbar:
            tasks = [self.process_row(i, row, len(df), pbar) for i, row in df.iterrows()]
            await asyncio.gather(*tasks)
        
        return True
    
    def export(self, output_file: Optional[str] = None) -> None:
        """
        Export deck to APKG file.
        
        Args:
            output_file: Output filename (defaults to ankitect_<lang>.apkg)
        """
        if output_file is None:
            output_file = os.path.join(Config.OUTPUT_DIR, f"ankitect_{self.language.lower()}.apkg")
        
        valid_media = list(set([f for f in self.media_files if os.path.exists(f)]))
        
        # Calculate total size
        total_size = sum(os.path.getsize(f) for f in valid_media if os.path.exists(f))
        self.stats['total_bytes'] = total_size
        
        # Backup old file
        if os.path.exists(output_file):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = output_file.replace(".apkg", f"_{timestamp}.apkg")
            os.rename(output_file, backup_file)
            print(f"[*] Backup created: {backup_file}")
        
        # Create package
        package = genanki.Package(self.deck)
        package.media_files = valid_media
        package.write_to_file(output_file)
        
        self._print_statistics(output_file, total_size)
        self._cleanup_old_backups(output_file)
    
    def _print_statistics(self, filename: str, total_size: int) -> None:
        """Print build statistics."""
        elapsed = time.time() - self.stats['start_time']
        minutes, seconds = divmod(int(elapsed), 60)
        
        img_total = self.stats['images_success'] + self.stats['images_failed']
        audio_w_total = self.stats['audio_word_success'] + self.stats['audio_word_failed']
        audio_s_total = self.stats['audio_sent_success'] + self.stats['audio_sent_failed']
        
        img_pct = (self.stats['images_success'] / img_total * 100) if img_total > 0 else 0
        audio_w_pct = (self.stats['audio_word_success'] / audio_w_total * 100) if audio_w_total > 0 else 0
        audio_s_pct = (self.stats['audio_sent_success'] / audio_s_total * 100) if audio_s_total > 0 else 0
        
        size_mb = total_size / (1024 * 1024)
        file_size_mb = get_file_size_mb(filename)
        
        print("\n" + "="*60)
        print("BUILD STATISTICS")
        print("="*60)
        print(f"[OK] Words processed:          {self.stats['words_processed']}")
        print(f"[IMG] Images downloaded:        {self.stats['images_success']}/{img_total} ({img_pct:.1f}%)")
        print(f"[AUDIO] Word audio generated:     {self.stats['audio_word_success']}/{audio_w_total} ({audio_w_pct:.1f}%)")
        print(f"[AUDIO] Sentence audio generated: {self.stats['audio_sent_success']}/{audio_s_total} ({audio_s_pct:.1f}%)")
        print(f"[TIME] Execution time:           {minutes}m {seconds}s")
        print(f"[SIZE] Media size:               {size_mb:.1f} MB")
        print(f"[FILE] Output file:              {file_size_mb:.1f} MB -> {filename}")
        
        if self.adaptive_stats['concurrency_adjustments'] > 0:
            print(f"\n[ADAPTIVE PARALLELIZATION]:")
            print(f"[ADJ] Adjustments:              {self.adaptive_stats['concurrency_adjustments']}")
            print(f"[CONC] Current concurrency:      {self.current_concurrency}/{Config.CONCURRENCY * 2}")
        
        print("="*60)
    
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
