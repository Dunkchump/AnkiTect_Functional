"""Audio fetcher - TTS and audio downloads."""

import asyncio
import os
import re
import html
import random
from typing import Optional

import edge_tts

from ..config import Config
from .base import BaseFetcher


class AudioFetcher(BaseFetcher):
    """Handle audio generation via TTS (Edge TTS)."""
    
    def __init__(self):
        # Get available voices from config, fallback to single voice
        self.available_voices = Config.settings.get("available_voices", [Config.VOICE])
        self.voice = Config.VOICE
        
    def get_random_voice(self) -> str:
        """Get a random voice from available voices."""
        return random.choice(self.available_voices)
        
    def clean_text(self, text: str) -> str:
        """Clean text for TTS processing."""
        if not text:
            return ""
        
        # Unescape HTML entities
        text = html.unescape(str(text))
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove numbered lists
        text = re.sub(r'(^|\s)\d+[\.\)]\s*', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    async def fetch(self, source: str, output_path: str, volume: str = "+0%") -> bool:
        """
        Generate audio using Edge TTS with random voice selection.
        
        Args:
            source: Text to convert to speech
            output_path: Path to save MP3
            volume: Volume adjustment (e.g., "+0%", "+40%")
            
        Returns:
            True if successful, False otherwise
        """
        if not source or not str(source).strip():
            return False
        
        try:
            clean_text = self.clean_text(source)
            if not clean_text:
                return False
            
            # Select random voice for this audio
            selected_voice = self.get_random_voice()
            
            # Small delay before TTS
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            communicate = edge_tts.Communicate(clean_text, selected_voice, volume=volume)
            await communicate.save(output_path)
            return True
            
        except Exception as e:
            print(f"Error generating audio: {str(e)[:50]}")
            return False
