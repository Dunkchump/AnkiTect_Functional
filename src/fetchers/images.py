"""Image fetcher - generate images via Pollinations API."""

import asyncio
import os
import urllib.parse
import sys
import uuid
from typing import Optional, Callable

import aiohttp
import aiofiles

from ..config import Config
from .base import BaseFetcher


# Image format magic bytes for validation
IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpeg',      # JPEG
    b'\x89PNG': 'png',            # PNG  
    b'RIFF': 'webp',              # WebP (RIFF....WEBP)
    b'GIF8': 'gif',               # GIF
}


def detect_image_format(content: bytes) -> Optional[str]:
    """Detect image format from magic bytes."""
    if not content or len(content) < 4:
        return None
    for magic, fmt in IMAGE_MAGIC_BYTES.items():
        if content.startswith(magic):
            return fmt
    # Check WebP specifically (RIFF....WEBP)
    if content[:4] == b'RIFF' and len(content) > 12 and content[8:12] == b'WEBP':
        return 'webp'
    return None


class ImageFetcher(BaseFetcher):
    """Handle image generation via Pollinations API with session pooling."""
    
    def __init__(self, concurrency_callback: Optional[Callable] = None):
        """
        Initialize image fetcher.
        
        Args:
            concurrency_callback: Function to call for adaptive concurrency adjustments
        """
        self.concurrency_callback = concurrency_callback
        self.retries = Config.RETRIES
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared aiohttp session (connection pooling)."""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                headers = {
                    "Authorization": f"Bearer {Config.POLLINATIONS_API_KEY}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                connector = aiohttp.TCPConnector(
                    ssl=False,
                    limit=Config.CONCURRENCY * 2,  # Connection pool size
                    limit_per_host=Config.CONCURRENCY,
                )
                timeout = aiohttp.ClientTimeout(total=Config.IMAGE_TIMEOUT)
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    headers=headers,
                    timeout=timeout
                )
            return self._session
    
    async def close(self) -> None:
        """Close the aiohttp session. Call this when done with the fetcher."""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure session is closed."""
        await self.close()
    
    async def _download_from_api(self, prompt: str, output_path: str) -> bool:
        """Generate and download image directly from Pollinations API."""
        if not Config.POLLINATIONS_API_KEY:
            print("  [!] No API key configured - set POLLINATIONS_API_KEY")
            return False
        
        session = await self._get_session()
        
        for attempt in range(self.retries):
            try:
                # URL encode the prompt
                encoded_prompt = urllib.parse.quote(prompt)
                
                # Use the correct API endpoint format
                url = f"{Config.POLLINATIONS_API_URL}/{encoded_prompt}"
                
                # Parameters as URL query string
                params = {
                    "model": Config.POLLINATIONS_IMAGE_MODEL,
                    "width": "320",
                    "height": "200",
                    "nologo": "true",
                    "safe": "false"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Robust image format detection
                        img_format = detect_image_format(content)
                        if img_format and len(content) > 2000:
                            # Atomic write: write to temp file, then rename
                            temp_path = f"{output_path}.{uuid.uuid4().hex[:8]}.tmp"
                            try:
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                async with aiofiles.open(temp_path, 'wb') as f:
                                    await f.write(content)
                                # Atomic rename (overwrites existing)
                                os.replace(temp_path, output_path)
                                return True
                            except Exception as write_err:
                                # Clean up temp file on failure
                                if os.path.exists(temp_path):
                                    try:
                                        os.remove(temp_path)
                                    except Exception:
                                        pass
                                raise write_err
                        else:
                            # Check magic bytes to debug
                            magic = content[:10] if content else b''
                            msg = f"  [!] Invalid image: {len(content)} bytes, magic: {magic[:4]}"
                            print(msg, flush=True)
                            sys.stdout.flush()
                            if attempt < self.retries - 1:
                                await asyncio.sleep(2 ** (attempt + 1))
                    elif response.status == 401:
                        print(f"  [!] API Auth failed (401) - check your API key")
                        return False
                    elif response.status == 429:
                        print(f"  [!] API Rate limit (429), waiting...")
                        if self.concurrency_callback:
                            self.concurrency_callback(status_code=429, is_success=False)
                        await asyncio.sleep(5 * (2 ** attempt))
                    else:
                        print(f"  [!] API Error {response.status}")
                        await asyncio.sleep(2 ** attempt)
            except asyncio.TimeoutError:
                print(f"  [!] API Timeout, retrying...")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [!] API Exception: {str(e)[:60]}")
                await asyncio.sleep(2 ** attempt)
        
        return False
    
    async def fetch(self, source: str, output_path: str) -> bool:
        """
        Generate image using Pollinations API from prompt text.
        
        Args:
            source: Prompt text for image generation
            output_path: Path to save image
            
        Returns:
            True if successful, False otherwise
        """
        prompt = str(source).strip()
        
        if not prompt or len(prompt) < 5:
            return False
        
        # Generate image directly via Pollinations API
        success = await self._download_from_api(prompt, output_path)
        if success:
            if self.concurrency_callback:
                self.concurrency_callback(status_code=200, is_success=True)
            return True
        
        if self.concurrency_callback:
            self.concurrency_callback(is_success=False)
        return False
