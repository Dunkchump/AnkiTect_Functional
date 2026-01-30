"""Audio fetcher - TTS and audio downloads."""

import asyncio
import os
import random
import uuid
from typing import Optional, Callable

import edge_tts

from ..config import Config
from ..utils.parsing import TextParser
from .base import BaseFetcher


class AudioFetcher(BaseFetcher):
    """Handle audio generation via TTS (Edge TTS)."""
    
    def __init__(self, concurrency_callback: Optional[Callable] = None):
        """
        Initialize audio fetcher.
        
        Args:
            concurrency_callback: Function to call for adaptive concurrency adjustments
        """
        # Get available voices from config, fallback to single voice
        self.available_voices = Config.settings.get("available_voices", [Config.VOICE])
        self.voice = Config.VOICE
        self.concurrency_callback = concurrency_callback
    
    async def close(self) -> None:
        """Cleanup resources. Edge TTS doesn't require explicit cleanup."""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    def get_random_voice(self) -> str:
        """Get a random voice from available voices."""
        return random.choice(self.available_voices)
        
    def clean_text(self, text: str) -> str:
        """Clean text for TTS processing using centralized TextParser."""
        return TextParser.clean_for_tts(text)
    
    async def fetch(self, source: str, output_path: str, volume: str = "+0%") -> bool:
        """
        Generate audio using Edge TTS with random voice selection.
        
        Uses atomic write pattern: write to temp file, then rename.
        
        Args:
            source: Text to convert to speech
            output_path: Path to save MP3
            volume: Volume adjustment (e.g., "+0%", "+40%")
            
        Returns:
            True if successful, False otherwise
        """
        if not source or not str(source).strip():
            return False
        
        temp_path = None
        try:
            clean_text = self.clean_text(source)
            if not clean_text:
                return False
            
            # Select random voice for this audio
            selected_voice = self.get_random_voice()
            
            # Add jitter to smooth out request spikes (0.1s - 0.5s)
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Atomic write: save to temp file first
            temp_path = f"{output_path}.{uuid.uuid4().hex[:8]}.tmp"
            
            communicate = edge_tts.Communicate(clean_text, selected_voice, volume=volume)
            await communicate.save(temp_path)
            
            # Verify file was created and has content
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                # Atomic rename
                os.replace(temp_path, output_path)
                temp_path = None  # Mark as successfully moved
                
                # Report success to callback
                if self.concurrency_callback:
                    self.concurrency_callback(status_code=200, is_success=True)
                
                return True
            else:
                return False
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limiting errors (HTTP 429)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"Rate limit hit (429): {error_msg[:50]}")
                if self.concurrency_callback:
                    self.concurrency_callback(status_code=429, is_success=False)
            else:
                print(f"Error generating audio: {error_msg[:50]}")
                if self.concurrency_callback:
                    self.concurrency_callback(is_success=False)
            
            return False
        
        finally:
            # Clean up temp file if it still exists (failed write)
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
