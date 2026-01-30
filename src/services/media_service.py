"""
Media Service - Centralized media generation and management.

Handles image and audio generation, caching, and file management.
Uses FetcherFactory for provider abstraction.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..fetchers import AudioFetcher, ImageFetcher


class MediaService:
    """
    Service for generating and managing media files.
    
    Provides high-level interface for image and audio generation,
    with built-in caching and progress reporting.
    """
    
    def __init__(
        self,
        media_dir: Optional[str] = None,
        concurrency_callback: Optional[Callable] = None
    ):
        """
        Initialize media service.
        
        Args:
            media_dir: Directory for media files (defaults to Config.MEDIA_DIR)
            concurrency_callback: Callback for adaptive concurrency
        """
        self.media_dir = Path(media_dir or Config.MEDIA_DIR)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        
        self._image_fetcher: Optional[ImageFetcher] = None
        self._audio_fetcher: Optional[AudioFetcher] = None
        self._concurrency_callback = concurrency_callback
    
    @property
    def image_fetcher(self) -> ImageFetcher:
        """Lazy-load image fetcher."""
        if self._image_fetcher is None:
            self._image_fetcher = ImageFetcher(
                concurrency_callback=self._concurrency_callback
            )
        return self._image_fetcher
    
    @property
    def audio_fetcher(self) -> AudioFetcher:
        """Lazy-load audio fetcher."""
        if self._audio_fetcher is None:
            self._audio_fetcher = AudioFetcher(
                concurrency_callback=self._concurrency_callback
            )
        return self._audio_fetcher
    
    async def close(self) -> None:
        """Clean up all fetchers."""
        if self._image_fetcher:
            await self._image_fetcher.close()
            self._image_fetcher = None
        if self._audio_fetcher:
            await self._audio_fetcher.close()
            self._audio_fetcher = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def get_image_path(self, card_uuid: str) -> Path:
        """
        Get the path for an image file.
        
        Args:
            card_uuid: Unique card identifier
            
        Returns:
            Path to image file
        """
        return self.media_dir / f"_img_{card_uuid}.jpg"
    
    def get_word_audio_path(self, card_uuid: str) -> Path:
        """
        Get the path for word audio file.
        
        Args:
            card_uuid: Unique card identifier
            
        Returns:
            Path to audio file
        """
        vid = Config.VOICE_ID
        return self.media_dir / f"_word_{card_uuid}_{vid}_v54.mp3"
    
    def get_sentence_audio_path(self, card_uuid: str, sentence_index: int) -> Path:
        """
        Get the path for sentence audio file.
        
        Args:
            card_uuid: Unique card identifier
            sentence_index: Sentence number (0, 1, or 2)
            
        Returns:
            Path to audio file
        """
        vid = Config.VOICE_ID
        return self.media_dir / f"_sent_{sentence_index + 1}_{card_uuid}_{vid}_v54.mp3"
    
    def file_exists(self, path: Path) -> bool:
        """Check if a media file exists and has content."""
        return path.exists() and path.stat().st_size > 100
    
    async def generate_image(
        self,
        prompt: str,
        card_uuid: str,
        force: bool = False
    ) -> Optional[Path]:
        """
        Generate an image for a vocabulary card.
        
        Args:
            prompt: Image generation prompt
            card_uuid: Unique card identifier
            force: If True, regenerate even if cached
            
        Returns:
            Path to generated image, or None on failure
        """
        output_path = self.get_image_path(card_uuid)
        
        # Check cache
        if not force and self.file_exists(output_path):
            return output_path
        
        # Generate
        success = await self.image_fetcher.fetch(prompt, str(output_path))
        
        if success and self.file_exists(output_path):
            return output_path
        return None
    
    async def generate_word_audio(
        self,
        word: str,
        card_uuid: str,
        volume: str = "+40%",
        force: bool = False
    ) -> Optional[Path]:
        """
        Generate audio for a word.
        
        Args:
            word: Word to synthesize
            card_uuid: Unique card identifier
            volume: Volume adjustment
            force: If True, regenerate even if cached
            
        Returns:
            Path to generated audio, or None on failure
        """
        output_path = self.get_word_audio_path(card_uuid)
        
        # Check cache
        if not force and self.file_exists(output_path):
            return output_path
        
        # Generate
        success = await self.audio_fetcher.fetch(word, str(output_path), volume=volume)
        
        if success and self.file_exists(output_path):
            return output_path
        return None
    
    async def generate_sentence_audio(
        self,
        sentence: str,
        card_uuid: str,
        sentence_index: int,
        force: bool = False
    ) -> Optional[Path]:
        """
        Generate audio for a sentence.
        
        Args:
            sentence: Sentence to synthesize
            card_uuid: Unique card identifier
            sentence_index: Sentence number (0, 1, or 2)
            force: If True, regenerate even if cached
            
        Returns:
            Path to generated audio, or None on failure
        """
        if not sentence or not sentence.strip():
            return None
        
        output_path = self.get_sentence_audio_path(card_uuid, sentence_index)
        
        # Check cache
        if not force and self.file_exists(output_path):
            return output_path
        
        # Generate
        success = await self.audio_fetcher.fetch(sentence, str(output_path))
        
        if success and self.file_exists(output_path):
            return output_path
        return None
    
    async def generate_all_media(
        self,
        card_uuid: str,
        image_prompt: str,
        word: str,
        sentences: List[str],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Generate all media for a card.
        
        Args:
            card_uuid: Unique card identifier
            image_prompt: Prompt for image generation
            word: Word for audio
            sentences: List of sentences for audio
            force: If True, regenerate even if cached
            
        Returns:
            Dictionary with paths and success status
        """
        results = {
            "image": None,
            "word_audio": None,
            "sentence_audio": [None, None, None],
            "success_count": 0,
            "failure_count": 0,
        }
        
        # Create tasks for parallel execution
        tasks = []
        
        # Image task
        if image_prompt:
            tasks.append(("image", self.generate_image(image_prompt, card_uuid, force)))
        
        # Word audio task
        if word:
            tasks.append(("word_audio", self.generate_word_audio(word, card_uuid, force=force)))
        
        # Sentence audio tasks
        for i, sentence in enumerate(sentences[:3]):
            if sentence and sentence.strip():
                tasks.append((f"sentence_{i}", self.generate_sentence_audio(sentence, card_uuid, i, force)))
        
        # Execute in parallel
        if tasks:
            task_results = await asyncio.gather(
                *[t[1] for t in tasks],
                return_exceptions=True
            )
            
            for (task_name, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    results["failure_count"] += 1
                elif result is not None:
                    if task_name == "image":
                        results["image"] = result
                    elif task_name == "word_audio":
                        results["word_audio"] = result
                    elif task_name.startswith("sentence_"):
                        idx = int(task_name.split("_")[1])
                        results["sentence_audio"][idx] = result
                    results["success_count"] += 1
                else:
                    results["failure_count"] += 1
        
        return results
    
    def get_all_media_files(self) -> List[Path]:
        """
        Get all media files in the media directory.
        
        Returns:
            List of paths to media files
        """
        if not self.media_dir.exists():
            return []
        
        media_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.mp3", "*.wav"]:
            media_files.extend(self.media_dir.glob(ext))
        
        return media_files
    
    def get_total_size_mb(self) -> float:
        """
        Get total size of all media files in MB.
        
        Returns:
            Total size in megabytes
        """
        total_bytes = sum(
            f.stat().st_size
            for f in self.get_all_media_files()
            if f.exists()
        )
        return total_bytes / (1024 * 1024)
    
    def cleanup_orphaned_files(self, valid_uuids: List[str]) -> int:
        """
        Remove media files that don't belong to any card.
        
        Args:
            valid_uuids: List of valid card UUIDs
            
        Returns:
            Number of files removed
        """
        removed = 0
        
        for f in self.get_all_media_files():
            # Extract UUID from filename
            name = f.stem  # e.g., "_img_abc123_DE"
            parts = name.split("_")
            
            if len(parts) >= 2:
                # Try to find UUID in filename
                file_uuid = None
                for i, part in enumerate(parts):
                    if len(part) >= 8:  # UUID is at least 8 chars
                        file_uuid = part
                        break
                
                if file_uuid and file_uuid not in valid_uuids:
                    try:
                        f.unlink()
                        removed += 1
                    except Exception:
                        pass
        
        return removed
