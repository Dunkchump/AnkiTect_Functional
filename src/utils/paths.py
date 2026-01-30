"""
Media path generation utilities - Single source of truth for file naming.

Eliminates DRY violations by centralizing all media file path generation.
Used by builder.py, workbench.py, and any future components.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional

from ..config import Config


class MediaPathGenerator:
    """
    Centralized media file path generator.
    
    Ensures consistent naming conventions across the application.
    Single source of truth for audio/image file naming patterns.
    """
    
    # Version suffix for cache invalidation on format changes
    VERSION = "v54"
    
    # File extensions
    AUDIO_EXT = ".mp3"
    IMAGE_EXT = ".jpg"
    
    @classmethod
    def _get_media_dir(cls) -> Path:
        """Get media directory path."""
        return Path(Config.MEDIA_DIR)
    
    @classmethod
    def audio_word(cls, card_uuid: str, voice_id: Optional[str] = None) -> str:
        """
        Generate filename for word audio.
        
        Args:
            card_uuid: Unique card identifier
            voice_id: Voice identifier (defaults to Config.VOICE_ID)
            
        Returns:
            Filename like "_word_abc123_de_v54.mp3"
        """
        vid = voice_id or Config.VOICE_ID
        return f"_word_{card_uuid}_{vid}_{cls.VERSION}{cls.AUDIO_EXT}"
    
    @classmethod
    def audio_sentence(cls, card_uuid: str, index: int, voice_id: Optional[str] = None) -> str:
        """
        Generate filename for sentence audio.
        
        Args:
            card_uuid: Unique card identifier
            index: Sentence index (1-based)
            voice_id: Voice identifier (defaults to Config.VOICE_ID)
            
        Returns:
            Filename like "_sent_1_abc123_de_v54.mp3"
        """
        vid = voice_id or Config.VOICE_ID
        return f"_sent_{index}_{card_uuid}_{vid}_{cls.VERSION}{cls.AUDIO_EXT}"
    
    @classmethod
    def image(cls, card_uuid: str) -> str:
        """
        Generate filename for card image.
        
        Args:
            card_uuid: Unique card identifier
            
        Returns:
            Filename like "_img_abc123.jpg"
        """
        return f"_img_{card_uuid}{cls.IMAGE_EXT}"
    
    @classmethod
    def audio_word_path(cls, card_uuid: str, voice_id: Optional[str] = None) -> str:
        """
        Generate full path for word audio.
        
        Args:
            card_uuid: Unique card identifier
            voice_id: Voice identifier
            
        Returns:
            Full path to audio file
        """
        return str(cls._get_media_dir() / cls.audio_word(card_uuid, voice_id))
    
    @classmethod
    def audio_sentence_path(cls, card_uuid: str, index: int, voice_id: Optional[str] = None) -> str:
        """
        Generate full path for sentence audio.
        
        Args:
            card_uuid: Unique card identifier
            index: Sentence index (1-based)
            voice_id: Voice identifier
            
        Returns:
            Full path to audio file
        """
        return str(cls._get_media_dir() / cls.audio_sentence(card_uuid, index, voice_id))
    
    @classmethod
    def image_path(cls, card_uuid: str) -> str:
        """
        Generate full path for card image.
        
        Args:
            card_uuid: Unique card identifier
            
        Returns:
            Full path to image file
        """
        return str(cls._get_media_dir() / cls.image(card_uuid))
    
    @classmethod
    def generate_card_uuid(cls, word: str, pos: str, meaning: str, index: int, language: str) -> str:
        """
        Generate a unique, deterministic UUID for a card.
        
        Uses SHA-256 hash of word + part of speech + meaning + index
        to ensure uniqueness even for homographs (e.g., "Bank" as bench vs. institution).
        
        Args:
            word: Target word (normalized)
            pos: Part of speech
            meaning: Full meaning text
            index: Row index in source data
            language: Language code
            
        Returns:
            UUID string like "a1b2c3d4e5f6_DE"
        """
        unique_string = f"{word}|{pos}|{meaning}|{index}"
        base_hash = hashlib.sha256(unique_string.encode()).hexdigest()[:32]
        return f"{base_hash}_{language}"
    
    @classmethod
    def get_all_media_files(cls, card_uuid: str, voice_id: Optional[str] = None) -> dict:
        """
        Get all media filenames for a card.
        
        Args:
            card_uuid: Unique card identifier
            voice_id: Voice identifier
            
        Returns:
            Dictionary with keys: image, word, sent_1, sent_2, sent_3
        """
        vid = voice_id or Config.VOICE_ID
        return {
            'image': cls.image(card_uuid),
            'word': cls.audio_word(card_uuid, vid),
            'sent_1': cls.audio_sentence(card_uuid, 1, vid),
            'sent_2': cls.audio_sentence(card_uuid, 2, vid),
            'sent_3': cls.audio_sentence(card_uuid, 3, vid),
        }
