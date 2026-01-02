"""Image fetcher - generate images via Pollinations API."""

import asyncio
import os
import urllib.parse
import sys
from typing import Optional, Callable

import aiohttp

from ..config import Config
from .base import BaseFetcher


class ImageFetcher(BaseFetcher):
    """Handle image generation via Pollinations API."""
    
    def __init__(self, concurrency_callback: Optional[Callable] = None):
        """
        Initialize image fetcher.
        
        Args:
            concurrency_callback: Function to call for adaptive concurrency adjustments
        """
        self.concurrency_callback = concurrency_callback
        self.retries = Config.RETRIES
    
    async def _download_from_api(self, prompt: str, output_path: str) -> bool:
        """Generate and download image directly from Pollinations API."""
        if not Config.POLLINATIONS_API_KEY:
            return False
        
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
                
                headers = {
                    "Authorization": f"Bearer {Config.POLLINATIONS_API_KEY}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=Config.IMAGE_TIMEOUT)
                
                async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            # Check if we got a valid JPEG image
                            # Real images start with JPEG magic bytes and are at least 2KB
                            if content.startswith(b'\xff\xd8\xff') and len(content) > 2000:
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                with open(output_path, 'wb') as f:
                                    f.write(content)
                                return True
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
